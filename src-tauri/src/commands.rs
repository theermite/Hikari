//! Tauri commands — the bridge between the frontend and the backend modules already
//! proven (B2b). Reuses the exact flow validated manually (`examples/*_manual_auth.rs`,
//! B2b) — no new backend logic, only the Tauri glue. Registered from `lib.rs` alongside
//! the deck commands (`deck_bridge`) — Tauri allows only one `invoke_handler`.

use tauri::{AppHandle, Emitter, State};

use crate::engine_lifecycle::{EngineState, TargetReload, reload_broadcast_target};

use crate::accounts::vault::{Platform, Secret, StoredToken};
use crate::accounts::{twitch, twitch_stream, vault, youtube};

/// What the frontend shows while waiting for the user to authorize in their browser.
#[derive(Clone, serde::Serialize)]
struct TwitchCodePayload {
    verification_uri: String,
    user_code: String,
}

/// Ouvre `url` avec l'application que Windows associe aux adresses web.
///
/// Trois voies ont été essayées, deux sont écartées et voici pourquoi :
///   — `cmd /C start` réanalyse sa ligne de commande et prend un `&` non échappé pour un
///     séparateur : toute adresse à plus d'un paramètre était tronquée en silence (vécu
///     dans `examples/youtube_manual_auth.rs`, Google ne voyait que le premier) ;
///   — `explorer.exe <adresse>` fonctionne souvent et, sur certaines configurations,
///     ouvre l'EXPLORATEUR DE FICHIERS au lieu du navigateur (vécu par Jay, 2026-09-06).
///     C'est un gestionnaire de fichiers à qui l'on demande un travail qui n'est pas le
///     sien ; qu'il l'ait fait un temps était une chance, pas un contrat.
///
/// Reste l'appel que Windows expose POUR cela. Il ne réanalyse aucune ligne de commande,
/// donc le défaut du `&` ne peut pas revenir, et c'est le même chemin que celui d'un clic
/// sur un lien depuis n'importe quelle application.
fn open_in_browser(url: &str) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows::Win32::UI::Shell::ShellExecuteW;
    use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
    use windows::core::PCWSTR;

    // Windows attend du texte en 16 bits terminé par zéro ; une adresse en contient
    // rarement, mais un accent dans un paramètre suffirait à casser une conversion naïve.
    let wide = |texte: &str| {
        std::ffi::OsStr::new(texte).encode_wide().chain(std::iter::once(0)).collect::<Vec<u16>>()
    };
    let operation = wide("open");
    let cible = wide(url);
    // Safety: les deux chaînes vivent jusqu'à la fin de l'appel, et sont terminées par
    // zéro comme l'API l'exige. Aucune fenêtre parente : l'appel vient d'une commande, pas
    // d'un clic dans une fenêtre à nous.
    let resultat = unsafe {
        ShellExecuteW(
            None,
            PCWSTR(operation.as_ptr()),
            PCWSTR(cible.as_ptr()),
            PCWSTR::null(),
            PCWSTR::null(),
            SW_SHOWNORMAL,
        )
    };
    // Cette fonction rend un pseudo-descripteur : au-dessus de 32 il a réussi, en dessous
    // c'est un code d'erreur. Contrat de l'API, et le seul moyen de savoir qu'elle a
    // échoué — sans ce test, un échec passerait pour un succès.
    if resultat.0 as usize > 32 {
        Ok(())
    } else {
        Err(std::io::Error::other(format!(
            "Windows n'a pas pu ouvrir l'adresse (code {})",
            resultat.0 as usize
        )))
    }
}

