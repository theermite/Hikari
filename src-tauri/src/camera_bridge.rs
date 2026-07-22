//! Camera bridge — the Tauri command wiring for real camera detection (B-cam tranche 1)
//! via `engine_bridge::run_detect_cameras`. Detection only — adding a camera into a LIVE,
//! rendered scene is separate debt (needs the continuous engine process, not yet launched
//! by the app — see PET B1 "Dette restante").

use hikari_protocol::CameraDevice;

use crate::engine_bridge::run_detect_cameras;

/// Lists the real camera devices detected on this machine — never a hardcoded/presumed
/// list (F-003's spirit applied to cameras). Blocking I/O, hence `spawn_blocking`.
#[tauri::command]
pub(crate) async fn list_cameras() -> Result<Vec<CameraDevice>, String> {
    tauri::async_runtime::spawn_blocking(run_detect_cameras)
        .await
        .map_err(|err| err.to_string())?
        .map_err(|err| err.to_string())
}
