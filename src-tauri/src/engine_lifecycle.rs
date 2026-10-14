//! Engine lifecycle (B1 debt payoff) — starts/stops the continuous engine process
//! (ADR-013) on demand, tied to whether the Aperçu panel is open, never running 100% of
//! the time the app is open (Jay's call, 2026-07-22: the engine holds GPU/capture
//! resources, only Diffuser/Produire need it). Relays every engine message to the
//! frontend as an `engine-message` event, and grafts the engine's preview window into the
//! Aperçu panel's OWN screen rect (option B, Jay 2026-07-23) — the frontend measures its
//! panel and reports the rect; this module keeps the native window following it as it
//! moves, resizes, or its tab goes inactive.
//!
//! Closing: `stop_engine_inner` never waits for the engine forever — it asks politely
//! (`Stop`), waits a bounded time, then kills (`wait_or_kill`). Closing the main window
//! ends the app (`exit_when_main_window_closes`), which stops the engine on the way out.
//! If the app is killed outright, the engine still exits on its own when its input pipe
//! closes (`stdin_reader.rs`).

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use hikari_protocol::{parse_engine_message, to_line, ControllerCommand, EngineMessage};
use tauri::{AppHandle, Emitter, Manager, State};

use crate::engine_bridge::engine_command;
use crate::preview_bridge::{graft_preview_window, hide_preview_window, position_preview_window};

/// The main window's label — the single window Hikari opens today (`tauri.conf.json`
/// declares no explicit label, so Tauri assigns the default `"main"`).
pub(crate) const MAIN_WINDOW_LABEL: &str = "main";

/// Sane placeholder rect (16:9, top-left) used only for the brief window between the
/// Aperçu panel mounting (which starts the engine) and its first real rect report — the
/// panel reports its true rect on mount, almost always before `PreviewReady` even arrives.
const FALLBACK_RECT: (i32, i32, u32, u32) = (0, 0, 320, 180);

/// How long a polite `Stop` is given before the engine is killed. The debug engine needs
/// about a second to free its sources; four leaves a wide margin without ever holding
/// the app (or its closing window) hostage.
const ENGINE_STOP_TIMEOUT: Duration = Duration::from_secs(4);

/// After the main window is gone, the process must end even if the normal exit path
/// never completes (measured 2026-10-13: the app stayed alive with no window).
const EXIT_WATCHDOG: Duration = Duration::from_secs(6);

pub(crate) struct EngineHandle {
    pub(crate) child: Child,
    pub(crate) stdin: ChildStdin,
    /// A-t-on demande a CE moteur de s'arreter ?
    ///
    /// Partage avec le fil qui lit sa sortie, qui n'a aucun autre moyen de le savoir. Un
    /// moteur qui s'eteint ecrit son inventaire de fin de vie — dont un decompte de fuites
    /// memoire que `libobs` classe en erreur. Sans ce drapeau, cet inventaire s'affichait
    /// a l'utilisateur sous « Le moteur a refuse » (Jay, 2026-09-07).
    pub(crate) stopping: Arc<AtomicBool>,
    /// Un direct est-il RÉELLEMENT en cours ? Posé par le fil qui lit la sortie du moteur,
    /// jamais par l'envoi d'un ordre : le moteur peut refuser (aucune destination), et une
    /// note posée trop tôt empêchait ensuite tout relancement du moteur (voir
    /// `plan_target_reload`). Partagé comme `stopping`, pour la même raison.
    pub(crate) streaming: Arc<AtomicBool>,
}

/// Ce que devient le drapeau « direct en cours » à la lecture d'un message du moteur.
/// Fonction pure : c'est la seule décision du sujet.
pub(crate) fn streaming_after(current: bool, msg: &EngineMessage) -> bool {
    match msg {
        EngineMessage::Started => true,
        EngineMessage::StreamStopped | EngineMessage::Stopped => false,
        _ => current,
    }
}

