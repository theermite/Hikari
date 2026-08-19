//! What one scene holds, and the two name-validation rules (empty, duplicate) shared by
//! both sides before a `CreateScene`/`DeleteScene` ever reaches the engine.

use serde::{Deserialize, Serialize};

use crate::sources::SceneSourceInfo;

/// What one scene currently holds, as the engine really sees it (multi-scene, tranche 3).
///
/// WHY per scene rather than "the active one": the Scenes panel shows the whole list at
/// once, so it must say what EACH scene carries without the user having to switch to it
/// just to find out — switching is a live cut on the output channel, never a free peek.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SceneInfo {
    pub name: String,
    /// Whether the ONE physical webcam is shown in this scene (`AddCamera`/`RemoveCamera`).
    pub has_camera: bool,
    /// This scene's OWN desired state for the NVIDIA background-removal filter — the value
    /// applied to the shared filter whenever this scene becomes live, not the filter's
    /// current global state (which belongs to whichever scene is live right now).
    pub background_removal: bool,
    /// This scene's OWN desired state for the circular mask filter. Same contract.
    pub circle_mask: bool,
    /// Everything this scene holds, in the order it was added — so the panel shows a
    /// scene's contents without switching to it (switching is a live cut, never a peek).
    pub sources: Vec<SceneSourceInfo>,
}

impl SceneInfo {
    /// A scene that holds no camera and no filter preference — the shape every scene has
    /// the moment `CreateScene` makes it. Pure, so tests and the engine agree on "empty"
    /// instead of each spelling out four fields.
    pub fn empty(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            has_camera: false,
            background_removal: false,
            circle_mask: false,
            sources: Vec::new(),
        }
    }
}

/// Why a scene could not be deleted (multi-scene, tranche 3).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SceneDeleteError {
    /// No scene by that name exists — a stale panel, or a name that was already deleted.
    Unknown,
    /// It is the only scene left. Deleting it would leave the output channel empty, so
    /// the preview and the live stream would go black with nothing explaining why.
    LastScene,
}

/// Validates a deletion request against the scenes that exist. Pure and total — no libobs —
/// so both sides (panel before sending, engine before obeying) enforce the same two rules
/// from one implementation, same split as [`validate_scene_name`].
pub fn validate_scene_deletion(name: &str, existing: &[String]) -> Result<(), SceneDeleteError> {
    if !existing.iter().any(|s| s == name) {
        return Err(SceneDeleteError::Unknown);
    }
    if existing.len() <= 1 {
        return Err(SceneDeleteError::LastScene);
    }
    Ok(())
}

/// Why a candidate scene name was rejected before ever reaching the engine.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SceneNameError {
    /// An empty (or whitespace-only) name — not a name a person can recognize in a list.
    Empty,
    /// A scene with this exact name already exists.
    Duplicate,
}

/// Validates a candidate scene name against the scenes that already exist — pure and
/// total, so "no duplicate, no blank name" is proven by unit tests without a real engine
/// process (same split as `validate_targets`, B3).
pub fn validate_scene_name(name: &str, existing: &[String]) -> Result<(), SceneNameError> {
    if name.trim().is_empty() {
        return Err(SceneNameError::Empty);
    }
    if existing.iter().any(|s| s == name) {
        return Err(SceneNameError::Duplicate);
    }
    Ok(())
}
