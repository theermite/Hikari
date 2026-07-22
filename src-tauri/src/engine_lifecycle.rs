//! Engine lifecycle (B1 debt payoff) — starts/stops the continuous engine process
//! (ADR-013) on demand, tied to whether the Aperçu panel is open, never running 100% of
//! the time the app is open (Jay's call, 2026-07-22: the engine holds GPU/capture
//! resources, only Diffuser/Produire need it). Relays every engine message to the
//! frontend as an `engine-message` event, and grafts the engine's preview window into the
//! WHOLE app window as soon as it's ready (option A, Jay 2026-07-23: the harder problem —
//! keeping the graft inside one specific, resizable dock panel — is separate, unproven
//! debt, deferred).
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
use crate::preview_bridge::{graft_preview_window, resize_preview_window};

/// The main window's label — the single window Hikari opens today (`tauri.conf.json`
/// declares no explicit label, so Tauri assigns the default `"main"`).
const MAIN_WINDOW_LABEL: &str = "main";

struct EngineHandle {
    child: Child,
    stdin: ChildStdin,
}

/// Runtime state: the engine child (if running) plus the grafted preview's HWND (if
/// grafted) — the latter is what `on_host_resized` needs to keep the preview filling the
/// window as it resizes.
#[derive(Default)]
struct EngineRuntime {
    handle: Option<EngineHandle>,
    preview_hwnd: Option<i64>,
}

/// Tauri-managed wrapper — `None`/empty fields are the honest starting state (nothing
/// launches until the Aperçu panel asks for it).
#[derive(Default)]
pub struct EngineState(Mutex<EngineRuntime>);

/// Starts the continuous engine process if it isn't already running (idempotent — the
/// Aperçu panel calls this on mount, and mounting twice must never double-launch).
/// Relays every parsed `EngineMessage` to the frontend as an `engine-message` event, and
/// grafts the preview into the whole app window as soon as `PreviewReady` arrives.
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
                        graft_into_main_window(&app, *hwnd);
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

/// Grafts the engine's preview window (`engine_hwnd`, just announced via `PreviewReady`)
/// into the whole main app window, sized to fit it (option A). Records the HWND in
/// `EngineState` so `on_host_resized` can keep it fitted as the window resizes.
fn graft_into_main_window(app: &AppHandle, engine_hwnd: i64) {
    let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) else {
        eprintln!("[preview] main window not found, cannot graft");
        return;
    };
    let (Ok(host_hwnd), Ok(size)) = (window.hwnd(), window.inner_size()) else {
        eprintln!("[preview] could not read host window handle/size");
        return;
    };
    if let Err(err) =
        graft_preview_window(engine_hwnd, host_hwnd.0 as i64, size.width, size.height)
    {
        eprintln!("[preview] graft failed: {err}");
        return;
    }
    if let Ok(mut guard) = app.state::<EngineState>().0.lock() {
        guard.preview_hwnd = Some(engine_hwnd);
    }
}

/// Re-fits the grafted preview (if any) when the host window resizes — a no-op before
/// the engine has announced its preview window. Called from the main window's own resize
/// handler, registered once at app setup (see `run()`).
pub(crate) fn on_host_resized(state: &State<EngineState>, host_w: u32, host_h: u32) {
    let Ok(guard) = state.0.lock() else { return };
    let Some(engine_hwnd) = guard.preview_hwnd else { return };
    resize_preview_window(engine_hwnd, host_w, host_h);
}
