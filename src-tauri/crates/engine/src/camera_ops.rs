//! Les caméras : les ouvrir, les poser dans une scène, leurs deux filtres, les retirer, et
//! les commandes de cadrage au pas fixe (B7) — le groupe caméra des gestionnaires d'`App`.
//!
//! Depuis le 2026-09-06 il y en a PLUSIEURS. Chaque appareil a sa propre source libobs,
//! ses propres filtres, et son propre cadrage dans chaque scène qui le montre. Auparavant
//! une seule source existait : choisir un deuxième appareil renvoyait le premier, sans
//! erreur — l'utilisateur voyait simplement la mauvaise image.

use anyhow::{Context, Result};
use hikari_protocol::{EngineMessage, SourceInfo};

use crate::{App, CameraFilters, CameraItem, OpenCamera, camera, emit};

impl App {
    /// Ouvre l'appareil `device_id` : une source libobs et ses deux filtres, une seule fois
    /// par appareil. Ne la pose dans aucune scène — c'est le travail de `handle_add_camera`.
    fn open_camera(&mut self, device_id: &str) -> Result<()> {
        let obs = self.obs.as_mut().context("AddCamera avant l'initialisation")?;
        // Le nom lisible vient du moteur lui-même, jamais du fil : c'est la seule source qui
        // dise la vérité si l'appareil a été rebranché sous un autre libellé.
        let device_name = camera::probe_camera_devices(&obs.context)
            .unwrap_or_default()
            .into_iter()
            .find(|device| device.device_id == device_id)
            .map(|device| device.name)
            .unwrap_or_default();
        let taken: Vec<String> = obs.cameras.values().map(|camera| camera.name.clone()).collect();
        let name = camera::camera_source_name(&device_name, &taken);
        let source = camera::build_camera_source(&mut obs.context, &name, device_id)?;
        let background_removal = camera::create_background_removal_filter(&source)?;
        let circle_mask = camera::create_circle_mask_filter(&source)?;
        let filters = CameraFilters { background_removal, circle_mask };
        obs.cameras.insert(device_id.to_string(), OpenCamera { source, name, filters });
        Ok(())
    }