/// Runtime state: the engine child (if running), the grafted preview's HWND (if
/// grafted), and the last screen rect the Aperçu panel reported for itself.
pub(crate) struct EngineRuntime {
    pub(crate) handle: Option<EngineHandle>,
    pub(crate) preview_hwnd: Option<i64>,
    pub(crate) panel_rect: (i32, i32, u32, u32),
}

impl Default for EngineRuntime {
    fn default() -> Self {
        Self {
            handle: None,
            preview_hwnd: None,
            panel_rect: FALLBACK_RECT,
        }
    }
}

/// Tauri-managed wrapper — the default state is honest: nothing launches until the
/// Aperçu panel asks for it.
#[derive(Default)]
/// `pub(crate)` sur le champ depuis le decoupage du 2026-09-07 : les commandes de scenes
/// vivent maintenant dans `engine_scenes.rs` et prennent le verrou elles-memes, comme
/// avant. Le decoupage ne devait rien changer au comportement — leur faire passer par une
/// autre fonction aurait ete un second changement cache dans le premier.
pub struct EngineState(pub(crate) Mutex<EngineRuntime>);

/// Starts the continuous engine process if it isn't already running (idempotent — the
/// Aperçu panel calls this on mount, and mounting twice must never double-launch).
/// Relays every parsed `EngineMessage` to the frontend as an `engine-message` event, and
/// grafts the preview into the Aperçu panel's last-known rect as soon as `PreviewReady`
/// arrives.
#[tauri::command]
pub(crate) async fn start_engine(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<(), String> {
    start_engine_inner(&app, &state).await
}

async fn start_engine_inner(app: &AppHandle, state: &EngineState) -> Result<(), String> {
    let app = app.clone();
    // La destination est résolue AVANT de prendre le verrou : elle passe par le réseau, et
    // tenir un verrou pendant une attente réseau bloquerait tout le reste du cockpit.
    //
    // Elle est posée dans l'environnement du moteur, jamais envoyée en message : une clé de
    // diffusion est un secret, et le fil de messages est lisible par tout ce qui l'écoute.
    // Son absence n'est pas une panne — Hikari s'ouvre très bien sans compte connecté. Elle
    // devient un refus au moment de DIFFUSER, avec ses mots (voir `broadcast::resolve_target`).
    let target = crate::broadcast_target::resolve_broadcast_target().await;

    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    if guard.handle.is_some() {
        return Ok(());
    }

    // `engine_command` and not a bare `Command`: it carries the no-console-window flag on
    // Windows. Spawning the engine directly here would show a black terminal beside the
    // cockpit — the exact defect Jay reported on 2026-09-04.
    let mut command = engine_command().map_err(|err| err.to_string())?;
    if let Some((server, key)) = &target {
        command
            .env("HIKARI_RTMP_SERVER", server)
            .env("HIKARI_RTMP_KEY", key.expose());
    }
    // Réglages d'encodage choisis à la main (B-settings) — "auto" reste inchangé.
    crate::encoding_settings::apply_encoding_env(&app, &mut command);
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|err| format!("lancement du moteur: {err}"))?;
    let stdin = child.stdin.take().ok_or("stdin du moteur indisponible")?;
    let stdout = child.stdout.take().ok_or("stdout du moteur indisponible")?;
    let stopping = Arc::new(AtomicBool::new(false));
    let stopping_reader = Arc::clone(&stopping);
    let streaming = Arc::new(AtomicBool::new(false));
    let streaming_reader = Arc::clone(&streaming);
    // Le journal des directs (images perdues) : un fichier par jour dans le dossier de
    // données de l'application. Absent si ce dossier est introuvable — sans effet sur le moteur.
    let stream_log_dir = app.path().app_data_dir().ok().map(|dir| dir.join("logs"));

    std::thread::spawn(move || {
        // Le moteur a-t-il fini de s'initialiser ?
        //
        // Tout ce que `libobs` déclare AVANT est du bruit de démarrage : une carte
        // d'acquisition absente, un encodeur non installé, un périphérique audio qui ne
        // répond pas à l'inventaire. Rien de tout cela ne vient d'un geste de
        // l'utilisateur, et rien ne lui donne prise — le remonter fabrique un bandeau que
        // personne ne lit, donc un bandeau muet le jour où ça compte (Jay, 2026-09-06 :
        // « j'ai eu plusieurs erreurs lorsque l'application s'est lancée »).
        //
        // Après ce signal, un échec est la conséquence de quelque chose : ce que
        // l'utilisateur vient de demander, ou ce que la session rejoue pour lui.
        let mut initialized = false;
        let mut stream_log = crate::stream_log::StreamLog::new();
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            match parse_engine_message(&line) {
                Ok(msg) => {
                    streaming_reader.store(
                        streaming_after(streaming_reader.load(Ordering::Relaxed), &msg),
                        Ordering::Relaxed,
                    );
                    if let Some(dir) = &stream_log_dir {
                        let now = crate::accounts::vault::now_unix();
                        let settings = if matches!(msg, EngineMessage::Started) {
                            crate::stream_log::describe_encoding(&app)
                        } else {
                            String::new()
                        };
                        if let Some(entry) = stream_log.on_message(&msg, now, &settings) {
                            crate::stream_log::append_line(dir, now, &entry);
                        }
                    }
                    if let EngineMessage::PreviewReady { hwnd } = &msg {
                        graft_into_panel_rect(&app, *hwnd);
                    }
                    if matches!(msg, EngineMessage::Ready) {
                        initialized = true;
                    }
                    // Un refus laisse une trace datée, en plus du bandeau. Sans elle, un
                    // défaut que l'utilisateur voit à l'écran ne peut être remonté qu'à sa
                    // description — et la description ne dit jamais QUAND, dans la suite
                    // des messages, le refus est tombé (vécu le 2026-09-06 sur
                    // « Monitor Capture existe déjà »).
                    if let EngineMessage::Error { message } = &msg {
                        eprintln!("[engine] REFUS {message}");
                    }
                    if let EngineMessage::SceneList { scenes, active } = &msg {
                        eprintln!(
                            "[engine] SCENES actives={active} {:?}",
                            scenes
                                .iter()
                                .map(|scene| (
                                    &scene.name,
                                    scene.sources.iter().map(|s| &s.name).collect::<Vec<_>>()
                                ))
                                .collect::<Vec<_>>()
                        );
                    }
                    let _ = app.emit("engine-message", &msg);
                }
                Err(err) => {
                    // Ce qui n'est pas du protocole est le journal de `libobs`. Il portait
                    // la raison exacte d'une caméra restée noire — « pas assez de bande
                    // passante » — et personne ne la voyait, parce que tout atterrissait
                    // dans la console de développement (Jay, 2026-09-06).
                    if let Some(shown) = hikari_protocol::engine_log_to_show(
                        &line,
                        initialized,
                        stopping_reader.load(Ordering::Relaxed),
                    ) {
                        let _ =
                            app.emit("engine-message", &EngineMessage::Error { message: shown });
                    }
                    eprintln!("[engine] WARN unparsable line {line:?} ({err})")
                }
            }
        }
    });

    guard.handle = Some(EngineHandle {
        child,
        stdin,
        stopping,
        streaming,
    });
    Ok(())
}

