//! La caméra qui décroche, relancée toute seule (2026-09-13) — Jay, pendant un direct de
//! 1 h 51 (2026-09-07) : « ma caméra s'est arrêtée de fonctionner, elle a figé ; j'ai dû la
//! supprimer de la scène et la remettre ». `camera::restart_camera` répare déjà ce geste,
//! appelé jusqu'ici uniquement à la main (`RestartCamera`) ; ce fichier appelle le même
//! chemin QUAND `hikari_protocol::camera_watchdog` décide qu'une caméra est figée, sur le
//! tick posé par `event_loop::about_to_wait`.

use hikari_protocol::{EngineMessage, FrameSample, STALE_SAMPLES_BEFORE_RESTART};

use crate::{camera, emit, App};

/// Ce qu'on sait de la dernière lecture de santé d'une caméra — le même horodatage lu au
/// tick précédent, et combien de tours de suite il n'a pas bougé.
#[derive(Debug, Clone, Copy)]
pub(crate) struct CameraHealth {
    last_timestamp: Option<u64>,
    stale_streak: u32,
}

impl CameraHealth {
    fn new() -> Self {
        Self {
            last_timestamp: None,
            stale_streak: 0,
        }
    }
}

impl App {
    /// Contrôle chaque caméra OUVERTE (peu importe si une scène la montre, un appareil déjà
    /// figé avant d'être posé mérite le même diagnostic) et relance automatiquement celles
    /// dont l'horodatage n'a pas bougé depuis `STALE_SAMPLES_BEFORE_RESTART` tours de suite.
    ///
    /// Deux passes, même raison que `retry_pending_masks` : la première lit `obs.cameras`
    /// (clone léger, source + nom), la seconde écrit `obs.camera_health` — lire et écrire la
    /// même carte en une seule boucle emprunterait `self.obs` deux fois à la fois.
    pub(crate) fn check_camera_health(&mut self) {
        let Some(obs) = &self.obs else { return };
        if obs.cameras.is_empty() {
            return;
        }
        let snapshot: Vec<(String, String, libobs_wrapper::sources::ObsSourceRef)> = obs
            .cameras
            .iter()
            .map(|(device_id, opened)| {
                (device_id.clone(), opened.name.clone(), opened.source.clone())
            })
            .collect();

        let mut to_restart: Vec<(String, String)> = Vec::new();
        for (device_id, name, source) in snapshot {
            // Une lecture qui échoue (fil OBS indisponible un instant) n'est pas un gel —
            // elle est traitée comme « rien de neuf à dire cette fois-ci », jamais comme une
            // preuve que la caméra est figée.
            let Ok(current) = camera::frame_timestamp(&source) else {
                continue;
            };
            let Some(obs) = &mut self.obs else { return };
            let health = obs
                .camera_health
                .entry(device_id.clone())
                .or_insert_with(CameraHealth::new);
            match hikari_protocol::sample_frame(health.last_timestamp, current) {
                FrameSample::Fresh => {
                    health.last_timestamp = current;
                    health.stale_streak = 0;
                }
                FrameSample::NotStarted => {
                    health.stale_streak = 0;
                }
                FrameSample::Stale => {
                    health.stale_streak += 1;
                    if health.stale_streak >= STALE_SAMPLES_BEFORE_RESTART {
                        health.stale_streak = 0;
                        to_restart.push((device_id, name));
                    }
                }
            }
        }

        for (device_id, name) in to_restart {
            eprintln!("[engine] caméra figée détectée : {name} ({device_id}) — relance automatique");
            self.handle_restart_camera(device_id.clone());
            emit(&EngineMessage::CameraAutoRestarted { device_id, name });
        }
    }
}