/// Runs the real Twitch Device Code flow (B2b, already proven manually) and stores the
/// resulting token in the OS credential store. Emits `twitch-code` as soon as the
/// verification URL/code are known (so the UI can show them immediately, not just at the
/// end), then `twitch-connected` or `twitch-error` when the flow concludes.
///
/// The single `Err` exit at the bottom (rather than each fallible step emitting its own
/// `twitch-error`) is deliberate: found in the field (2026-07-19, YouTube's twin bug, same
/// shape) that an early failure — e.g. `start_device_flow` erroring before ANY event is
/// emitted — leaves the UI stuck on "waiting" forever with zero feedback, because the
/// frontend's `invoke().catch()` swallows the rejection silently. Routing every fallible
/// step through `try_connect_twitch` and emitting exactly once here, on the one path all
/// errors funnel through, makes "no visible error" structurally impossible instead of
/// relying on each call site to remember to emit.
#[tauri::command]
pub(crate) async fn connect_twitch(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<(), String> {
    let result = try_connect_twitch(&app).await;
    if let Err(message) = &result {
        let _ = app.emit("twitch-error", message.clone());
    }
    if result.is_ok() {
        announce_target_reload(&app, &state).await;
    }
    result
}

/// Fait parvenir au moteur la cle du compte qu'on vient de connecter, et le DIT quand il
/// ne peut pas la recevoir tout de suite.
///
/// Sans ce relais, le compte etait connecte et la diffusion restait impossible jusqu'a la
/// fermeture complete de l'application, sans que rien ne l'annonce (Jay, 2026-09-07). Le
/// refus pendant un direct n'est pas une panne : il est normal, il est dit, et il se
/// resout tout seul au direct suivant.
async fn announce_target_reload(app: &AppHandle, state: &EngineState) {
    match reload_broadcast_target(app, state).await {
        Ok(TargetReload::RefusedWhileLive) => {
            let _ = app.emit(
                "engine-notice",
                "Compte connecté. La nouvelle clé de diffusion sera prise en compte au prochain direct — le direct en cours n'est pas interrompu.".to_string(),
            );
        }
        Ok(_) => {}
        Err(err) => {
            let _ = app.emit(
                "engine-notice",
                format!("Compte connecté, mais le moteur n'a pas pu relire la clé ({err}). Ferme et rouvre Hikari pour diffuser."),
            );
        }
    }
}

async fn try_connect_twitch(app: &AppHandle) -> Result<(), String> {
    let http = reqwest::Client::new();
    let (mut builder, prompt) = twitch::start_device_flow(twitch::TWITCH_CLIENT_ID, &http)
        .await
        .map_err(|err| err.to_string())?;

    let _ = app.emit(
        "twitch-code",
        TwitchCodePayload { verification_uri: prompt.verification_uri.clone(), user_code: prompt.user_code },
    );
    let _ = open_in_browser(&prompt.verification_uri);

    let token = twitch::wait_for_authorization(&mut builder, &http).await.map_err(|err| err.to_string())?;
    // Le nom du compte est lu MAINTENANT, pas au prochain demarrage du moteur.
    //
    // Il l'etait, et ca ne suffisait pas : quand Jay se reconnecte depuis l'ecran
    // Parametres, le moteur ne tourne pas (le panneau Apercu est ferme), donc rien ne le
    // relance, donc rien ne lisait le nom — et « gurugonc » disparaissait de l'ecran juste
    // apres s'y etre affiche (2026-09-07). Une donnee dont le remplissage depend d'un autre
    // evenement est une donnee qui manque le jour ou cet evenement n'arrive pas.
    //
    // Un echec de lecture n'annule PAS la connexion : le compte est connecte, seul son nom
    // manque. Le refuser ici transformerait un confort en panne.
    let nom = twitch_stream::fetch_display_name(&http, twitch::TWITCH_CLIENT_ID, &token.access_token)
        .await
        .map_err(|err| {
            eprintln!("[twitch] nom du compte illisible ({err}) — connexion conservee");
        })
        .ok();
    let token = StoredToken { account_name: nom, ..token };
    vault::store(Platform::Twitch, &token).map_err(|err| err.to_string())?;
    let _ = app.emit("twitch-connected", ());
    Ok(())
}

/// Runs the real YouTube Authorization Code + PKCE flow (B2b, already proven manually via
/// `examples/youtube_manual_auth.rs`) and stores the resulting token in the OS credential
/// store. Credentials come from the environment ONLY (`YOUTUBE_CLIENT_ID`/
/// `YOUTUBE_CLIENT_SECRET`, Jay's own Google Cloud Console registration) — never hardcoded
/// (decision 2026-07-19: the repo is public with no other user yet, so there is no reason
/// to commit Jay's specific client credential; revisit if/when other users need to run the
/// app without setting env vars). Unlike Twitch's Device Code Flow, there is no code to
/// show the user, but the authorization URL IS emitted (`youtube-url`, mirroring
/// `twitch-code`'s timing — right after it's built, before `open_in_browser` is even
/// attempted) so the UI always has a clickable/copyable fallback: `open_in_browser`
/// spawning `explorer.exe` successfully does not guarantee the resulting window reaches
/// the foreground (Windows can block a background process from stealing focus — found
/// live 2026-07-19, Jay's browser opened but stayed unfocused behind the app, both
/// Twitch and YouTube).
/// Same single-exit shape as `connect_twitch` (see its doc comment) — here it is the fix
/// site: the env vars missing (the first thing to fail in practice, before any browser
/// opens) used to return early with zero event emitted, leaving the UI on "waiting"
/// forever (found live 2026-07-19, Jay's first real run).
#[tauri::command]
pub(crate) async fn connect_youtube(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<(), String> {
    let result = try_connect_youtube(&app).await;
    if let Err(message) = &result {
        let _ = app.emit("youtube-error", message.clone());
    }
    if result.is_ok() {
        announce_target_reload(&app, &state).await;
    }
    result
}

async fn try_connect_youtube(app: &AppHandle) -> Result<(), String> {
    let client_id = std::env::var("YOUTUBE_CLIENT_ID")
        .map_err(|_| "variable d'environnement YOUTUBE_CLIENT_ID absente".to_string())?;
    let client_secret = std::env::var("YOUTUBE_CLIENT_SECRET")
        .map_err(|_| "variable d'environnement YOUTUBE_CLIENT_SECRET absente".to_string())?;
    let client_secret = Secret::new(client_secret);

    let pending = youtube::start_authorization(&client_id);
    let _ = app.emit("youtube-url", pending.authorization_url.clone());
    let _ = open_in_browser(&pending.authorization_url);

    let http = reqwest::Client::new();
    let token = youtube::finish_authorization(pending, &client_id, &client_secret, &http)
        .await
        .map_err(|err| err.to_string())?;
    vault::store(Platform::YouTube, &token).map_err(|err| err.to_string())?;
    let _ = app.emit("youtube-connected", ());
    Ok(())
}

/// L'etat des comptes connectes, lu dans le coffre a la demande de l'ecran Comptes.
///
/// Pourquoi cette commande existe : l'ecran ne se souvenait de rien. Il partait de « pas
/// connecte » a chaque affichage et ne passait au vert que sur l'evenement `twitch-connected`
/// du moment. Sortir des Parametres puis y revenir suffisait donc a effacer la connexion —
/// a l'ecran seulement, le jeton etant reste dans le coffre tout du long (Jay, 2026-09-07).
///
/// Elle ne rend QUE des booleens : aucun jeton, aucune date d'expiration ne traverse vers
/// l'interface. Un secret ne sort pas du coffre pour alimenter un affichage.
#[tauri::command]
pub(crate) fn account_status() -> crate::accounts::AccountStatus {
    crate::accounts::read_status()
}
