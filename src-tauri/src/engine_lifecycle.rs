//! Engine lifecycle (B1 debt payoff, tranche 1) — starts/stops the continuous engine
//! process (ADR-013) on demand, tied to whether the Aperçu panel is open, never running
//! 100% of the time the app is open (Jay's call, 2026-07-22: the engine holds GPU/capture
//! resources, only Diffuser/Produire need it). Relays every engine message to the
//! frontend as a `engine-message` event. The native video graft into the Aperçu panel's
//! exact screen rect is separate, harder debt (real windowing work) — this brick proves
//! the on/off lifecycle and status only.
//!
//! Known gap: if the app process itself is killed (not just the Aperçu panel closed),
//! the engine child is not guaranteed to die with it (Windows does not do this by
//! default) — acceptable for this brick, revisit if it causes a real orphaned-process
//! problem in practice.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;

use hikari_protocol::{ControllerCommand, parse_engine_message, to_line};
use tauri::{AppHandle, Emitter, State};

use crate::engine_bridge::engine_path;

struct EngineHandle {
    child: Child,
    stdin: ChildStdin,
}

/// Holds the running engine child, if any. `None` = not running (the honest starting
/// state — nothing launches until the Aperçu panel asks for it).
#[derive(Default)]
pub struct EngineState(Mutex<Option<EngineHandle>>);

/// Starts the continuous engine process if it isn't already running (idempotent — the
/// Aperçu panel calls this on mount, and mounting twice must never double-launch).
/// Relays every parsed `EngineMessage` to the frontend as an `engine-message` event.
#[tauri::command]
pub(crate) fn start_engine(app: AppHandle, state: State<EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    if guard.is_some() {
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
                    let _ = app.emit("engine-message", &msg);
                }
                Err(err) => eprintln!("[engine] WARN unparsable line {line:?} ({err})"),
            }
        }
    });

    *guard = Some(EngineHandle { child, stdin });
    Ok(())
}

/// Stops the engine cleanly (`ControllerCommand::Stop` over stdin, then waits for exit).
/// A no-op if it isn't running (the Aperçu panel calls this on unmount, and unmounting an
/// already-stopped engine must never error).
#[tauri::command]
pub(crate) fn stop_engine(state: State<EngineState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(mut handle) = guard.take() else {
        return Ok(());
    };
    let line = to_line(&ControllerCommand::Stop).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi Stop au moteur: {err}"))?;
    handle.child.wait().map_err(|err| format!("attente arrêt moteur: {err}"))?;
    Ok(())
}