/// Stops the engine cleanly (`ControllerCommand::Stop` over stdin, then waits for exit).
/// A no-op if it isn't running (the Aperçu panel calls this on unmount, and unmounting an
/// already-stopped engine must never error).
#[tauri::command]
pub(crate) fn stop_engine(state: State<EngineState>) -> Result<(), String> {
    stop_engine_inner(&state)
}

fn stop_engine_inner(state: &EngineState) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    guard.preview_hwnd = None;
    let Some(mut handle) = guard.handle.take() else {
        return Ok(());
    };
    // Dit AVANT d'envoyer l'ordre : ce que le moteur ecrira ensuite appartient a son
    // extinction, et n'est le refus de rien.
    handle.stopping.store(true, Ordering::Relaxed);
    let line = to_line(&ControllerCommand::Stop).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi Stop au moteur: {err}"))?;
    if !wait_or_kill(&mut handle.child, ENGINE_STOP_TIMEOUT) {
        eprintln!(
            "[engine] arrêt forcé : pas de réponse au signal de fin en {ENGINE_STOP_TIMEOUT:?}"
        );
    }
    Ok(())
}

/// Waits for `child` to exit, at most `timeout`, then kills it. Returns `true` when it
/// exited on its own. Never blocks forever: a stuck engine must not hold the app.
pub(crate) fn wait_or_kill(child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return true,
            Ok(None) if Instant::now() < deadline => {
                std::thread::sleep(Duration::from_millis(50));
            }
            // Deadline passed, or the state cannot be read: stop it for good.
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return false;
            }
        }
    }
}

