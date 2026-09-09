//! Scene lifecycle (create/switch/delete) and the shared tail every scene-changing command
//! calls to emit the real state — the scene group of `App`'s command handlers.

use hikari_protocol::{EngineMessage, SceneInfo};
use libobs_wrapper::scenes::SceneItemTrait;

use crate::{camera, emit, scenes, sources, App, MASK_RETRY_MAX_ATTEMPTS};

impl App {
    /// Creates a new, empty scene (multi-scene, tranche 1). Rejects a blank or already-used
    /// name (`hikari_protocol::validate_scene_name`) — checked against the engine's OWN live
    /// scene list, never a name the caller merely claims doesn't exist yet.
    pub(crate) fn handle_create_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error {
                message: "CreateScene avant l'initialisation".into(),
            });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error {
                    message: err.to_string(),
                });
                return;
            }
        };
        if let Err(err) = hikari_protocol::validate_scene_name(&name, &existing) {
            emit(&EngineMessage::Error {
                message: format!("nom de scène invalide : {err:?}"),
            });
            return;
        }
        if let Err(err) = scenes::create_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error {
                message: err.to_string(),
            });
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
            emit(&EngineMessage::Error {
                message: "SwitchScene avant l'initialisation".into(),
            });
            return;
        };
        let duration_ms = hikari_protocol::clamp_transition_duration_ms(duration_ms);
        let previous_scene = obs.active_scene.clone();
        if let Err(err) =
            scenes::switch_scene(&mut obs.context, &obs.transition, &name, duration_ms)
        {
            emit(&EngineMessage::Error {
                message: err.to_string(),
            });
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

    /// Applies the filter state `scene` wants for EACH camera it shows — called on
    /// `SwitchScene` and right after `AddCamera` when the target scene is already live.
    ///
    /// Per camera since 2026-09-06: two cameras can share a scene with different looks (one
    /// detoured, one framed in a circle), so a single pair of booleans could not describe it.
    pub(crate) fn apply_scene_filter_state(&mut self, scene: &str) {
        let Some(obs) = &mut self.obs else { return };
        let wanted: Vec<(String, (bool, hikari_protocol::MaskShape))> = obs
            .scene_filter_state
            .iter()
            .filter(|((shown_in, _), _)| shown_in == scene)
            .map(|((_, device_id), state)| (device_id.clone(), *state))
            .collect();
        for (device_id, (background_removal_on, mask_shape)) in wanted {
            let Some(opened) = obs.cameras.get(&device_id) else {
                continue;
            };
            if let Err(err) = camera::set_filter_enabled(
                &opened.filters.background_removal,
                background_removal_on,
            ) {
                emit(&EngineMessage::Error {
                    message: err.to_string(),
                });
            }
            let key = (scene.to_string(), device_id.clone());
            match camera::set_mask_shape(&opened.filters.mask, &opened.source, mask_shape) {
                Ok(camera::MaskApplyOutcome::Applied) => {
                    obs.mask_retry_pending.remove(&key);
                }
                // La caméra n'a pas encore rendu d'image — pas une faute de l'utilisateur,
                // rien à lui dire. `retry_pending_masks` retentera au prochain tick tant
                // que la paire reste ici (2026-09-09, relecture indépendante avant
                // publication : sans cette file, un masque demandé au rejeu d'une session
                // se perdait purement et simplement, sans erreur visible).
                Ok(camera::MaskApplyOutcome::CameraNotReadyYet) => {
                    obs.mask_retry_pending.insert(key, 0);
                }
                Err(err) => {
                    emit(&EngineMessage::Error {
                        message: err.to_string(),
                    });
                }
            }
        }
    }

    /// Retente les masques mis en attente parce que leur caméra n'avait pas encore rendu
    /// d'image (2026-09-09, relecture indépendante avant publication) — appelé à chaque
    /// tick tant que `mask_retry_pending` n'est pas vide, voir `event_loop::about_to_wait`.
    /// Relit l'état VOULU à chaque tentative, jamais celui qui a échoué la première fois :
    /// l'utilisateur a pu régler autre chose pendant l'attente.
    ///
    /// Deux garde-fous ajoutés au second passage de relecture indépendante :
    /// - **une scène en attente qui n'est PAS celle actuellement en direct n'est jamais
    ///   appliquée maintenant** — le filtre de masque est partagé par appareil entre toutes
    ///   les scènes qui le montrent ; l'appliquer pour une scène non live écrirait sur ce
    ///   que la scène RÉELLEMENT à l'antenne affiche. L'entrée reste en attente : la
    ///   prochaine fois que sa scène redevient active, `apply_scene_filter_state` la reprend
    ///   depuis le début.
    /// - **une attente qui dépasse `MASK_RETRY_MAX_ATTEMPTS` est abandonnée avec un message**
    ///   — sans ça, une caméra qui ne démarre jamais (prise par un autre logiciel, pilote en
    ///   erreur) laissait l'utilisateur cliquer dans le vide indéfiniment, sans un mot.
    pub(crate) fn retry_pending_masks(&mut self) {
        let mut changed = false;
        let mut gave_up: Vec<String> = Vec::new();
        if let Some(obs) = &mut self.obs {
            if obs.mask_retry_pending.is_empty() {
                return;
            }
            let active_scene = obs.active_scene.clone();
            let pending: Vec<((String, String), u32)> = obs
                .mask_retry_pending
                .iter()
                .map(|(key, attempts)| (key.clone(), *attempts))
                .collect();
            for (key, attempts) in pending {
                let (scene, device_id) = &key;
                if scene != &active_scene {
                    // Pas la scène à l'antenne : on n'y touche pas ce tick-ci, elle reste en
                    // attente jusqu'à ce qu'elle redevienne active.
                    continue;
                }
                let Some(opened) = obs.cameras.get(device_id) else {
                    // L'appareil a été retiré pendant l'attente : plus rien à réessayer.
                    obs.mask_retry_pending.remove(&key);
                    changed = true;
                    continue;
                };
                let mask_shape = obs
                    .scene_filter_state
                    .get(&key)
                    .map(|(_, shape)| *shape)
                    .unwrap_or(hikari_protocol::MaskShape::None);
                match camera::set_mask_shape(&opened.filters.mask, &opened.source, mask_shape) {
                    Ok(camera::MaskApplyOutcome::Applied) => {
                        obs.mask_retry_pending.remove(&key);
                        changed = true;
                    }
                    Ok(camera::MaskApplyOutcome::CameraNotReadyYet) => {
                        let attempts = attempts + 1;
                        if attempts >= MASK_RETRY_MAX_ATTEMPTS {
                            obs.mask_retry_pending.remove(&key);
                            gave_up.push(device_id.clone());
                            changed = true;
                        } else {
                            obs.mask_retry_pending.insert(key, attempts);
                        }
                    }
                    Err(err) => {
                        obs.mask_retry_pending.remove(&key);
                        emit(&EngineMessage::Error {
                            message: err.to_string(),
                        });
                        changed = true;
                    }
                }
            }
        }
        for device_id in gave_up {
            emit(&EngineMessage::Error {
                message: format!(
                    "La caméra {device_id} n'a pas démarré après plusieurs secondes — son masque n'a pas pu être posé. Elle est peut-être utilisée par une autre application."
                ),
            });
        }
        if changed {
            self.emit_scene_list();
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
        let Some(obs) = self.obs.as_ref() else {
            return Vec::new();
        };
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
        let runtime = obs.context.runtime().clone();
        let names = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error {
                    message: err.to_string(),
                });
                return;
            }
        };
        let scenes = names
            .into_iter()
            .map(|name| {
                let has_camera = obs
                    .camera_items
                    .keys()
                    .any(|(shown_in, _)| shown_in == &name);
                // Chaque entrée porte sa position RÉELLE dans la pile libobs, à côté de son
                // apparence — la même paire que `active_item_rects` (`drag_ops.rs`) lit déjà
                // pour savoir quelle source un clic désigne. Sans elle, une caméra ne pouvait
                // pas être réordonnée : la pile annoncée classait toujours les captures par
                // ordre d'ajout et les caméras par identifiant d'appareil, jamais par la
                // position que `ReorderSource` venait de lui donner (2026-09-09).
                let mut ordered: Vec<(i32, hikari_protocol::SceneSourceInfo)> = Vec::new();
                if let Some(added) = obs.scene_sources.get(&name) {
                    ordered.extend(added.iter().map(|source| {
                        // Placement lu depuis libobs, jamais mémorisé de notre côté : une
                        // copie qui dérive ferait sauvegarder une position fausse.
                        let position = source.item.get_source_position().ok();
                        let scale = source.item.get_source_scale().ok();
                        let order = sources::order_position(&runtime, &source.item).unwrap_or(0);
                        (
                            order,
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
                                locked: obs.locked.contains(&(name.clone(), source.name.clone())),
                                // Une capture n'a pas de filtre caméra : la case existe pour
                                // toutes les sources, elle ne vaut quelque chose que pour une caméra.
                                background_removal: false,
                                mask_shape: hikari_protocol::MaskShape::None,
                                visible: !obs.hidden.contains(&(name.clone(), source.name.clone())),
                            },
                        )
                    }));
                }
                // Une entrée par caméra posée dans cette scène. Même traitement que les
                // autres sources : placement lu depuis libobs, et l'appareil retenu comme
                // cible — c'est ce qui rend chaque caméra rejouable au lancement suivant.
                // Le tri final (plus bas) décide de l'ordre réellement montré ; celui-ci
                // n'a plus qu'à rester STABLE d'un appel à l'autre pour les caméras dont la
                // position exacte serait, par malchance, illisible (repli à `unwrap_or(0)`).
                let mut shown: Vec<(&String, _)> = obs
                    .camera_items
                    .iter()
                    .filter(|((shown_in, _), _)| shown_in == &name)
                    .map(|((_, device_id), item)| (device_id, item))
                    .collect();
                shown.sort_by_key(|(device_id, _)| (*device_id).clone());
                for (device_id, item) in shown {
                    let camera_name = obs
                        .cameras
                        .get(device_id)
                        .map(|opened| opened.name.clone())
                        .unwrap_or_else(|| camera::CAMERA_SOURCE_NAME.to_string());
                    let (background_removal, mask_shape) = obs
                        .scene_filter_state
                        .get(&(name.clone(), device_id.clone()))
                        .copied()
                        .unwrap_or((false, hikari_protocol::MaskShape::None));
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
                                scale
                                    .as_ref()
                                    .map_or(100, |s| (s.x() * 100.0).round() as i32),
                            )
                        }
                    };
                    let order = sources::order_position(&runtime, item).unwrap_or(0);
                    ordered.push((
                        order,
                        hikari_protocol::SceneSourceInfo {
                            kind: hikari_protocol::CAMERA_KIND.to_string(),
                            source_kind: hikari_protocol::SourceKind::Camera,
                            target_id: device_id.clone(),
                            x,
                            y,
                            scale_percent,
                            locked: obs.locked.contains(&(name.clone(), camera_name.clone())),
                            background_removal,
                            mask_shape,
                            visible: !obs.hidden.contains(&(name.clone(), camera_name.clone())),
                            name: camera_name,
                        },
                    ));
                }
                // Triée par la pile RÉELLE du moteur, jamais par l'ordre d'ajout ou
                // l'alphabet d'un identifiant — décroissant, donc le plus en avant vient en
                // premier (même convention que `SceneRow.tsx` et `active_item_rects`).
                ordered.sort_by_key(|(order, _)| std::cmp::Reverse(*order));
                let sources: Vec<hikari_protocol::SceneSourceInfo> =
                    ordered.into_iter().map(|(_, info)| info).collect();
                SceneInfo {
                    has_camera,
                    sources,
                    name,
                }
            })
            .collect();
        emit(&EngineMessage::SceneList {
            scenes,
            active: obs.active_scene.clone(),
        });
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
            emit(&EngineMessage::Error {
                message: "DeleteScene avant l'initialisation".into(),
            });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error {
                    message: err.to_string(),
                });
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
                emit(&EngineMessage::Error {
                    message: "aucune scène de repli".into(),
                });
                return;
            };
            // Instant cut: this fallback is forced by a deletion, never a user gesture — an
            // animated fade here would be motion nobody asked for.
            self.handle_switch_scene(fallback, 0);
            let Some(obs_again) = &mut self.obs else {
                return;
            };
            if obs_again.active_scene == name {
                // The switch failed and already reported why; deleting now would leave the
                // output channel on a dropped scene.
                return;
            }
        }

        let Some(obs) = &mut self.obs else { return };
        obs.camera_items
            .retain(|(shown_in, _), _| shown_in != &name);
        obs.scene_filter_state
            .retain(|(shown_in, _), _| shown_in != &name);
        obs.item_rects = None;
        // Une caméra que plus aucune scène ne montre garde l'appareil ouvert : témoin
        // allumé, et indisponible ailleurs. Elle part avec la dernière scène qui l'affichait.
        self.release_unused_cameras();
        let Some(obs) = &mut self.obs else { return };
        // Les captures de cette scène partent avec elle : garder leurs poignées maintiendrait
        // la scène en vie et la suppression ne ferait rien (même piège que l'élément caméra).
        obs.scene_sources.remove(&name);
        if let Err(err) = scenes::delete_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error {
                message: err.to_string(),
            });
            return;
        }
        self.emit_scene_list();
    }
}
