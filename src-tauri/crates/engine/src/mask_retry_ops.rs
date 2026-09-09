//! La nouvelle tentative d'un masque de caméra pas encore posé (2026-09-09, relecture
//! indépendante avant publication) — extrait de `scene_ops.rs` le même jour, ce fichier
//! ayant atteint le plafond BLOQUANT de 500 lignes une fois le troisième passage de
//! relecture appliqué. Pure séparation de fichier, aucun changement de comportement au
//! moment de l'extraction.

use hikari_protocol::EngineMessage;

use crate::{camera, emit, App, MASK_RETRY_MAX_AGE};

/// Ce qu'on sait d'une attente de masque en cours (2026-09-09, relecture indépendante avant
/// publication, SEPTIÈME passage) — l'âge de l'attente ET le dernier échantillon de taille
/// lu sur la caméra, pour exiger DEUX lectures identiques de suite avant de faire confiance
/// à sa géométrie (voir `hikari_protocol::confirm_camera_size`). Sans ce deuxième
/// échantillon, une caméra relancée pouvait annoncer une taille non nulle mais PÉRIMÉE
/// (celle d'avant la relance) et voir son masque posé une fois pour toutes sur la mauvaise
/// proportion.
// Jamais `Copy` (2026-09-10, relecture indépendante avant publication, huitième passage) :
// un type dont un champ EST FAIT pour être muté en place (`last_sampled_size`) ne doit
// jamais pouvoir être copié en silence — une future écriture sur une copie au lieu de
// l'entrée réelle de la table compilerait sans avertissement et perdrait l'échantillon.
#[derive(Debug, Clone)]
pub(crate) struct MaskWait {
    pub(crate) inserted_at: std::time::Instant,
    pub(crate) last_sampled_size: Option<(u32, u32)>,
}

impl MaskWait {
    pub(crate) fn new() -> Self {
        Self {
            inserted_at: std::time::Instant::now(),
            last_sampled_size: None,
        }
    }
}

impl App {
    /// Retente les masques mis en attente parce que leur caméra n'avait pas encore rendu
    /// d'image, ou dont la taille lue n'était pas encore confirmée (2026-09-09, relecture
    /// indépendante avant publication) — appelé à chaque tick tant que `mask_retry_pending`
    /// n'est pas vide, voir `event_loop::about_to_wait`. Relit l'état VOULU à chaque
    /// tentative, jamais celui qui a échoué la première fois : l'utilisateur a pu régler
    /// autre chose pendant l'attente.
    ///
    /// Garde-fous, cumulés sur sept passages de relecture indépendante :
    /// - **une entrée dont l'appareil a disparu est retirée EN PREMIER, quelle que soit sa
    ///   scène** — sinon une entrée orpheline (`release_unused_cameras`, une scène supprimée
    ///   ailleurs) ne se nettoyait que si sa scène redevenait active, ce qui pouvait ne
    ///   jamais arriver.
    /// - **une scène en attente qui n'est PAS celle actuellement en direct n'est jamais
    ///   appliquée maintenant** — le filtre de masque est partagé par appareil entre toutes
    ///   les scènes qui le montrent (`hikari_protocol::decide_mask_retry`).
    /// - **une attente dont l'ÂGE dépasse `MASK_RETRY_MAX_AGE` se termine toujours**, sur
    ///   l'âge, jamais sur un compteur de tentatives actives.
    /// - **un abandon ne parle QUE si la caméra a réellement été mise à l'épreuve** — sinon
    ///   retrait silencieux (`MaskRetryDecision::Abandon`), jamais un message accusateur.
    /// - **une taille non nulle n'est jamais appliquée sur une seule lecture** — deux
    ///   lectures identiques de suite sont exigées (`hikari_protocol::confirm_camera_size`)
    ///   avant de dessiner et poser le masque, pour ne jamais figer une géométrie périmée
    ///   après une relance.
    pub(crate) fn retry_pending_masks(&mut self) {
        let mut changed = false;
        let mut gave_up: Vec<String> = Vec::new();
        if let Some(obs) = &mut self.obs {
            if obs.mask_retry_pending.is_empty() {
                return;
            }
            let active_scene = obs.active_scene.clone();
            let pending: Vec<((String, String), MaskWait)> = obs
                .mask_retry_pending
                .iter()
                .map(|(key, wait)| (key.clone(), wait.clone()))
                .collect();
            for (key, wait) in pending {
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
                    wait.inserted_at.elapsed(),
                    MASK_RETRY_MAX_AGE,
                );
                match decision {
                    hikari_protocol::MaskRetryDecision::Skip => continue,
                    // Jamais tentée : rien à reprocher à la caméra, rien à dire.
                    hikari_protocol::MaskRetryDecision::Abandon => {
                        obs.mask_retry_pending.remove(&key);
                        changed = true;
                        continue;
                    }
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
                match camera::set_mask_shape(
                    &opened.filters.mask,
                    &opened.source,
                    mask_shape,
                    wait.last_sampled_size,
                ) {
                    Ok(camera::MaskApplyOutcome::Applied) => {
                        obs.mask_retry_pending.remove(&key);
                        changed = true;
                    }
                    // Pas encore prête : l'entrée reste, avec son horodatage D'ORIGINE
                    // (jamais réinitialisé ici) — c'est ce qui fait avancer son âge vers le
                    // plafond d'un tick à l'autre.
                    Ok(camera::MaskApplyOutcome::CameraNotReadyYet) => {}
                    // Taille lue, mais pas encore identique à la précédente — mémorise
                    // l'échantillon pour la comparaison du prochain tick, sans toucher à
                    // l'horodatage d'origine.
                    Ok(camera::MaskApplyOutcome::SizeUnconfirmed { sampled }) => {
                        if let Some(entry) = obs.mask_retry_pending.get_mut(&key) {
                            entry.last_sampled_size = Some(sampled);
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
