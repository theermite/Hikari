//! Captures placed into a scene: reordering, exact placement, locking, listing what the
//! machine can capture, adding and removing — the source group of `App`'s command handlers.

use hikari_protocol::EngineMessage;

use crate::{App, SceneSource, camera, emit, sources};

impl App {
    /// Moves a source one step in front of, or behind, the others in its scene.
    ///
    /// Notre propre liste bouge du même pas que libobs : elle sert de source de vérité au
    /// panneau, et deux ordres qui divergent donneraient un écran qui ment sur ce qui cache
    /// quoi. À l'écran, la liste va du plus en AVANT au plus en arrière, comme dans OBS.
    pub(crate) fn handle_reorder_source(
        &mut self,
        scene: String,
        name: String,
        direction: hikari_protocol::SourceOrder,
    ) {
        let Some(obs) = &mut self.obs else { return };
        let Some(list) = obs.scene_sources.get_mut(&scene) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source déplaçable de cette scène"),
            });
            return;
        };
        let Some(index) = list.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source déplaçable de cette scène"),
            });
            return;
        };
        // Le premier de la liste est le plus en avant : avancer, c'est reculer d'un index.
        let target = match direction {
            hikari_protocol::SourceOrder::Front => index.checked_sub(1),
            hikari_protocol::SourceOrder::Back => {
                if index + 1 < list.len() { Some(index + 1) } else { None }
            }
        };
        // Déjà au bout : rien à faire, et surtout pas d'enroulement — un clic de trop ne
        // doit jamais envoyer une source à l'autre extrémité de la pile.
        let Some(target) = target else { return };
        let runtime = obs.context.runtime().clone();
        let Some(list) = obs.scene_sources.get_mut(&scene) else { return };
        if let Err(err) = sources::set_order(&runtime, &list[index].item, direction) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        // Vérifié par sonde le 2026-08-05 : notre liste et l'ordre réel du moteur coïncident
        // exactement après cet échange (positions relevées des deux côtés).
        list.swap(index, target);
        // L'ordre décide quelle source un clic désigne : le cache doit repartir de zéro.
        obs.item_rects = None;
        self.emit_scene_list();
    }

    /// Places a source exactly — la commande qui rend une session rejouable.
    pub(crate) fn handle_set_source_transform(
        &mut self,
        scene: String,
        name: String,
        x: i32,
        y: i32,
        scale_percent: i32,
    ) {
        let Some(obs) = &self.obs else { return };
        // La caméra ne vit pas dans `scene_sources` (elle est UNE source physique partagée,
        // rangée à part) : la chercher là seulement rendait son cadrage IMPLACABLE au rejeu
        // de session — retenu sur le disque, refusé par le moteur (Jay, 2026-08-06).
        let Some(item) = obs
            .scene_sources
            .get(&scene)
            .and_then(|list| list.iter().find(|source| source.name == name))
            .map(|source| &source.item)
            .or_else(|| {
                (name == camera::CAMERA_SOURCE_NAME).then(|| obs.camera_items.get(&scene))?
            })
        else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas dans « {scene} »"),
            });
            return;
        };
        // L'échelle voyage en pourcentage — un entier survit à l'aller-retour d'un fichier
        // de session sans les surprises d'arrondi d'un nombre à virgule.
        let scale = hikari_protocol::clamp_camera_scale(scale_percent as f32 / 100.0);
        if let Err(err) = camera::set_camera_transform(item, x, y, scale) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.scene_layout_changed();
        self.emit_scene_list();
    }

    /// Locks or unlocks a source against the mouse, in ONE scene (brique Sources).
    ///
    /// Ne vérifie pas que la source existe : verrouiller ce qui n'est pas là n'abîme rien, et
    /// une erreur ici ferait échouer le rejeu d'une session dont une source a disparu entre
    /// deux lancements (une fenêtre fermée, un fichier déplacé). Le verrou attend alors la
    /// source, plutôt que d'interrompre tout le reste.
    pub(crate) fn handle_set_source_locked(&mut self, scene: String, name: String, locked: bool) {
        let Some(obs) = &mut self.obs else { return };
        if locked {
            obs.locked.insert((scene, name));
        } else {
            obs.locked.remove(&(scene, name));
        }
        // Le cache des rectangles décide de ce qu'un clic peut attraper : le laisser tel quel
        // rendrait le verrou effectif seulement au prochain changement de scène.
        obs.item_rects = None;
        self.emit_scene_list();
    }

    /// Emits everything the machine can capture right now (brique Sources).
    pub(crate) fn handle_list_capture_targets(&mut self) {
        let (games, windows, monitors) = sources::list_capture_targets();
        emit(&EngineMessage::CaptureTargets { games, windows, monitors });
    }

    /// The names already taken in `scene` — every capture plus the camera. Used to refuse a
    /// duplicate BEFORE libobs silently renames it ("Webcam 2").
    fn source_names_in_scene(&self, scene: &str) -> Vec<String> {
        let Some(obs) = &self.obs else { return Vec::new() };
        let mut names: Vec<String> = obs
            .scene_sources
            .get(scene)
            .map(|added| added.iter().map(|source| source.name.clone()).collect())
            .unwrap_or_default();
        if obs.camera_items.contains_key(scene) {
            names.push(camera::CAMERA_SOURCE_NAME.to_string());
        }
        names
    }

    /// Adds a game, window or screen capture into a scene (brique Sources).
    pub(crate) fn handle_add_capture_source(
        &mut self,
        scene: String,
        kind: hikari_protocol::SourceKind,
        target_id: String,
        name: String,
    ) {
        if self.obs.is_none() {
            emit(&EngineMessage::Error {
                message: "AddCaptureSource avant l'initialisation".into(),
            });
            return;
        }
        let taken = self.source_names_in_scene(&scene);
        if let Err(err) = hikari_protocol::validate_source_name(&name, &taken) {
            let message = match err {
                hikari_protocol::SceneNameError::Empty => "le nom de la source est vide".to_string(),
                hikari_protocol::SceneNameError::Duplicate => {
                    format!("« {name} » existe déjà dans cette scène")
                }
            };
            emit(&EngineMessage::Error { message });
            return;
        }
        let Some(obs) = &mut self.obs else { return };
        match sources::add_capture_to_scene(&mut obs.context, kind, &target_id, &name, &scene) {
            Ok(item) => {
                // En TÊTE, pas en queue : libobs pose une nouvelle source devant les autres,
                // et notre liste doit refléter cet ordre réel — sinon le panneau annoncerait
                // l'inverse de ce que l'écran montre.
                obs.scene_sources.entry(scene).or_default().insert(
                    0,
                    SceneSource {
                        name,
                        kind: kind.libobs_id().to_string(),
                        source_kind: kind,
                        target_id,
                        item,
                    },
                );
                // Oubli corrigé le 2026-08-05 : sans ça, le cache des rectangles gardait la
                // scène telle qu'elle était AVANT l'ajout, donc la nouvelle source n'était
                // saisissable par personne.
                obs.item_rects = None;
            }
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        }
        self.emit_scene_list();
    }

    /// Removes a capture from ONE scene. Other scenes keep theirs.
    pub(crate) fn handle_remove_source(&mut self, scene: String, name: String) {
        let Some(obs) = &mut self.obs else { return };
        let Some(list) = obs.scene_sources.get_mut(&scene) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source retirable de cette scène"),
            });
            return;
        };
        let Some(index) = list.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source retirable de cette scène"),
            });
            return;
        };
        let removed = list.remove(index);
        obs.item_rects = None;
        if let Err(err) = sources::remove_from_scene(&mut obs.context, &scene, removed.item) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        self.emit_scene_list();
    }
}
