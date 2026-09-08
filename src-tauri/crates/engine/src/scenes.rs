//! Multi-scene support — create named scenes and switch which one is live. Switching goes
//! THROUGH the app's one permanent fade transition (`transitions.rs`, B7) — no scene ever
//! touches the output channel itself any more, `duration_ms == 0` being the engine's own
//! instant-cut path rather than a zero-length animation (a real libobs quirk: a
//! zero-duration `obs_transition_start` can leave the last frame of the OUTGOING scene on
//! screen instead of cutting to the new one).

use anyhow::{Context, Result};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::sources::ObsSourceRef;

use crate::transitions;

/// Every scene name the engine currently knows about — read live from the context's own
/// list (never a shadow copy the engine could let drift), same principle as
/// `camera::nudge_camera` reading position/scale straight from libobs.
pub fn list_scene_names(context: &mut ObsContext) -> Result<Vec<String>> {
    let guard = context
        .scenes_mut()
        .read()
        .map_err(|_| anyhow::anyhow!("verrou scènes corrompu"))?;
    Ok(guard.iter().map(|scene| scene.name().to_string()).collect())
}

/// Creates a new, empty scene named `name`. Left off every output channel (not live) until
/// `switch_scene` activates it — matches how "main" itself starts live only because
/// `try_init` explicitly puts it on channel 0.
pub fn create_scene(context: &mut ObsContext, name: &str) -> Result<()> {
    context.scene(name.to_string(), None).context("création scène")?;
    Ok(())
}

/// Deletes the scene named `name` by dropping the wrapper's only handle on it — the crate's
/// own drop guard then releases the underlying libobs scene.
///
/// WHY it works this way: `libobs-wrapper` 9.0.4 exposes no `remove_scene`; scenes live in
/// a `RwLock<Vec<ObsSceneRef>>` the context hands out (`scenes_mut`), and dropping the last
/// reference is exactly what the crate's `scene_drop_guards` waits for. Verified by reading
/// the crate source (2026-08-04), never assumed.
///
/// The caller MUST have released everything scene-local first (its camera scene item above
/// all): a live `ObsSceneItemRef` keeps the scene alive, so the delete would silently do
/// nothing and the panel would show a scene libobs still renders.
pub fn delete_scene(context: &mut ObsContext, name: &str) -> Result<()> {
    let mut guard = context
        .scenes_mut()
        .write()
        .map_err(|_| anyhow::anyhow!("verrou scènes corrompu"))?;
    let before = guard.len();
    guard.retain(|scene| scene.name() != name);
    if guard.len() == before {
        anyhow::bail!("scène introuvable : {name}");
    }
    Ok(())
}

/// Makes `name` the live scene, fading through the app's one transition over
/// `duration_ms` (`0` = instant cut). The scene that was live before stays fully intact
/// (its sources, filters, everything) as an ordinary inactive scene; switching back to it
/// later is the same call in reverse. `duration_ms` MUST already be
/// `hikari_protocol::clamp_transition_duration_ms`-clamped — see `transitions::start_transition`.
pub fn switch_scene(
    context: &mut ObsContext,
    transition: &ObsSourceRef,
    name: &str,
    duration_ms: u32,
) -> Result<()> {
    let scene = context
        .get_scene(name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    let dest = scene.get_scene_source_ptr().context("pointeur scène")?;
    if duration_ms == 0 {
        transitions::set_transition_immediate(transition, dest).context("coupe sèche")?;
    } else {
        transitions::start_transition(transition, dest, duration_ms).context("fondu")?;
    }
    Ok(())
}
