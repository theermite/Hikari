//! Commandes de scenes, de sources et de camera — la couche mince entre l'interface et le
//! moteur.
//!
//! Extraites de `engine_lifecycle.rs` le 2026-09-07 : ce fichier depassait le plafond de
//! 500 lignes, et le melange « cycle de vie du processus » + « catalogue de commandes »
//! obligeait a lire l'un pour trouver l'autre. Aucun changement de comportement.

use std::io::Write;

use tauri::State;

use hikari_protocol::{to_line, ControllerCommand};

use crate::engine_lifecycle::{send_command, EngineState};

/// Adds a webcam source to the live scene (B-cam) by sending `AddCamera` to the already-
/// running engine. Requires the engine to be running (Aperçu panel open) — a clear error
/// beats a silent no-op if it isn't, since there's no queue to "add it once started".
#[tauri::command]
pub(crate) fn add_camera_source(
    state: State<EngineState>,
    device_id: String,
    scene: String,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::AddCamera { device_id, scene })
        .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi AddCamera au moteur: {err}"))
}

/// Retire la caméra `device_id` de `scene` — les autres caméras de la scène restent, et
/// les autres scènes gardent celle-ci. Sans effet si cette caméra n'y est pas.
#[tauri::command]
pub(crate) fn remove_camera_source(
    state: State<EngineState>,
    device_id: String,
    scene: String,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::RemoveCamera { device_id, scene })
        .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi RemoveCamera au moteur: {err}"))
}

/// Sets whether the real NVIDIA background-removal filter is applied to the webcam
/// (B-cam, F-036). Toggling REBUILDS the camera source (see
/// `ControllerCommand::SetBackgroundRemoval`'s own doc for why — no public filter-removal
/// API exists) — a brief camera reinit blip, disclosed to Jay. Requires the engine
/// running AND a camera already added.
#[tauri::command]
pub(crate) fn set_background_removal(
    state: State<EngineState>,
    device_id: String,
    scene: String,
    enabled: bool,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::SetBackgroundRemoval {
        device_id,
        scene,
        enabled,
    })
    .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi au moteur: {err}"))
}

/// Sets whether a circular alpha mask is applied to the webcam (B-cam, F-036). Same
/// rebuild-based toggle and requirements as `set_background_removal`.
#[tauri::command]
pub(crate) fn set_circle_mask(
    state: State<EngineState>,
    device_id: String,
    scene: String,
    enabled: bool,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::SetCircleMask {
        device_id,
        scene,
        enabled,
    })
    .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi au moteur: {err}"))
}

/// Moves the webcam by `(dx, dy)` scene pixels (B7 — arrow buttons, never a raw drag: the
/// dockview drag already broke silently in this WebView2 build, session 2026-07-23).
/// Requires the engine running AND a camera already added.
#[tauri::command]
pub(crate) fn nudge_camera(
    state: State<EngineState>,
    device_id: String,
    scene: String,
    dx: i32,
    dy: i32,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::NudgeCamera {
        device_id,
        scene,
        dx,
        dy,
    })
    .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi NudgeCamera au moteur: {err}"))
}

/// Grows or shrinks the webcam by one fixed step (B7). Same requirements as `nudge_camera`.
#[tauri::command]
pub(crate) fn scale_camera(
    state: State<EngineState>,
    device_id: String,
    scene: String,
    grow: bool,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::ScaleCamera {
        device_id,
        scene,
        grow,
    })
    .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi ScaleCamera au moteur: {err}"))
}

/// Creates a new, empty scene (multi-scene, tranche 1). Requires the engine running.
#[tauri::command]
pub(crate) fn create_scene(state: State<EngineState>, name: String) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::CreateScene { name }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi CreateScene au moteur: {err}"))
}

/// Switches the live scene through a fondu (B7). `duration_ms` should come from
/// `hikari_protocol::TRANSITION_DURATIONS_MS` — the engine re-clamps it regardless
/// (`clamp_transition_duration_ms`), `0` being an instant cut. Requires the engine running.
#[tauri::command]
pub(crate) fn switch_scene(
    state: State<EngineState>,
    name: String,
    duration_ms: u32,
) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::SwitchScene { name, duration_ms })
        .map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi SwitchScene au moteur: {err}"))
}

/// Deletes a scene and everything scene-local it carried (multi-scene, tranche 3). The
/// engine re-checks the two rules (the scene exists, it is not the last one) and answers an
/// `Error` message rather than obeying — this command only carries the intent.
#[tauri::command]
pub(crate) fn delete_scene(state: State<EngineState>, name: String) -> Result<(), String> {
    let mut guard = state
        .0
        .lock()
        .map_err(|_| "verrou moteur corrompu".to_string())?;
    let Some(handle) = guard.handle.as_mut() else {
        return Err("le moteur n'est pas démarré — ouvre le panneau Aperçu d'abord".to_string());
    };
    let line = to_line(&ControllerCommand::DeleteScene { name }).map_err(|err| err.to_string())?;
    writeln!(handle.stdin, "{line}").map_err(|err| format!("envoi DeleteScene au moteur: {err}"))
}