/// The main window is gone: stop the engine, then end the app. A watchdog guarantees the
/// process ends even if the normal exit path does not (2026-10-13: the app stayed alive
/// with no window, its engine at 1 GB, until killed by hand).
pub(crate) fn exit_when_main_window_closes(app: &AppHandle) {
    let app = app.clone();
    std::thread::spawn(move || {
        std::thread::sleep(EXIT_WATCHDOG);
        eprintln!("[app] sortie forcée : l'arrêt normal n'a pas abouti");
        std::process::exit(0);
    });
    let state = app.state::<EngineState>();
    if let Err(err) = stop_engine_inner(&state) {
        eprintln!("[app] arrêt du moteur à la fermeture : {err}");
    }
    app.exit(0);
}

/// Starts the real RTMP stream (B2a). The engine resolves its target from its OWN
/// environment and never receives a key over this pipe — a secret on the wire is a path
/// we would have to un-build later (see `ControllerCommand::StartStream`).
///
/// A missing target is therefore NOT detectable here: the engine answers with an
/// `Error` message the interface displays. Better a real refusal from the engine than a
/// guess from the controller about an environment it does not own.
///
/// `test` (2026-09-19) : diffusion réelle vers l'ingest Twitch, marquée
/// `bandwidthtest` — mesurable, mais rien ne se publie ni ne prévient personne. Voir
/// `hikari_protocol::with_bandwidth_test`.
#[tauri::command]
pub(crate) fn start_stream(state: State<EngineState>, test: bool) -> Result<(), String> {
    // Le drapeau « direct en cours » n'est PAS posé ici : c'est le message `Started` du
    // moteur qui le pose (`streaming_after`). Un ordre envoyé n'est pas un direct démarré.
    send(
        &state,
        ControllerCommand::StartStream { test },
        "StartStream",
    )
}

/// Stops the current stream. The engine and its preview stay alive — only the output is
/// detached, so the cockpit keeps showing the scene it was broadcasting.
#[tauri::command]
pub(crate) fn stop_stream(state: State<EngineState>) -> Result<(), String> {
    let result = send(&state, ControllerCommand::StopStream, "StopStream");
    if let Ok(guard) = state.0.lock() {
        if let Some(handle) = guard.handle.as_ref() {
            handle.streaming.store(false, Ordering::Relaxed);
        }
    }
    result
}

/// Sends one command to the running engine, or says why it cannot.
pub(crate) fn send(
    state: &EngineState,
    command: ControllerCommand,
    name: &str,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&command).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi {name} au moteur: {err}"))
}

/// Records the Aperçu panel's current screen rect and, if the preview is already
/// grafted, repositions it there immediately (also un-hides it, matching
/// `preview_bridge::position_preview_window`'s own behavior). Called by the frontend on
/// mount and on every resize/move of the panel.
#[tauri::command]
pub(crate) fn position_preview(
    state: State<EngineState>,
    x: i32,
    y: i32,
    width: u32,
    height: u32,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    guard.panel_rect = (x, y, width, height);
    if let Some(engine_hwnd) = guard.preview_hwnd {
        position_preview_window(engine_hwnd, x, y, width, height);
    }
    Ok(())
}

