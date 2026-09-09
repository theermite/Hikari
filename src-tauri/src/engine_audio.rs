//! Commandes du mixeur audio (B6) — la couche mince entre l'interface et le moteur.
//!
//! Extraites de `engine_lifecycle.rs` le 2026-09-07, meme raison que les scenes : le
//! fichier depassait le plafond de 500 lignes. Aucun changement de comportement.

use tauri::State;

use hikari_protocol::ControllerCommand;

use crate::engine_lifecycle::{send_command, EngineState};

/// Asks the engine for the machine's real audio devices (B6).
#[tauri::command]
pub(crate) fn list_audio_devices(state: State<EngineState>) -> Result<(), String> {
    send_command(&state, ControllerCommand::ListAudioDevices)
}

/// Adds a microphone or desktop-audio capture to the mixer (B6).
#[tauri::command]
pub(crate) fn add_audio_source(
    state: State<EngineState>,
    device_id: String,
    kind: hikari_protocol::AudioSourceKind,
    name: String,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::AddAudioSource {
            device_id,
            kind,
            name,
        },
    )
}

/// Removes an audio source from the mixer (B6).
#[tauri::command]
pub(crate) fn remove_audio_source(state: State<EngineState>, name: String) -> Result<(), String> {
    send_command(&state, ControllerCommand::RemoveAudioSource { name })
}

/// Sets a mixer source's volume from a 0–100 slider position (B6).
#[tauri::command]
pub(crate) fn set_audio_volume(
    state: State<EngineState>,
    name: String,
    percent: i32,
) -> Result<(), String> {
    send_command(&state, ControllerCommand::SetAudioVolume { name, percent })
}

/// Mutes or unmutes a mixer source (B6).
#[tauri::command]
pub(crate) fn set_audio_muted(
    state: State<EngineState>,
    name: String,
    muted: bool,
) -> Result<(), String> {
    send_command(&state, ControllerCommand::SetAudioMuted { name, muted })
}

/// Sets whether the streamer hears a source, and whether the audience does (B6).
#[tauri::command]
pub(crate) fn set_audio_monitoring(
    state: State<EngineState>,
    name: String,
    monitoring: hikari_protocol::AudioMonitoring,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetAudioMonitoring { name, monitoring },
    )
}

/// Sets room-noise suppression for a microphone: on/off, method, and Speex's strength (B6).
#[tauri::command]
pub(crate) fn set_noise_settings(
    state: State<EngineState>,
    name: String,
    enabled: bool,
    method: hikari_protocol::NoiseMethod,
    level_db: f32,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetNoiseSettings {
            name,
            enabled,
            method,
            level_db,
        },
    )
}

/// Sets the volume the streamer hears, independently of the audience's (B6).
#[tauri::command]
pub(crate) fn set_monitor_volume(
    state: State<EngineState>,
    name: String,
    percent: i32,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetMonitorVolume { name, percent },
    )
}
