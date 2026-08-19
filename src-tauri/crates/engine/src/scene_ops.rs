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

    /// Applies `scene`'s own desired filter state to the shared camera filters (a no-op if
    /// no camera exists yet, or `scene` has never had one added) — called on `SwitchScene`
    /// and right after `AddCamera` if the target scene is already the active one.
    pub(crate) fn apply_scene_filter_state(&mut self, scene: &str) {
        let Some(obs) = &mut self.obs else { return };
        let Some(filters) = &obs.camera_filters else { return };
        let Some(&(background_removal_on, circle_mask_on)) = obs.scene_filter_state.get(scene) else { return };
        if let Err(err) = camera::set_filter_enabled(&filters.background_removal, background_removal_on) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        if let Err(err) = camera::set_filter_enabled(&filters.circle_mask, circle_mask_on) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
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
                let (background_removal, circle_mask) =
                    obs.scene_filter_state.get(&name).copied().unwrap_or((false, false));
                let has_camera = obs.camera_items.contains_key(&name);
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
                        }
                    }));
                }
                if let Some(item) = obs.camera_items.get(&name) {
                    // Même traitement que les autres sources : placement lu depuis libobs, et
                    // l'appareil retenu comme cible — c'est ce qui rend la caméra rejouable.
                    let position = item.get_source_position().ok();
                    let scale = item.get_source_scale().ok();
                    sources.push(hikari_protocol::SceneSourceInfo {
                        name: camera::CAMERA_SOURCE_NAME.to_string(),
                        kind: hikari_protocol::CAMERA_KIND.to_string(),
                        source_kind: hikari_protocol::SourceKind::Camera,
                        target_id: obs.camera_device_id.clone().unwrap_or_default(),
                        x: position.as_ref().map_or(0, |p| *p.x() as i32),
                        y: position.as_ref().map_or(0, |p| *p.y() as i32),
                        scale_percent: scale
                            .as_ref()
                            .map_or(100, |s| (s.x() * 100.0).round() as i32),
                        locked: obs.locked.contains(&(
                            name.clone(),
                            camera::CAMERA_SOURCE_NAME.to_string(),
                        )),
                    });
                }
                SceneInfo { has_camera, background_removal, circle_mask, sources, name }
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
        obs.camera_items.remove(&name);
        obs.scene_filter_state.remove(&name);
        obs.item_rects = None;
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
