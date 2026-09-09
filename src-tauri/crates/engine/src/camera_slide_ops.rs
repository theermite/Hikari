//! Glisser une caméra partagée d'une scène à l'autre (B7, option A) — extrait de
//! `scene_ops.rs` le 2026-09-09, ce fichier ayant atteint le plafond BLOQUANT de 500 lignes.
//! Groupe cohérent : les trois étapes d'un même geste (démarrer, avancer, clore en place).

use libobs_wrapper::scenes::SceneItemTrait;

use crate::{camera, App, CameraSlide};

impl App {
    /// Glides a camera device shown in BOTH `from_scene` and `to_scene` from its placement
    /// in the scene just left to its OWN saved placement in the scene just entered (B7,
    /// option A — Jay 2026-09-08: the full manually/automation-triggered move is the later
    /// target, this covers only "the same camera appears in both scenes"). A no-op if no
    /// device is shared, or if either placement can't be read — a missing camera glide is
    /// never worth failing the scene switch itself over.
    pub(crate) fn start_camera_slide(
        &mut self,
        from_scene: &str,
        to_scene: &str,
        duration_ms: u32,
    ) {
        if from_scene == to_scene {
            return;
        }
        // Un glissement déjà en vol (2026-09-08, relecture) finit sur SA propre cible avant
        // que celui-ci ne commence — sinon la caméra qu'il déplaçait reste figée à une
        // position intermédiaire, jamais rattrapée par aucun tick puisque `self.camera_slide`
        // va changer de sujet juste après. Fait AVANT tout emprunt du nouveau glissement :
        // les deux glissements peuvent viser des caméras différentes.
        self.finish_camera_slide_in_place();
        let Some(obs) = &mut self.obs else { return };
        // Collected first (never borrowed while re-queried below): every device shown in
        // `from_scene`, matched against `to_scene`'s own keys — the shared HashMap can't be
        // read twice at once through the same `&mut ObsInner` borrow otherwise.
        let from_devices: Vec<String> = obs
            .camera_items
            .keys()
            .filter(|(scene, _)| scene == from_scene)
            .map(|(_, device)| device.clone())
            .collect();
        let Some(device_id) = from_devices.into_iter().find(|device| {
            obs.camera_items
                .contains_key(&(to_scene.to_string(), device.clone()))
        }) else {
            return;
        };
        let Some(from_item) = obs
            .camera_items
            .get(&(from_scene.to_string(), device_id.clone()))
        else {
            return;
        };
        let Ok(from_position) = from_item.get_source_position() else {
            return;
        };
        let Ok(from_scale) = from_item.get_source_scale() else {
            return;
        };
        let from = (
            *from_position.x() as i32,
            *from_position.y() as i32,
            *from_scale.x(),
        );
        let Some(to_item) = obs
            .camera_items
            .get(&(to_scene.to_string(), device_id.clone()))
        else {
            return;
        };
        let Ok(to_position) = to_item.get_source_position() else {
            return;
        };
        let Ok(to_scale) = to_item.get_source_scale() else {
            return;
        };
        let to = (
            *to_position.x() as i32,
            *to_position.y() as i32,
            *to_scale.x(),
        );
        // Starts exactly where the outgoing scene left it — the first frame of the incoming
        // scene must show the OLD spot, or the glide would begin with a jump of its own.
        if camera::set_camera_transform(to_item, from.0, from.1, from.2).is_err() {
            return;
        }
        self.camera_slide = Some(CameraSlide {
            scene: to_scene.to_string(),
            device_id,
            from,
            to,
            started_at: std::time::Instant::now(),
            duration: std::time::Duration::from_millis(duration_ms as u64),
        });
    }

    /// Snaps whatever camera glide is in flight straight to ITS OWN `to`, and clears it
    /// (2026-09-08, relecture) — the shared step `start_camera_slide` (a second switch
    /// interrupting the first) and `advance_camera_slide` (the normal end of a glide) both
    /// need, so the item never gets left at an interpolated position nobody ever finishes
    /// writing or announcing. A no-op if nothing is in flight.
    pub(crate) fn finish_camera_slide_in_place(&mut self) {
        let Some(slide) = self.camera_slide.take() else {
            return;
        };
        let Some(obs) = &self.obs else { return };
        if let Some(item) = obs.camera_items.get(&(slide.scene, slide.device_id)) {
            let _ = camera::set_camera_transform(item, slide.to.0, slide.to.1, slide.to.2);
        }
    }

    /// Advances the in-progress camera glide by one tick (B7, option A) — called from
    /// `about_to_wait` alongside the audio-meter and frame-counter ticks. Ends the slide
    /// (clears `self.camera_slide`) once `elapsed >= duration`, landing EXACTLY on `to`
    /// rather than whatever the last tick's rounding produced. Announces the real state
    /// (`emit_scene_list`) when the glide ENDS (2026-09-08, relecture) — without this, the
    /// last position ever emitted for the camera was the interpolated one from the tick
    /// before completion, and that interpolated value is exactly what a listening panel
    /// would then save as the truth, corrupting the very placement B7's option A exists to
    /// carry across a scene switch.
    pub(crate) fn advance_camera_slide(&mut self) {
        let Some(slide) = &self.camera_slide else {
            return;
        };
        let elapsed = slide.started_at.elapsed();
        let progress = if slide.duration.is_zero() {
            1.0
        } else {
            elapsed.as_secs_f32() / slide.duration.as_secs_f32()
        };
        let (x, y, scale) = hikari_protocol::lerp_camera_transform(slide.from, slide.to, progress);
        let scene = slide.scene.clone();
        let device_id = slide.device_id.clone();
        let done = elapsed >= slide.duration;
        if let Some(obs) = &self.obs {
            if let Some(item) = obs.camera_items.get(&(scene, device_id)) {
                let _ = camera::set_camera_transform(item, x, y, scale);
            }
        }
        if done {
            self.camera_slide = None;
            self.emit_scene_list();
        }
    }
}
