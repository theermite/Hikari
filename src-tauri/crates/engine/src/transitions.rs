//! The scene-switch fade (B7) — a permanent `fade_transition` source held on the output
//! channel, swapped between scenes instead of the raw scene-on-channel cut `scenes.rs`
//! used before. `libobs-wrapper` 9.0.4 wraps no transition API at all (checked in its
//! source, 2026-09-08: only the source-callback name strings exist) — the source itself is
//! created through the same `define_object_manager!` macro `camera.rs` already uses for
//! `dshow_input`, so its lifecycle stays fully managed (no manual create/release). Only
//! `obs_transition_start`/`obs_transition_set` are raw, dispatched on the OBS thread the
//! same way `filters::set_enabled` already does.

use anyhow::{Context, Result};
use libobs_simple::define_object_manager;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::sources::{ObsSourceBuilder, ObsSourceRef};
use libobs_wrapper::unsafe_send::Sendable;
// See `camera.rs`'s own comment: the macro expands a literal `libobs::obs_source` path, so
// this local alias must resolve to the exact `sys` crate `libobs-wrapper` links against.
use libobs_wrapper::sys as libobs;

/// A scene's own source handle (`ObsSceneRef::get_scene_source_ptr`) — a scene, not a
/// generic source, is always what a switch fades TO, so both transition functions below
/// take this rather than an `ObsSourceRef` a caller doesn't have for a scene.
pub type SceneSourcePtr = Sendable<*mut libobs::obs_source>;

define_object_manager!(
    #[derive(Debug)]
    /// The stock cross-fade transition libobs itself registers as `fade_transition` — the
    /// same one OBS Studio's own "Fade" option uses.
    struct FadeTransitionSource("fade_transition", *mut libobs::obs_source) for ObsSourceRef {}
);

// `libobs-simple`'s own `impl_default_builder!` helper is crate-private — this is its exact
// body, transcribed from `camera.rs` (verified against `libobs-simple` 8.0.1 source,
// `src/sources/macro_helper.rs`), not invented.
impl ObsSourceBuilder for FadeTransitionSourceBuilder {
    type T = ObsSourceRef;

    fn build(self) -> Result<Self::T, libobs_wrapper::utils::ObsError> {
        use libobs_wrapper::data::ObsObjectBuilder;
        let runtime = self.runtime.clone();
        ObsSourceRef::new_from_info(self.object_build()?, runtime)
    }
}

/// The libobs `obs_transition_mode` value meaning "cancel whatever is mid-flight and start
/// this one now" — the one mode a single fixed transition source ever needs, since Hikari
/// never queues a second switch mid-fade.
const OBS_TRANSITION_MODE_AUTO: libobs::obs_transition_mode = 0;

/// Creates the one fade transition Hikari keeps alive for the app's whole life — never
/// rebuilt per switch, matching how `bootstrap.rs` already keeps a single "main" scene
/// alive rather than recreating it.
pub fn create_fade_transition(context: &ObsContext) -> Result<ObsSourceRef> {
    context
        .source_builder::<FadeTransitionSourceBuilder, _>("hikari-transition")
        .context("préparation transition")?
        .build()
        .context("création transition fondu")
}

/// Puts `transition` on the output channel permanently (B7) — every scene switch afterwards
/// goes THROUGH it (`start_transition`/`set_transition_immediate`) instead of a scene ever
/// touching the channel directly, the one rule that keeps `scenes.rs`'s old
/// `scene.set_to_channel(0)` from silently reappearing beside it.
pub fn put_transition_on_output(transition: &ObsSourceRef) -> Result<()> {
    let runtime = transition.runtime().clone();
    let ptr = transition.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: `ptr` comes from a live `SmartPointerSendable` (`transition` outlives
            // this call, held by `ObsInner` for the app's life) and we are on the OBS
            // thread — the same argument `filters::set_enabled` already makes.
            libobs::obs_set_output_source(0, ptr.get_ptr());
        })
        .context("pose de la transition sur le canal de sortie")
}

/// Sets `transition`'s picture to `dest` with NO animation (B7) — the very first scene at
/// boot, where there is no "from" state to fade out of. Raw because `libobs-wrapper` 9.0.4
/// wraps neither this nor `obs_transition_start` (checked in its source, 2026-09-08).
pub fn set_transition_immediate(transition: &ObsSourceRef, dest: SceneSourcePtr) -> Result<()> {
    let runtime = transition.runtime().clone();
    let transition_ptr = transition.as_ptr();
    runtime
        .run_with_obs_result(move || {
            // Forces the closure to capture the WHOLE `Sendable` (which is `Send` on
            // purpose) rather than just its `.0` field (a bare `*mut obs_source`, NOT
            // `Send`) — Rust 2021's disjoint capture narrows to the smallest path used,
            // and `dest.0` alone below would otherwise be captured directly. Same trick
            // the wrapper's own `run_with_obs!` macro applies to every variable it takes.
            let dest = dest;
            unsafe {
                // Safety: `transition_ptr` comes from a live `SmartPointerSendable`
                // (`transition` lives in `ObsInner`), `dest` comes from the caller's own
                // live `ObsSceneRef::get_scene_source_ptr()` (same contract `set_to_channel`
                // already relies on), and we are on the OBS thread.
                libobs::obs_transition_set(transition_ptr.get_ptr(), dest.0);
            }
        })
        .context("pose immédiate de la scène de départ")
}

/// Starts the fade FROM whatever `transition` currently shows TO `dest`, over
/// `duration_ms` (B7). `duration_ms` MUST already be `clamp_transition_duration_ms`-clamped
/// — this function trusts its caller rather than re-clamping, since both callers
/// (`scenes::switch_scene`) already go through the shared validation, and duplicating the
/// clamp here would let the two silently drift to different ceilings.
pub fn start_transition(
    transition: &ObsSourceRef,
    dest: SceneSourcePtr,
    duration_ms: u32,
) -> Result<()> {
    let runtime = transition.runtime().clone();
    let transition_ptr = transition.as_ptr();
    runtime
        .run_with_obs_result(move || {
            // Same whole-value-capture trick as `set_transition_immediate` — see its comment.
            let dest = dest;
            unsafe {
                // Safety: same pointers, same lifetimes, same thread as `set_transition_immediate`.
                libobs::obs_transition_start(
                    transition_ptr.get_ptr(),
                    OBS_TRANSITION_MODE_AUTO,
                    duration_ms,
                    dest.0,
                );
            }
        })
        .context("démarrage de la transition")
}