/// Hides the grafted preview (if any) without stopping the engine — called when the
/// Aperçu panel's tab becomes inactive (another tab in the same dock group is now shown).
#[tauri::command]
pub(crate) fn hide_preview(state: State<EngineState>) -> Result<(), String> {
    let guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    if let Some(engine_hwnd) = guard.preview_hwnd {
        hide_preview_window(engine_hwnd);
    }
    Ok(())
}

/// Sends one mixer command to the engine (B6). Shared body of the five audio commands
/// below: they differ only by the payload, and repeating the lock/guard/serialize dance five
/// times is where a divergence would eventually creep in.
pub(crate) fn send_command(
    state: &State<EngineState>,
    command: ControllerCommand,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&command).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi audio au moteur: {err}"))
}

/// Grafts the engine's preview window (`engine_hwnd`, just announced via `PreviewReady`)
/// into the Aperçu panel's last-known rect (option B).
fn graft_into_panel_rect(app: &AppHandle, engine_hwnd: i64) {
    let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) else {
        eprintln!("[preview] main window not found, cannot graft");
        return;
    };
    let Ok(host_hwnd) = window.hwnd() else {
        eprintln!("[preview] could not read host window handle");
        return;
    };
    let state = app.state::<EngineState>();
    let Ok(mut guard) = state.0.lock() else {
        return;
    };
    let (x, y, w, h) = guard.panel_rect;
    if let Err(err) = graft_preview_window(engine_hwnd, host_hwnd.0 as i64, x, y, w, h) {
        eprintln!("[preview] graft failed: {err:#}");
        return;
    }
    guard.preview_hwnd = Some(engine_hwnd);
}

/// Fait arriver au moteur une cle de diffusion connectee APRES son lancement.
///
/// Le moteur lit sa cle dans son propre environnement, pose une seule fois au demarrage.
/// Avant cette fonction, connecter un compte n'avait donc aucun effet tant que toute
/// l'application n'etait pas fermee et rouverte (Jay, 2026-09-07) — un geste que rien
/// n'annoncait, et dont l'absence donnait un compte connecte qui ne diffusait pas.
///
/// Relance le moteur, et JAMAIS pendant un direct : la cle neuve ne sert qu'au direct
/// suivant, couper celui en cours coute infiniment plus cher.
pub(crate) async fn reload_broadcast_target(
    app: &AppHandle,
    state: &EngineState,
) -> Result<TargetReload, String> {
    let plan = {
        let guard = state
            .0
            .lock()
            .map_err(|_| "verrou moteur corrompu".to_string())?;
        plan_target_reload(
            guard.handle.is_some(),
            guard
                .handle
                .as_ref()
                .is_some_and(|handle| handle.streaming.load(Ordering::Relaxed)),
        )
    };
    if plan == TargetReload::Restart {
        stop_engine_inner(state)?;
        start_engine_inner(app, state).await?;
    }
    Ok(plan)
}

/// Ce qu'il faut faire quand un compte vient d'etre connecte et que la cle de diffusion a
/// change.
///
/// Le moteur lit sa cle dans son PROPRE environnement, pose au moment ou on le lance : une
/// cle arrivee apres coup ne l'atteint pas. La seule facon de la lui donner est de le
/// relancer — sauf s'il diffuse, auquel cas relancer couperait le direct.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TargetReload {
    /// Le moteur ne tourne pas : il lira la cle neuve a son prochain demarrage, sans geste.
    NothingToDo,
    /// Le moteur tourne a vide : on le relance, la cle neuve arrive dans son environnement.
    Restart,
    /// Un direct est en cours : on ne le coupe pas pour une cle qui ne sert qu'au suivant.
    RefusedWhileLive,
}