/// Asks the engine for everything the machine can capture right now (brique Sources).
#[tauri::command]
pub(crate) fn list_capture_targets(state: State<EngineState>) -> Result<(), String> {
    send_command(&state, ControllerCommand::ListCaptureTargets)
}

/// Adds a game, window or screen capture into a scene (brique Sources).
#[tauri::command]
pub(crate) fn add_capture_source(
    state: State<EngineState>,
    scene: String,
    kind: hikari_protocol::SourceKind,
    target_id: String,
    name: String,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::AddCaptureSource {
            scene,
            kind,
            target_id,
            name,
        },
    )
}

/// Removes a capture from one scene (brique Sources).
#[tauri::command]
pub(crate) fn remove_source(
    state: State<EngineState>,
    scene: String,
    name: String,
) -> Result<(), String> {
    send_command(&state, ControllerCommand::RemoveSource { scene, name })
}

/// Places a source exactly (brique Persistance) — ce qui permet de rejouer une session
/// sauvegardée au lancement suivant.
#[tauri::command]
pub(crate) fn set_source_transform(
    state: State<EngineState>,
    scene: String,
    name: String,
    x: i32,
    y: i32,
    scale_percent: i32,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetSourceTransform {
            scene,
            name,
            x,
            y,
            scale_percent,
        },
    )
}

/// Locks or unlocks a source against the mouse, in one scene (brique Sources). A locked
/// source stays visible, reorderable and removable — the lock guards against the accidental
/// gesture, never against the deliberate decision.
#[tauri::command]
pub(crate) fn set_source_locked(
    state: State<EngineState>,
    scene: String,
    name: String,
    locked: bool,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetSourceLocked {
            scene,
            name,
            locked,
        },
    )
}

/// Relance l'appareil derrière une caméra, sans la retirer d'aucune scène.
///
/// Elle garde son cadrage, ses filtres et sa place dans la pile — c'est ce qui
/// distingue ce geste du retrait-remise que Jay a dû faire en plein direct.
#[tauri::command]
pub(crate) fn restart_camera(state: State<EngineState>, device_id: String) -> Result<(), String> {
    send_command(&state, ControllerCommand::RestartCamera { device_id })
}

/// Montre ou cache une source dans une scène, sans la retirer (maquette, l'œil).
///
/// Distinct du retrait : une source cachée garde son cadrage, ses filtres et sa place dans
/// la pile. C'est le geste du direct — masquer le temps d'une manipulation, puis remontrer.
#[tauri::command]
pub(crate) fn set_source_visible(
    state: State<EngineState>,
    scene: String,
    name: String,
    visible: bool,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetSourceVisible {
            scene,
            name,
            visible,
        },
    )
}

/// Moves a source one step in front of, or behind, the others in its scene (brique Sources).
#[tauri::command]
pub(crate) fn reorder_source(
    state: State<EngineState>,
    scene: String,
    name: String,
    direction: hikari_protocol::SourceOrder,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::ReorderSource {
            scene,
            name,
            direction,
        },
    )
}

/// Change l'apparence d'une source texte : police, taille, couleur, contour, alignement.
///
/// Ne dit RIEN du texte lui-même — le moteur fusionne les réglages nommés avec ceux qui ne
/// le sont pas, donc le contenu reste ce qu'il est.
#[tauri::command]
pub(crate) fn set_text_settings(
    state: State<EngineState>,
    scene: String,
    name: String,
    settings: hikari_protocol::TextSettings,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetTextSettings {
            scene,
            name,
            settings,
        },
    )
}

/// Change le contenu d'une source texte deja posee — jamais sa police ni sa couleur.
#[tauri::command]
pub(crate) fn set_text_content(
    state: State<EngineState>,
    scene: String,
    name: String,
    text: String,
) -> Result<(), String> {
    send_command(
        &state,
        ControllerCommand::SetTextContent { scene, name, text },
    )
}

/// Redemande l'inventaire actuel des scenes, sans rien changer — utilise par une fenetre
/// de reglages qui vient de s'ouvrir et n'a pas assiste au dernier changement.
#[tauri::command]
pub(crate) fn request_scene_list(state: State<EngineState>) -> Result<(), String> {
    send_command(&state, ControllerCommand::RequestSceneList)
}
