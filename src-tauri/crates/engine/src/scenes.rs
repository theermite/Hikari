//! Multi-scene support (tranche 1) — create named scenes and switch which one is live.
//! Switching is an instant cut (`obs_set_output_source` on channel 0, the same primitive
//! `fit_source_to_screen`'s caller already relies on) — never a transition (B7's remaining
//! scope). Sources still only ever go into "main" at this tranche (`camera.rs` is
//! untouched) — new scenes start empty until a later tranche lets a source target a
//! chosen scene.

use anyhow::{Context, Result};
use libobs_wrapper::context::ObsContext;

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

/// Makes `name` the live scene on the output channel (channel 0) — an instant cut. The
/// scene that was live before stays fully intact (its sources, filters, everything) as an
/// ordinary inactive scene; switching back to it later is the same call in reverse.
pub fn switch_scene(context: &mut ObsContext, name: &str) -> Result<()> {
    let scene = context
        .get_scene(name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene.set_to_channel(0).context("activation scène")?;
    Ok(())
}