/// Decide, sans rien executer. Fonction pure : c'est la seule partie de ce sujet ou une
/// erreur coupe un direct, et c'est donc la seule qui merite un test.
pub fn plan_target_reload(engine_running: bool, streaming: bool) -> TargetReload {
    match (engine_running, streaming) {
        (false, _) => TargetReload::NothingToDo,
        (true, true) => TargetReload::RefusedWhileLive,
        (true, false) => TargetReload::Restart,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_do_nothing_when_the_engine_is_not_running() {
        assert_eq!(plan_target_reload(false, false), TargetReload::NothingToDo);
    }

    #[test]
    fn should_restart_the_engine_when_it_runs_idle() {
        // Sans cela, connecter un compte n'avait aucun effet avant de fermer et rouvrir
        // toute l'application (Jay, 2026-09-07).
        assert_eq!(plan_target_reload(true, false), TargetReload::Restart);
    }

    #[test]
    fn should_never_restart_the_engine_during_a_live() {
        // Un direct coute plus cher qu'une cle a jour : celle-ci ne sert qu'au direct
        // SUIVANT, alors que relancer couperait celui qui est en cours.
        assert_eq!(
            plan_target_reload(true, true),
            TargetReload::RefusedWhileLive
        );
    }

    #[test]
    fn should_not_restart_a_stopped_engine_even_if_a_stream_flag_lingers() {
        // Etat incoherent (un drapeau reste a vrai apres un arret brutal) : on retombe sur
        // le cas sur, jamais sur un relancement surprise.
        assert_eq!(plan_target_reload(false, true), TargetReload::NothingToDo);
    }

    #[test]
    fn should_note_a_live_only_when_the_engine_says_it_started() {
        // Constaté le 2026-10-14 : l'application notait « direct en cours » dès l'envoi de
        // l'ordre, le moteur refusait (aucune destination), et la note restait — plus aucune
        // reconnexion de compte ne relançait alors le moteur.
        assert!(streaming_after(false, &EngineMessage::Started));
        assert!(!streaming_after(
            false,
            &EngineMessage::Error {
                message: "Aucune destination de diffusion".into()
            }
        ));
    }

    #[test]
    fn should_forget_the_live_when_the_stream_or_the_engine_stops() {
        assert!(!streaming_after(true, &EngineMessage::StreamStopped));
        assert!(!streaming_after(true, &EngineMessage::Stopped));
    }

    #[test]
    fn should_keep_the_live_noted_through_ordinary_messages() {
        assert!(streaming_after(
            true,
            &EngineMessage::Frames {
                dropped: 0,
                total: 10
            }
        ));
        assert!(!streaming_after(false, &EngineMessage::Ready));
    }

    #[cfg(windows)]
    fn spawn_cmd(script: &str) -> std::process::Child {
        std::process::Command::new("cmd")
            .args(["/C", script])
            .stdout(Stdio::null())
            .spawn()
            .expect("cmd doit se lancer")
    }

    #[cfg(windows)]
    #[test]
    fn should_report_a_clean_exit_without_killing_anything() {
        let mut child = spawn_cmd("exit 0");

        let exited_alone = wait_or_kill(&mut child, std::time::Duration::from_secs(10));

        assert!(exited_alone);
    }

    #[cfg(windows)]
    #[test]
    fn should_kill_a_child_that_outlives_the_timeout() {
        // Un moteur qui ne répond plus au signal de fin ne doit jamais retenir l'application
        // à la fermeture : constaté le 2026-10-13, l'app restait en vie sans fenêtre, avec
        // son moteur à 1 Go, jusqu'à ce qu'on les tue à la main.
        let mut child = spawn_cmd("ping -n 40 127.0.0.1 >NUL");
        let started = std::time::Instant::now();

        let exited_alone = wait_or_kill(&mut child, std::time::Duration::from_millis(300));

        assert!(!exited_alone);
        assert!(started.elapsed() < std::time::Duration::from_secs(10));
        assert!(child.try_wait().expect("lecture de l'état").is_some());
    }
}
