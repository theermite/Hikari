//! Filter switching — the one-line operation every filtered source needs, video or audio.
//!
//! Lives on its own rather than inside `camera.rs` (where it started): a reader finding
//! `camera::set_filter_enabled` called on a microphone would rightly pause. Nothing here is
//! camera-specific — a libobs filter IS an `obs_source_t` internally, whatever it filters.

use anyhow::{Context, Result};
// `runtime()` and `as_ptr()` reach a filter through this trait, not through the struct.
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::sources::ObsFilterRef;
use libobs_wrapper::sys as libobs;

/// Toggles `filter` on or off in place — the real per-filter switch OBS itself exposes (the
/// "eye" icon), `obs_source_set_enabled` on the filter's own source handle.
///
/// `libobs-wrapper` 9.0.4 does not wrap it (checked in its source), so this dispatches the
/// raw call on the OBS thread, the same thread-safety contract every safe wrapper method
/// uses internally. Toggling beats rebuilding: a rebuild interrupts the signal — the visible
/// blip the camera filters had on 2026-07-23, and an audible gap on a microphone.
pub fn set_enabled(filter: &ObsFilterRef, enabled: bool) -> Result<()> {
    let runtime = filter.runtime().clone();
    let ptr = filter.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: `ptr` comes from a live `SmartPointerSendable` (the filter is still
            // attached and we hold a reference), and we are on the OBS thread — the same
            // argument the wrapper's own `apply_filter` makes.
            libobs::obs_source_set_enabled(ptr.get_ptr(), enabled);
        })
        .context("activation/désactivation filtre")
}
