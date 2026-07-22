//! Preflight bridge — the Tauri command wiring for `preflight.rs`'s pure decision logic
//! against a REAL, one-shot encoder detection (`engine_bridge::run_detect_encoders`,
//! B9 pré-vol option A). Never a continuous engine process — that wiring stays separate
//! debt (see PET B1 "Dette restante").

use crate::engine_bridge::run_detect_encoders;
use crate::preflight::go_live_allowed;

/// What the frontend shows after a pré-vol check: either the safe encoder actually
/// detected, or why Go Live is blocked (F-010/F-012) — never both, never neither.
#[derive(Clone, serde::Serialize)]
pub(crate) struct PreflightOutcome {
    ok: bool,
    encoder_name: Option<String>,
    hardware: Option<bool>,
    reason: Option<String>,
}

/// Runs a real pré-vol check: spawns the engine in one-shot detection mode (blocking I/O,
/// hence `spawn_blocking` — never on the async runtime's worker thread) and applies the
/// already-tested `go_live_allowed` decision to what it actually reported.
#[tauri::command]
pub(crate) async fn run_preflight() -> Result<PreflightOutcome, String> {
    let available = tauri::async_runtime::spawn_blocking(run_detect_encoders)
        .await
        .map_err(|err| err.to_string())?
        .map_err(|err| err.to_string())?;

    Ok(match go_live_allowed(&available) {
        Ok(encoder) => PreflightOutcome {
            ok: true,
            encoder_name: Some(encoder.name),
            hardware: Some(encoder.hardware),
            reason: None,
        },
        Err(_) => PreflightOutcome {
            ok: false,
            encoder_name: None,
            hardware: None,
            reason: Some("aucun encodeur reconnu détecté".to_string()),
        },
    })
}
