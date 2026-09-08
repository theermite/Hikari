//! Scene lifecycle (create/switch/delete) and the shared tail every scene-changing command
//! calls to emit the real state — the scene group of `App`'s command handlers.

use hikari_protocol::{EngineMessage, SceneInfo};
use libobs_wrapper::scenes::SceneItemTrait;

use crate::{App, CameraSlide, camera, emit, scenes};

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

    /// Switches the live scene through the app's one fade transition (B7). `duration_ms`
    /// (already `hikari_protocol::clamp_transition_duration_ms`-clamped by the caller, and
    /// re-clamped here as the defensive floor) is `0` for an instant cut. Errors clearly on
    /// an unknown name rather than a silent no-op.
    pub(crate) fn handle_switch_scene(&mut self, name: String, duration_ms: u32) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "SwitchScene avant l'initialisation".into() });
            return;
        };
        let duration_ms = hikari_protocol::clamp_transition_duration_ms(duration_ms);
        let previous_scene = obs.active_scene.clone();
        if let Err(err) = scenes::switch_scene(&mut obs.context, &obs.transition, &name, duration_ms) {
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
        // L'ORDRE entre les deux lignes suivantes n'a plus d'importance (2026-09-09,
        // troisième tour de relecture) : `emit_scene_list` sait maintenant lire
        // `self.camera_slide` et publie la destination du glissement pour la caméra
        // concernée, jamais une position interpolée — quel que soit le moment où
        // N'IMPORTE QUEL appelant (celui-ci, `RequestSceneList`, une suppression, un futur
        // appelant) la demande. Les deux tours précédents rapiéçaient un ORDRE d'appel ;
        // celui-ci ferme la famille en donnant à l'annonce sa propre source de vérité.
        self.emit_scene_list();
        if duration_ms > 0 {
            self.start_camera_slide(&previous_scene, &name, duration_ms);
        }
    }

    /// Glides a camera device shown in BOTH `from_scene` and `to_scene` from its placement
    /// in the scene just left to its OWN saved placement in the scene just entered (B7,
    /// option A — Jay 2026-09-08: the full manually/automation-triggered move is the later
    /// target, this covers only "the same camera appears in both scenes"). A no-op if no
    /// device is shared, or if either placement can't be read — a missing camera glide is
    /// never worth failing the scene switch itself over.
    fn start_camera_slide(&mut self, from_scene: &str, to_scene: &str, duration_ms: u32) {
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
        let Some(device_id) = from_devices
            .into_iter()
            .find(|device| obs.camera_items.contains_key(&(to_scene.to_string(), device.clone())))
        else {
            return;
        };
        let Some(from_item) = obs.camera_items.get(&(from_scene.to_string(), device_id.clone())) else { return };
        let Ok(from_position) = from_item.get_source_position() else { return };
        let Ok(from_scale) = from_item.get_source_scale() else { return };
        let from = (*from_position.x() as i32, *from_position.y() as i32, *from_scale.x());
        let Some(to_item) = obs.camera_items.get(&(to_scene.to_string(), device_id.clone())) else { return };
        let Ok(to_position) = to_item.get_source_position() else { return };
        let Ok(to_scale) = to_item.get_source_scale() else { return };
        let to = (*to_position.x() as i32, *to_position.y() as i32, *to_scale.x());
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
    fn finish_camera_slide_in_place(&mut self) {
        let Some(slide) = self.camera_slide.take() else { return };
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
        let Some(slide) = &self.camera_slide else { return };
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
        // Ce que l'ANNONCE doit dire pour une caméra en plein glissement (2026-09-09,
        // troisième tour de relecture — la famille n'était pas fermée en changeant
        // seulement l'ORDRE d'appel dans `handle_switch_scene` : tout autre appelant de
        // cette même fonction — `RequestSceneList`, une suppression, le filet
        // `scene_contents_fingerprint`, une future commande — publiait encore la position
        // interpolée, jamais lue nulle part ailleurs que dans le mouvement lui-même).
        // Capturé AVANT d'emprunter `self.obs`, jamais depuis libobs pour ce couple précis :
        // la vérité annoncée d'une caméra en vol est TOUJOURS sa destination déjà
        // enregistrée pour la scène qu'elle rejoint, quel que soit l'instant où quelqu'un
        // demande l'inventaire.
        let slide_target = self
            .camera_slide
            .as_ref()
            .map(|slide| (slide.scene.clone(), slide.device_id.clone(), slide.to));
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
                            visible: !obs
                                .hidden
                                .contains(&(name.clone(), source.name.clone())),
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
                    // En vol : la vérité annoncée est la destination du glissement, jamais
                    // la position interpolée que libobs affiche réellement à cet instant.
                    let in_flight = slide_target
                        .as_ref()
                        .filter(|(slide_scene, slide_device, _)| {
                            slide_scene == &name && slide_device == device_id
                        })
                        .map(|(_, _, to)| *to);
                    let (x, y, scale_percent) = match in_flight {
                        Some((x, y, scale)) => (x, y, (scale * 100.0).round() as i32),
                        None => {
                            let position = item.get_source_position().ok();
                            let scale = item.get_source_scale().ok();
                            (
                                position.as_ref().map_or(0, |p| *p.x() as i32),
                                position.as_ref().map_or(0, |p| *p.y() as i32),
                                scale.as_ref().map_or(100, |s| (s.x() * 100.0).round() as i32),
                            )
                        }
                    };
                    sources.push(hikari_protocol::SceneSourceInfo {
                        kind: hikari_protocol::CAMERA_KIND.to_string(),
                        source_kind: hikari_protocol::SourceKind::Camera,
                        target_id: device_id.clone(),
                        x,
                        y,
                        scale_percent,
                        locked: obs.locked.contains(&(name.clone(), camera_name.clone())),
                        background_removal,
                        circle_mask,
                        visible: !obs.hidden.contains(&(name.clone(), camera_name.clone())),
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
        // Un glissement en vol VERS cette scène (2026-09-09, relecture) n'a plus de scène
        // où arriver — même raison que `handle_remove_camera`. Fait seulement ICI, APRÈS la
        // validation (avertissement de relecture, 2026-09-09) : une suppression REFUSÉE
        // (scène inconnue, dernière scène) ne doit tuer aucun glissement d'une scène qui
        // continue d'exister.
        if let Some(slide) = &self.camera_slide {
            if slide.scene == name {
                self.camera_slide = None;
            }
        }

        // Leave the scene before dropping it: a fallback is guaranteed to exist here,
        // because `validate_scene_deletion` already refused the last-scene case.
        if obs.active_scene == name {
            let Some(fallback) = existing.iter().find(|other| **other != name).cloned() else {
                emit(&EngineMessage::Error { message: "aucune scène de repli".into() });
                return;
            };
            // Instant cut: this fallback is forced by a deletion, never a user gesture — an
            // animated fade here would be motion nobody asked for.
            self.handle_switch_scene(fallback, 0);
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
