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
    context
        .scene(name.to_string(), None)
        .context("création scène")?;
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

/// Le nom RÉSERVÉ de la scène de recouvrement permanent (F-033/F-034, dérisqué et confirmé
/// à l'écran le 2026-09-15 : un média posé ici s'affiche sur TOUTE scène active). Créée
/// automatiquement par le moteur, jamais par l'utilisateur — exclue de la liste normale des
/// scènes côté app (même nom, en dur, côté TypeScript : `OVERLAY_SCENE_NAME`).
pub const OVERLAY_SCENE_NAME: &str = "DSK";

/// Le canal de sortie de la scène de recouvrement. Hors de la plage du mixeur audio
/// (`audio::FIRST_AUDIO_CHANNEL` + `MAX_AUDIO_SOURCES`, soit 1 à 8) : un canal ne porte
/// qu'UNE source, et le premier micro attaché chassait la scène DSK du canal 1 — plus aucun
/// média ne s'affichait. libobs en offre 64 et les dessine par ordre croissant : 32 reste
/// au-dessus de la scène active (canal 0) avec une grande marge de chaque côté.
pub const OVERLAY_CHANNEL: u32 = 32;

/// Pose `scene` sur le canal de sortie 1, composé PAR-DESSUS le canal 0 (la transition,
/// donc la scène active) par libobs lui-même, en PERMANENCE. Jamais appelé avant que
/// `self.obs` existe : la tentative du 2026-09-14 a bloqué `try_init` en touchant un canal
/// avant que la sortie vidéo existe (dérisqué et confirmé le 2026-09-15).
pub fn set_overlay_channel(context: &mut ObsContext, name: &str) -> Result<()> {
    let scene = context
        .get_scene(name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene
        .set_to_channel(OVERLAY_CHANNEL)
        .context("pose de la scène sur le canal de recouvrement")
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

#[cfg(test)]
mod tests {
    use super::OVERLAY_CHANNEL;
    use crate::audio::{FIRST_AUDIO_CHANNEL, MAX_AUDIO_SOURCES};

    #[test]
    fn should_keep_the_overlay_channel_out_of_the_audio_mixer_range() {
        // Un canal libobs ne porte qu'UNE source : attacher un micro sur le canal de la
        // scène de recouvrement la chasse, et plus aucun média ne s'affiche (vécu
        // 2026-10-13 — le mixeur prenait les canaux 1 à 8, la scène DSK le canal 1).
        let audio = FIRST_AUDIO_CHANNEL..FIRST_AUDIO_CHANNEL + MAX_AUDIO_SOURCES;
        assert!(
            !audio.contains(&OVERLAY_CHANNEL),
            "canal {OVERLAY_CHANNEL} déjà pris par le mixeur audio {audio:?}"
        );
    }

    #[test]
    fn should_put_the_overlay_above_the_live_scene_channel() {
        // Le canal 0 porte la transition (la scène active) ; libobs dessine les canaux par
        // ordre croissant, donc le recouvrement doit être au-dessus.
        assert!(OVERLAY_CHANNEL > 0);
    }
}
