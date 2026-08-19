//! The physical webcam: adding it to a scene, its two filters, removing it, and the
//! keyboard-step nudge/scale commands (B7) — the camera group of `App`'s command handlers.

use hikari_protocol::{EngineMessage, SourceInfo};

use crate::{App, CameraFilters, camera, emit};

impl App {
    /// Puts the ONE physical webcam into `scene` (B-cam, multi-scene tranche 2) — builds
    /// the source and its two filters (disabled) only the FIRST time any scene requests a
    /// camera (Jay, 2026-07-24: "la caméra est unique"); every later scene reuses that same
    /// source, added as its own scene item (`camera::add_existing_camera_to_scene`).
    pub(crate) fn handle_add_camera(&mut self, device_id: String, scene: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "AddCamera avant l'initialisation".into() });
            return;
        };
        if obs.camera_source.is_none() {
            let source = match camera::build_camera_source(&mut obs.context, &device_id) {
                Ok(source) => source,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            let background_removal = match camera::create_background_removal_filter(&source) {
                Ok(filter) => filter,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            let circle_mask = match camera::create_circle_mask_filter(&source) {
                Ok(filter) => filter,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            obs.camera_source = Some(source);
            obs.camera_device_id = Some(device_id.clone());
            obs.camera_filters = Some(CameraFilters { background_removal, circle_mask });
        }
        let source = obs.camera_source.clone().expect("camera_source just ensured above");
        let item = match camera::add_existing_camera_to_scene(&mut obs.context, source, &scene) {
            Ok(item) => item,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        obs.camera_items.insert(scene.clone(), item);
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false));
        // A camera appeared in this scene: any cached rectangle is stale (there was none).
        obs.item_rects = None;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
        let Some(obs) = &mut self.obs else { return };
        if !obs.sources.iter().any(|source| source.kind == hikari_protocol::CAMERA_KIND) {
            obs.sources.push(SourceInfo::camera(camera::CAMERA_SOURCE_NAME));
        }
        emit(&EngineMessage::Sources { items: obs.sources.clone() });
    }

    /// Sets whether the background-removal filter is enabled FOR `scene` (B-cam, F-036,
    /// multi-scene tranche 2) — updates that scene's own desired state; applied immediately
    /// only if `scene` is the one currently live (otherwise it takes effect next time this
    /// scene becomes active, via `handle_switch_scene`).
    pub(crate) fn handle_set_background_removal(&mut self, scene: String, enabled: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        if !obs.camera_items.contains_key(&scene) {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        }
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false)).0 = enabled;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
    }

    /// Sets whether the circular mask filter is enabled FOR `scene`. Same per-scene
    /// contract as `handle_set_background_removal`.
    pub(crate) fn handle_set_circle_mask(&mut self, scene: String, enabled: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        if !obs.camera_items.contains_key(&scene) {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        }
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false)).1 = enabled;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
    }

    /// Removes the webcam from `scene` only — other scenes keep it, with their own filter
    /// state untouched. Once no scene shows it anymore, the shared source + filters are
    /// fully released (their `Drop` detaches the filters and destroys the source).
    pub(crate) fn handle_remove_camera(&mut self, scene: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.remove(&scene) else { return };
        if let Err(err) = camera::remove_camera_from_scene(&mut obs.context, &scene, item) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        obs.scene_filter_state.remove(&scene);
        obs.item_rects = None;
        if obs.camera_items.is_empty() {
            obs.camera_source = None;
            obs.camera_device_id = None;
            obs.camera_filters = None;
            // The next camera may be a different device with its own resolution.

            obs.sources.retain(|source| source.kind != hikari_protocol::CAMERA_KIND);
            emit(&EngineMessage::Sources { items: obs.sources.clone() });
        }
    }

    /// Moves the webcam's placement WITHIN `scene` by `(dx, dy)` pixels (B7). A no-op (with
    /// an explicit error, never a silent drop) if `scene` doesn't show the camera.
    pub(crate) fn handle_nudge_camera(&mut self, scene: String, dx: i32, dy: i32) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.get(&scene) else {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        };
        match camera::nudge_camera(item, dx, dy) {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Grows or shrinks the webcam's placement within `scene` by one fixed step (B7). Same
    /// guard as `handle_nudge_camera`.
    pub(crate) fn handle_scale_camera(&mut self, scene: String, grow: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.get(&scene) else {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        };
        match camera::scale_camera(item, grow) {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }
}