    /// Pose la caméra `device_id` dans `scene`. L'appareil n'est ouvert qu'à la première
    /// demande ; toute scène suivante réutilise la MÊME source, avec son propre élément de
    /// scène — donc son propre cadrage, exactement comme OBS traite une source partagée.
    pub(crate) fn handle_add_camera(&mut self, device_id: String, scene: String) {
        if self.obs.is_none() {
            emit(&EngineMessage::Error { message: "AddCamera avant l'initialisation".into() });
            return;
        }
        if !self.obs.as_ref().is_some_and(|obs| obs.cameras.contains_key(&device_id)) {
            if let Err(err) = self.open_camera(&device_id) {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        }
        let Some(obs) = &mut self.obs else { return };
        let Some(opened) = obs.cameras.get(&device_id) else { return };
        let (source, name) = (opened.source.clone(), opened.name.clone());
        let item = match camera::add_existing_camera_to_scene(&mut obs.context, source, &scene) {
            Ok(item) => item,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        let key = (scene.clone(), device_id.clone());
        obs.camera_items.insert(key.clone(), item);
        obs.scene_filter_state.entry(key).or_insert((false, false));
        // Une caméra est apparue dans cette scène : tout rectangle en cache est périmé.
        obs.item_rects = None;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
        let Some(obs) = &mut self.obs else { return };
        if !obs.sources.iter().any(|source| source.name == name) {
            obs.sources.push(SourceInfo::camera(name));
        }
        emit(&EngineMessage::Sources { items: obs.sources.clone() });
    }

    /// Règle le fond détouré (NVIDIA) pour la caméra `device_id` DANS `scene` (B-cam,
    /// F-036) — chaque scène garde son propre état voulu, appliqué dès qu'elle passe en
    /// direct (`handle_switch_scene`), jamais imposé aux autres scènes.
    pub(crate) fn handle_set_background_removal(
        &mut self,
        device_id: String,
        scene: String,
        enabled: bool,
    ) {
        self.set_camera_filter(device_id, scene, |state| state.0 = enabled);
    }

    /// Règle le masque circulaire. Même contrat par caméra et par scène.
    pub(crate) fn handle_set_circle_mask(&mut self, device_id: String, scene: String, enabled: bool) {
        self.set_camera_filter(device_id, scene, |state| state.1 = enabled);
    }

    /// Le tronc commun des deux réglages de filtre : même garde, même portée, même
    /// application immédiate si la scène est celle en direct.
    fn set_camera_filter(
        &mut self,
        device_id: String,
        scene: String,
        change: impl FnOnce(&mut (bool, bool)),
    ) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let key = (scene.clone(), device_id);
        if !obs.camera_items.contains_key(&key) {
            emit(&EngineMessage::Error {
                message: "cette caméra n'est pas dans cette scène — ajoute-la d'abord".into(),
            });
            return;
        }
        change(obs.scene_filter_state.entry(key).or_insert((false, false)));
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
    }

    /// Retire la caméra `device_id` de `scene` seulement — les autres scènes la gardent avec
    /// leurs propres filtres, et les autres caméras de `scene` ne bougent pas. L'appareil
    /// n'est relâché (sa source et ses filtres détruits) que lorsque plus aucune scène ne
    /// le montre.
    pub(crate) fn handle_remove_camera(&mut self, device_id: String, scene: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let key = (scene.clone(), device_id.clone());
        let Some(item) = obs.camera_items.remove(&key) else { return };
        if let Err(err) = camera::remove_camera_from_scene(&mut obs.context, &scene, item) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        obs.scene_filter_state.remove(&key);
        obs.item_rects = None;
        let still_shown = obs.camera_items.keys().any(|(_, shown)| shown == &device_id);
        if !still_shown {
            // La prochaine caméra peut être un autre appareil, avec sa propre définition.
            if let Some(closed) = obs.cameras.remove(&device_id) {
                obs.sources.retain(|source| source.name != closed.name);
                emit(&EngineMessage::Sources { items: obs.sources.clone() });
            }
        }
        // La scène ne porte plus cette caméra : le dire. Sans ça l'écran gardait la caméra
        // dans la liste de la scène jusqu'au prochain changement — l'interface montrait une
        // source que le moteur avait déjà retirée (trouvé le 2026-09-06).
        self.emit_scene_list();
    }

    /// Les caméras posées dans `scene`, chacune sous son nom — triées, pour que la pile de
    /// sources ne change pas d'ordre d'un lancement à l'autre.
    pub(crate) fn cameras_in_scene(&self, scene: &str) -> Vec<(String, &CameraItem)> {
        let Some(obs) = self.obs.as_ref() else { return Vec::new() };
        let mut found: Vec<_> = obs
            .camera_items
            .iter()
            .filter(|((shown_in, _), _)| shown_in == scene)
            .filter_map(|((_, device_id), item)| {
                Some((obs.cameras.get(device_id)?.name.clone(), item))
            })
            .collect();
        found.sort_by(|(left, _), (right, _)| left.cmp(right));
        found
    }

    /// Les caméras de `scene` en valeurs POSSÉDÉES — nom lisible et appareil, sans emprunt.
    ///
    /// Existe pour les appelants qui tiennent déjà un emprunt mutable du moteur : ils ne
    /// peuvent pas relire `self` en même temps, et une liste possédée les en dispense.
    pub(crate) fn camera_names_in_scene(&self, scene: &str) -> Vec<(String, String)> {
        let Some(obs) = self.obs.as_ref() else { return Vec::new() };
        let mut found: Vec<(String, String)> = obs
            .camera_items
            .keys()
            .filter(|(shown_in, _)| shown_in == scene)
            .filter_map(|(_, device_id)| {
                Some((obs.cameras.get(device_id)?.name.clone(), device_id.clone()))
            })
            .collect();
        found.sort();
        found
    }

    /// L'élément de scène de la caméra qui porte ce NOM dans `scene`.
    ///
    /// Le repli sur l'unique caméra de la scène sert le rejeu d'une session enregistrée
    /// avant le 2026-09-06 : elle a retenu le nom historique « Webcam », alors que la caméra
    /// rouverte porte désormais le nom de son appareil. Sans ce repli, le cadrage sauvegardé
    /// serait refusé en silence — le défaut déjà vécu le 2026-08-06.
    pub(crate) fn camera_item_by_name(&self, scene: &str, name: &str) -> Option<&CameraItem> {
        let shown = self.cameras_in_scene(scene);
        if let Some((_, item)) = shown.iter().find(|(camera_name, _)| camera_name == name) {
            return Some(item);
        }
        if name == camera::CAMERA_SOURCE_NAME && shown.len() == 1 {
            return Some(shown[0].1);
        }
        None
    }

    /// L'appareil derrière une caméra désignée par son nom dans `scene`, s'il y en a un.
    ///
    /// Vide pour une source ordinaire : un déplacement à la souris rapporte le même message
    /// pour toutes les sources, et une chaîne vide dit « ceci n'est pas une caméra » sans
    /// inventer un identifiant qui ne désignerait rien.
    pub(crate) fn camera_device_id_by_name(&self, scene: &str, name: &str) -> String {
        let Some(obs) = self.obs.as_ref() else { return String::new() };
        let trouve = obs
            .camera_items
            .keys()
            .filter(|(shown_in, _)| shown_in == scene)
            .find(|(_, device_id)| {
                obs.cameras.get(device_id).is_some_and(|opened| opened.name == name)
            })
            .map(|(_, device_id)| device_id.clone());
        // Silencieux quand ça marche, bavard quand ça rate. Un refus de retrait resté
        // inexpliqué le 2026-09-06 : il ne se reproduisait plus une heure après, et sans
        // cette trace la prochaine fois serait aussi muette que la première.
        if trouve.is_none() {
            eprintln!(
                "[engine] CAMERA INTROUVABLE scene={scene:?} nom={name:?} posees={:?}",
                obs.camera_items
                    .keys()
                    .map(|(shown_in, device_id)| (
                        shown_in,
                        obs.cameras.get(device_id).map(|opened| &opened.name)
                    ))
                    .collect::<Vec<_>>()
            );
        }
        trouve.unwrap_or_default()
    }

    /// Ferme les appareils que plus aucune scène ne montre.
    ///
    /// Appelé après la suppression d'une scène : sans cela l'appareil resterait ouvert —
    /// témoin lumineux allumé, caméra indisponible pour une autre application — alors que
    /// plus rien ne l'affiche. `handle_remove_camera` fait déjà ce ménage pour son propre
    /// retrait ; supprimer une scène en retire plusieurs d'un coup.
    pub(crate) fn release_unused_cameras(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        let orphans: Vec<String> = obs
            .cameras
            .keys()
            .filter(|device_id| {
                !obs.camera_items.keys().any(|(_, shown)| &shown == device_id)
            })
            .cloned()
            .collect();
        if orphans.is_empty() {
            return;
        }
        for device_id in orphans {
            if let Some(closed) = obs.cameras.remove(&device_id) {
                obs.sources.retain(|source| source.name != closed.name);
            }
        }
        emit(&EngineMessage::Sources { items: obs.sources.clone() });
    }

    /// Déplace la caméra `device_id` DANS `scene` de `(dx, dy)` pixels (B7). Un refus
    /// explicite, jamais un abandon silencieux, si cette scène ne la montre pas.
    pub(crate) fn handle_nudge_camera(&mut self, device_id: String, scene: String, dx: i32, dy: i32) {
        self.transform_camera(device_id, scene, |item| camera::nudge_camera(item, dx, dy));
    }

    /// Agrandit ou réduit la caméra `device_id` dans `scene` d'un pas fixe (B7). Même garde.
    pub(crate) fn handle_scale_camera(&mut self, device_id: String, scene: String, grow: bool) {
        self.transform_camera(device_id, scene, |item| camera::scale_camera(item, grow));
    }

    /// Le tronc commun du déplacement et du redimensionnement : trouver l'élément de scène
    /// de CETTE caméra, appliquer, puis rapporter le cadrage réel obtenu.
    fn transform_camera(
        &mut self,
        device_id: String,
        scene: String,
        apply: impl FnOnce(&CameraItem) -> Result<(i32, i32, i32)>,
    ) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.get(&(scene.clone(), device_id.clone())) else {
            emit(&EngineMessage::Error {
                message: "cette caméra n'est pas dans cette scène — ajoute-la d'abord".into(),
            });
            return;
        };
        match apply(item) {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { device_id, scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }
}
