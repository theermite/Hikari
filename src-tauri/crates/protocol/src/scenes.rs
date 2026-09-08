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
    /// Whether this scene shows AT LEAST ONE camera (`AddCamera`/`RemoveCamera`).
    ///
    /// Which cameras, and how each is framed and filtered, is in `sources` — one entry per
    /// camera since 2026-09-06. This stays as the one-glance answer the scene list needs.
    pub has_camera: bool,
    /// Everything this scene holds, in the order it was added — so the panel shows a
    /// scene's contents without switching to it (switching is a live cut, never a peek).
    pub sources: Vec<SceneSourceInfo>,
}

impl SceneInfo {
    /// A scene that holds nothing — the shape every scene has the moment `CreateScene`
    /// makes it. Pure, so tests and the engine agree on "empty" instead of each spelling
    /// out the fields.
    pub fn empty(name: impl Into<String>) -> Self {
        Self { name: name.into(), has_camera: false, sources: Vec::new() }
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

/// The durations the panel offers (B7, transitions) — coupe sèche, then three fades. A
/// closed list rather than a free field: an unbounded slider lets a stray value hang a
/// switch on a live stream, exactly the class of mistake `clamp_transition_duration_ms`
/// exists to catch even if a future caller bypasses the panel.
pub const TRANSITION_DURATIONS_MS: [u32; 4] = [0, 300, 500, 1000];

/// Clamps a requested transition duration to a safe ceiling (B7). Pure and total, so both
/// the panel (before sending) and the engine (before obeying) refuse the same runaway
/// value — a duration meant in milliseconds but typed in seconds, or a corrupted wire
/// value, would otherwise hang the output on the last frame of the outgoing scene for that
/// long, live, with no way to cut it short.
///
/// `0` always means an instant cut (never "no transition specified"): it is the first
/// entry of [`TRANSITION_DURATIONS_MS`] and the engine's own no-fade path.
pub fn clamp_transition_duration_ms(requested_ms: u32) -> u32 {
    const MAX_TRANSITION_MS: u32 = 2_000;
    requested_ms.min(MAX_TRANSITION_MS)
}

#[cfg(test)]
mod transition_duration_tests {
    use super::*;

    #[test]
    fn should_pass_through_when_within_ceiling() {
        assert_eq!(clamp_transition_duration_ms(0), 0);
        assert_eq!(clamp_transition_duration_ms(500), 500);
        assert_eq!(clamp_transition_duration_ms(2_000), 2_000);
    }

    #[test]
    fn should_clamp_when_above_ceiling() {
        assert_eq!(clamp_transition_duration_ms(60_000), 2_000);
        assert_eq!(clamp_transition_duration_ms(u32::MAX), 2_000);
    }
}
