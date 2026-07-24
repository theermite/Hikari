//! Engine lifecycle (B1 debt payoff) — starts/stops the continuous engine process
//! (ADR-013) on demand, tied to whether the Aperçu panel is open, never running 100% of
//! the time the app is open (Jay's call, 2026-07-22: the engine holds GPU/capture
//! resources, only Diffuser/Produire need it). Relays every engine message to the
//! frontend as an `engine-message` event, and grafts the engine's preview window into the
//! Aperçu panel's OWN screen rect (option B, Jay 2026-07-23) — the frontend measures its
//! panel and reports the rect; this module keeps the native window following it as it
//! moves, resizes, or its tab goes inactive.
//!
//! Known gap: if the app process itself is killed (not just the Aperçu panel closed),
//! the engine child is not guaranteed to die with it (Windows does not do this by
//! default) — acceptable for this brick, revisit if it causes a real orphaned-process
//! problem in practice.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;

use hikari_protocol::{ControllerCommand, EngineMessage, parse_engine_message, to_line};
use tauri::{AppHandle, Emitter, Manager, State};

use crate::engine_bridge::engine_path;
use crate::preview_bridge::{graft_preview_window, hide_preview_window, position_preview_window};

/// The main window's label — the single window Hikari opens today (`tauri.conf.json`
/// declares no explicit label, so Tauri assigns the default `"main"`).
const MAIN_WINDOW_LABEL: &str = "main";

/// Sane placeholder rect (16:9, top-left) used only for the brief window between the
/// Aperçu panel mounting (which starts the engine) and its first real rect report — the
/// panel reports its true rect on mount, almost always before `PreviewReady` even arrives.
const FALLBACK_RECT: (i32, i32, u32, u32) = (0, 0, 320, 180);

struct EngineHandle {
    child: Child,
    stdin: ChildStdin,
}

/// Runtime state: the engine child (if running), the grafted preview's HWND (if
/// grafted), and the last screen rect the Aperçu panel reported for itself.
struct EngineRuntime {
    handle: Option<EngineHandle>,
    preview_hwnd: Option<i64>,
    panel_rect: (i32, i32, u32, u32),
}

impl Default for EngineRuntime {
    fn default() -> Self {
        Self { handle: None, preview_hwnd: None, panel_rect: FALLBACK_RECT }
    }
}

/// Tauri-managed wrapper — the default state is honest: nothing launches until the
/// Aperçu panel asks for it.
#[derive(Default)]
pub struct EngineState(Mutex<EngineRuntime>);

/// Starts the continuous engine process if it isn't already running (idempotent — the
/// Aperçu panel calls this on mount, and mounting twice must never double-launch).
/// Relays every parsed `EngineMessage` to the frontend as an `engine-message` event, and
/// grafts the preview into the Aperçu panel's last-known rect as soon as `PreviewReady`
/// arrives.
#[tauri::command]
pub(crate) fn start_engine(app: AppHandle, state: State<EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    if guard.handle.is_some() {
        return Ok(());
    }

    let engine = engine_path().map_err(|err| err.to_string())?;
    let mut child = Command::new(&engine)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|err| format!("lancement du moteur: {err}"))?;
    let stdin = child.stdin.take().ok_or("stdin du moteur indisponible")?;
    let stdout = child.stdout.take().ok_or("stdout du moteur indisponible")?;

    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            match parse_engine_message(&line) {
                Ok(msg) => {
                    if let EngineMessage::PreviewReady { hwnd } = &msg {
                        graft_into_panel_rect(&app, *hwnd);
                    }
                    let _ = app.emit("engine-message", &msg);
                }
                Err(err) => eprintln!("[engine] WARN unparsable line {line:?} ({err})"),
            }
        }
    });

    guard.handle = Some(EngineHandle { child, stdin });
    Ok(())
}

/// Stops the engine cleanly (`ControllerCommand::Stop` over stdin, then waits for exit).
/// A no-op if it isn't running (the Aperçu panel calls this on unmount, and unmounting an
/// already-stopped engine must never error).
#[tauri::command]
pub(crate) fn stop_engine(state: State<EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    guard.preview_hwnd = None;
    let Some(mut handle) = guard.handle.take() else {
        return Ok(());
    };
    let line = to_line(&ControllerCommand::Stop).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi Stop au moteur: {err}"))?;
    handle.child.wait().map_err(|err| format!("attente arrêt moteur: {err}"))?;
    Ok(())
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
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
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
    let guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    if let Some(engine_hwnd) = guard.preview_hwnd {
        hide_preview_window(engine_hwnd);
    }
    Ok(())
}

/// Adds a webcam source to the live scene (B-cam) by sending `AddCamera` to the already-
/// running engine. Requires the engine to be running (Aperçu panel open) — a clear error
/// beats a silent no-op if it isn't, since there's no queue to "add it once started".
#[tauri::command]
pub(crate) fn add_camera_source(state: State<EngineState>, device_id: String) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::AddCamera { device_id }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi AddCamera au moteur: {err}"))
}

/// Removes the webcam from the live scene entirely (its filters go with it) — the real
/// way to "turn the camera off" today, since individual filters can't be detached (see
/// `enable_background_removal`'s doc). A no-op if no camera is present.
#[tauri::command]
pub(crate) fn remove_camera_source(state: State<EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::RemoveCamera).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi RemoveCamera au moteur: {err}"))
}

/// Sets whether the real NVIDIA background-removal filter is applied to the webcam
/// (B-cam, F-036). Toggling REBUILDS the camera source (see
/// `ControllerCommand::SetBackgroundRemoval`'s own doc for why — no public filter-removal
/// API exists) — a brief camera reinit blip, disclosed to Jay. Requires the engine
/// running AND a camera already added.
#[tauri::command]
pub(crate) fn set_background_removal(state: State<EngineState>, enabled: bool) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::SetBackgroundRemoval { enabled }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi au moteur: {err}"))
}

/// Sets whether a circular alpha mask is applied to the webcam (B-cam, F-036). Same
/// rebuild-based toggle and requirements as `set_background_removal`.
#[tauri::command]
pub(crate) fn set_circle_mask(state: State<EngineState>, enabled: bool) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::SetCircleMask { enabled }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi au moteur: {err}"))
}

/// Moves the webcam by `(dx, dy)` scene pixels (B7 — arrow buttons, never a raw drag: the
/// dockview drag already broke silently in this WebView2 build, session 2026-07-23).
/// Requires the engine running AND a camera already added.
#[tauri::command]
pub(crate) fn nudge_camera(state: State<EngineState>, dx: i32, dy: i32) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::NudgeCamera { dx, dy }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi NudgeCamera au moteur: {err}"))
}

/// Grows or shrinks the webcam by one fixed step (B7). Same requirements as `nudge_camera`.
#[tauri::command]
pub(crate) fn scale_camera(state: State<EngineState>, grow: bool) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::ScaleCamera { grow }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi ScaleCamera au moteur: {err}"))
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
    let Ok(mut guard) = state.0.lock() else { return };
    let (x, y, w, h) = guard.panel_rect;
    if let Err(err) = graft_preview_window(engine_hwnd, host_hwnd.0 as i64, x, y, w, h) {
        eprintln!("[preview] graft failed: {err}");
        return;
    }
    guard.preview_hwnd = Some(engine_hwnd);
}
