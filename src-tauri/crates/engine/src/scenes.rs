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
