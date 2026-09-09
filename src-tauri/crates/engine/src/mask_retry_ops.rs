//! La nouvelle tentative d'un masque de caméra pas encore posé (2026-09-09, relecture
//! indépendante avant publication) — extrait de `scene_ops.rs` le même jour, ce fichier
//! ayant atteint le plafond BLOQUANT de 500 lignes une fois le troisième passage de
//! relecture appliqué. Pure séparation de fichier, aucun changement de comportement au
//! moment de l'extraction.

use hikari_protocol::EngineMessage;

use crate::{camera, emit, App, MASK_RETRY_MAX_AGE};

impl App {
    /// Retente les masques mis en attente parce que leur caméra n'avait pas encore rendu
    /// d'image (2026-09-09, relecture indépendante avant publication) — appelé à chaque
    /// tick tant que `mask_retry_pending` n'est pas vide, voir `event_loop::about_to_wait`.
    /// Relit l'état VOULU à chaque tentative, jamais celui qui a échoué la première fois :
    /// l'utilisateur a pu régler autre chose pendant l'attente.
    ///
    /// Garde-fous, cumulés sur trois passages de relecture indépendante :
    /// - **une entrée dont l'appareil a disparu est retirée EN PREMIER, quelle que soit sa
    ///   scène** — sinon une entrée orpheline (`release_unused_cameras`, une scène supprimée
    ///   ailleurs) ne se nettoyait que si sa scène redevenait active, ce qui pouvait ne
    ///   jamais arriver.
    /// - **une scène en attente qui n'est PAS celle actuellement en direct n'est jamais
    ///   appliquée maintenant** — le filtre de masque est partagé par appareil entre toutes
    ///   les scènes qui le montrent ; l'appliquer pour une scène non live écrirait sur ce
    ///   que la scène RÉELLEMENT à l'antenne affiche (`hikari_protocol::decide_mask_retry`).
    /// - **une attente dont l'ÂGE dépasse `MASK_RETRY_MAX_AGE` est abandonnée avec un
    ///   message** — sur l'âge, jamais sur un compteur de tentatives actives : sans ça, une
    ///   entrée dont la scène ne redevenait jamais active n'était jamais comptée, donc
    ///   jamais plafonnée, et l'attente ne se terminait jamais (défaut du second passage).
    pub(crate) fn retry_pending_masks(&mut self) {
        let mut changed = false;
        let mut gave_up: Vec<String> = Vec::new();
        if let Some(obs) = &mut self.obs {
            if obs.mask_retry_pending.is_empty() {
                return;
            }
            let active_scene = obs.active_scene.clone();
            let pending: Vec<((String, String), std::time::Instant)> = obs
                .mask_retry_pending
                .iter()
                .map(|(key, inserted_at)| (key.clone(), *inserted_at))
                .collect();
            for (key, inserted_at) in pending {
                let (scene, device_id) = &key;
                let Some(opened) = obs.cameras.get(device_id) else {
                    // L'appareil a disparu pendant l'attente (retiré, ou fermé par
                    // `release_unused_cameras` après la suppression d'une autre scène) :
                    // plus rien à réessayer, quelle que soit la scène de cette entrée.
                    obs.mask_retry_pending.remove(&key);
                    changed = true;
                    continue;
                };
                let name = opened.name.clone();
                let decision = hikari_protocol::decide_mask_retry(
                    scene == &active_scene,
                    inserted_at.elapsed(),
                    MASK_RETRY_MAX_AGE,
                );
                match decision {
                    hikari_protocol::MaskRetryDecision::Skip => continue,
                    hikari_protocol::MaskRetryDecision::GiveUp => {
                        obs.mask_retry_pending.remove(&key);
                        gave_up.push(name);
                        changed = true;
                        continue;
                    }
                    hikari_protocol::MaskRetryDecision::Attempt => {}
                }
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
                    // Pas encore prête : l'entrée reste, avec son horodatage D'ORIGINE
                    // (jamais réinitialisé ici) — c'est ce qui fait avancer son âge vers le
                    // plafond d'un tick à l'autre.
                    Ok(camera::MaskApplyOutcome::CameraNotReadyYet) => {}
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
        for name in gave_up {
            emit(&EngineMessage::Error {
                message: format!(
                    "La caméra « {name} » n'a pas démarré après plusieurs secondes — son masque n'a pas pu être posé. Elle est peut-être utilisée par une autre application."
                ),
            });
        }
        if changed {
            self.emit_scene_list();
        }
    }
}
