//! Scene lifecycle (create/switch/delete) and the shared tail every scene-changing command
//! calls to emit the real state — the scene group of `App`'s command handlers.

use hikari_protocol::{EngineMessage, SceneInfo};
use libobs_wrapper::scenes::SceneItemTrait;

use crate::{App, camera, emit, scenes};

impl App {
    /// Creates a new, empty scene (multi-scene, tranche 1). Rejects a blank or already-used
    /// name (`hikari_protocol::validate_scene_name`) — checked against the engine's OWN live
    /// scene list, never a name the caller merely claims doesn't exist yet.
    pub(crate) fn handle_create_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "CreateScene avant l'initialisation".into() });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        if let Err(err) = hikari_protocol::validate_scene_name(&name, &existing) {
            emit(&EngineMessage::Error { message: format!("nom de scène invalide : {err:?}") });
            return;
        }
        if let Err(err) = scenes::create_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.emit_scene_list();
    }

    /// Switches the live scene (multi-scene, tranche 1) — an instant cut, never a
    /// transition (B7's remaining scope). Errors clearly on an unknown name rather than a
    /// silent no-op.
    pub(crate) fn handle_switch_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "SwitchScene avant l'initialisation".into() });
            return;
        };
        if let Err(err) = scenes::switch_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        obs.active_scene = name.clone();
        // The camera sits differently in each scene (its own position and scale), so the
        // cached rectangle belongs to the scene we just left.
        obs.item_rects = None;
        // Applies THIS scene's own filter state (Jay, 2026-07-24) — the "scene automation
        // toggles my filters" flow: switching scenes turns the right filters on/off.
        self.apply_scene_filter_state(&name);
        self.emit_scene_list();
    }

    /// Applies the filter state `scene` wants for EACH camera it shows — called on
    /// `SwitchScene` and right after `AddCamera` when the target scene is already live.
    ///
    /// Per camera since 2026-09-06: two cameras can share a scene with different looks (one
    /// detoured, one framed in a circle), so a single pair of booleans could not describe it.
    pub(crate) fn apply_scene_filter_state(&mut self, scene: &str) {
        let Some(obs) = &mut self.obs else { return };
        let wanted: Vec<(String, (bool, bool))> = obs
            .scene_filter_state
            .iter()
            .filter(|((shown_in, _), _)| shown_in == scene)
            .map(|((_, device_id), state)| (device_id.clone(), *state))
            .collect();
        for (device_id, (background_removal_on, circle_mask_on)) in wanted {
            let Some(opened) = obs.cameras.get(&device_id) else { continue };
            if let Err(err) =
                camera::set_filter_enabled(&opened.filters.background_removal, background_removal_on)
            {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Err(err) = camera::set_filter_enabled(&opened.filters.circle_mask, circle_mask_on)
            {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
        }
    }

    /// Ce que les scènes CONTIENNENT, sous une forme comparable — jamais ce qu'elles
    /// montrent (position, échelle, filtres), qui change à chaque pixel déplacé.
    ///
    /// Sert de filet dans la boucle d'événements : si une commande a changé la composition
    /// sans l'annoncer, la comparaison avant/après le voit et l'annonce à sa place. Lit
    /// l'état du moteur, jamais libobs — appelée à chaque commande, elle doit rester
    /// gratuite.
    pub(crate) fn scene_contents_fingerprint(&self) -> Vec<String> {
        let Some(obs) = self.obs.as_ref() else { return Vec::new() };
        let mut marks: Vec<String> = Vec::new();
        for (scene, list) in &obs.scene_sources {
            for source in list {
                marks.push(format!("s|{scene}|{}", source.name));
            }
        }
        for (scene, device_id) in obs.camera_items.keys() {
            marks.push(format!("c|{scene}|{device_id}"));
        }
        for (scene, name) in &obs.locked {
            marks.push(format!("v|{scene}|{name}"));
        }
        // Une table de hachage ne rend pas ses clés dans le même ordre d'un appel à
        // l'autre : sans ce tri, deux états IDENTIQUES se compareraient différents et le
        // filet annoncerait à chaque commande.
        marks.sort();
        marks
    }

    /// Emits the real scene list + active scene straight from libobs (never a shadowed
    /// count) — shared tail of every command that can change what the scenes hold.
    ///
    /// Each entry carries what THAT scene holds (tranche 3), read from the engine's own
    /// per-scene maps: the panel can then show the whole list at once, instead of forcing a
    /// live scene switch just to discover what a scene contains.
    pub(crate) fn emit_scene_list(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        let names = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        let scenes = names
            .into_iter()
            .map(|name| {
                let has_camera = obs.camera_items.keys().any(|(shown_in, _)| shown_in == &name);
                let mut sources: Vec<hikari_protocol::SceneSourceInfo> = Vec::new();
                if let Some(added) = obs.scene_sources.get(&name) {
                    sources.extend(added.iter().map(|source| {
                        // Placement lu depuis libobs, jamais mémorisé de notre côté : une
                        // copie qui dérive ferait sauvegarder une position fausse.
                        let position = source.item.get_source_position().ok();
                        let scale = source.item.get_source_scale().ok();
                        hikari_protocol::SceneSourceInfo {
                            name: source.name.clone(),
                            kind: source.kind.clone(),
                            source_kind: source.source_kind,
                            target_id: source.target_id.clone(),
                            x: position.as_ref().map_or(0, |p| *p.x() as i32),
                            y: position.as_ref().map_or(0, |p| *p.y() as i32),
                            scale_percent: scale
                                .as_ref()
                                .map_or(100, |s| (s.x() * 100.0).round() as i32),
                            locked: obs
                                .locked
                                .contains(&(name.clone(), source.name.clone())),
                            // Une capture n'a pas de filtre caméra : la case existe pour
                            // toutes les sources, elle ne vaut quelque chose que pour une caméra.
                            background_removal: false,
                            circle_mask: false,
                        }
                    }));
                }
                // Une entrée par caméra posée dans cette scène. Même traitement que les
                // autres sources : placement lu depuis libobs, et l'appareil retenu comme
                // cible — c'est ce qui rend chaque caméra rejouable au lancement suivant.
                let mut shown: Vec<(&String, _)> = obs
                    .camera_items
                    .iter()
                    .filter(|((shown_in, _), _)| shown_in == &name)
                    .map(|((_, device_id), item)| (device_id, item))
                    .collect();
                // Ordre stable : sans tri, une table de hachage renvoie les caméras dans un
                // ordre différent à chaque lancement, et la liste sauterait sous les yeux.
                shown.sort_by_key(|(device_id, _)| (*device_id).clone());
                for (device_id, item) in shown {
                    let camera_name = obs
                        .cameras
                        .get(device_id)
                        .map(|opened| opened.name.clone())
                        .unwrap_or_else(|| camera::CAMERA_SOURCE_NAME.to_string());
                    let (background_removal, circle_mask) = obs
                        .scene_filter_state
                        .get(&(name.clone(), device_id.clone()))
                        .copied()
                        .unwrap_or((false, false));
                    let position = item.get_source_position().ok();
                    let scale = item.get_source_scale().ok();
                    sources.push(hikari_protocol::SceneSourceInfo {
                        kind: hikari_protocol::CAMERA_KIND.to_string(),
                        source_kind: hikari_protocol::SourceKind::Camera,
                        target_id: device_id.clone(),
                        x: position.as_ref().map_or(0, |p| *p.x() as i32),
                        y: position.as_ref().map_or(0, |p| *p.y() as i32),
                        scale_percent: scale
                            .as_ref()
                            .map_or(100, |s| (s.x() * 100.0).round() as i32),
                        locked: obs.locked.contains(&(name.clone(), camera_name.clone())),
                        background_removal,
                        circle_mask,
                        name: camera_name,
                    });
                }
                SceneInfo { has_camera, sources, name }
            })
            .collect();
        emit(&EngineMessage::SceneList { scenes, active: obs.active_scene.clone() });
    }

    /// Deletes a scene and everything scene-local it carried (multi-scene, tranche 3).
    ///
    /// Order matters and is the whole point of this function: re-validate, then leave the
    /// scene if it is live (the output channel must never end up pointing at a scene that
    /// is about to be dropped), then release its camera item and filter preference, and
    /// only then delete. The shared physical webcam is untouched — other scenes keep
    /// showing it, exactly like `handle_remove_camera`.
    pub(crate) fn handle_delete_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "DeleteScene avant l'initialisation".into() });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        if let Err(err) = hikari_protocol::validate_scene_deletion(&name, &existing) {
            let message = match err {
                hikari_protocol::SceneDeleteError::Unknown => {
                    format!("scène introuvable : {name}")
                }
                hikari_protocol::SceneDeleteError::LastScene => {
                    "impossible de supprimer la dernière scène".to_string()
                }
            };
            emit(&EngineMessage::Error { message });
            return;
        }

        // Leave the scene before dropping it: a fallback is guaranteed to exist here,
        // because `validate_scene_deletion` already refused the last-scene case.
        if obs.active_scene == name {
            let Some(fallback) = existing.iter().find(|other| **other != name).cloned() else {
                emit(&EngineMessage::Error { message: "aucune scène de repli".into() });
                return;
            };
            self.handle_switch_scene(fallback);
            let Some(obs_again) = &mut self.obs else { return };
            if obs_again.active_scene == name {
                // The switch failed and already reported why; deleting now would leave the
                // output channel on a dropped scene.
                return;
            }
        }

        let Some(obs) = &mut self.obs else { return };
        obs.camera_items.retain(|(shown_in, _), _| shown_in != &name);
        obs.scene_filter_state.retain(|(shown_in, _), _| shown_in != &name);
        obs.item_rects = None;
        // Une caméra que plus aucune scène ne montre garde l'appareil ouvert : témoin
        // allumé, et indisponible ailleurs. Elle part avec la dernière scène qui l'affichait.
        self.release_unused_cameras();
        let Some(obs) = &mut self.obs else { return };
        // Les captures de cette scène partent avec elle : garder leurs poignées maintiendrait
        // la scène en vie et la suppression ne ferait rien (même piège que l'élément caméra).
        obs.scene_sources.remove(&name);
        if let Err(err) = scenes::delete_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.emit_scene_list();
    }
}
