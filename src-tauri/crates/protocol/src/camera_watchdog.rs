//! La décision pure derrière la caméra qui décroche (2026-09-13). Jay, pendant un direct de
//! 1 h 51 (2026-09-07) : « ma caméra s'est arrêtée de fonctionner, elle a figé ; j'ai dû la
//! supprimer de la scène et la remettre ». `camera::restart_camera` répare déjà le geste —
//! ce module décide QUAND le déclencher tout seul, sans que Jay ait à remarquer l'image
//! figée pendant qu'il est en direct.
//!
//! Extrait dans ce crate sans dépendance libobs, même raison que `mask_retry` : le crate
//! `engine` n'a aucun test (`test = false`), donc une décision qui mérite d'être fiabilisée
//! doit en sortir pour devenir testable.

/// Ce qu'un contrôle de santé a trouvé pour une caméra, à CE tick — comparaison entre
/// l'horodatage de sa dernière image lue au tick précédent et celui lu maintenant
/// (`obs_source_get_frame`, le seul signal que libobs donne pour « une image neuve est
/// arrivée »).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameSample {
    /// L'horodatage a changé depuis le dernier contrôle : la caméra produit des images.
    Fresh,
    /// Aucune image encore décodée, et aucune ne l'a jamais été — une caméra qui vient de
    /// s'ouvrir, jamais un échec.
    NotStarted,
    /// Même horodatage qu'au tick précédent, OU plus aucune image du tout après en avoir
    /// déjà rendu — les deux visages du même décrochage.
    Stale,
}

/// Compare l'horodatage précédent au courant. `previous` est `None` au tout premier
/// contrôle d'une caméra neuve — jamais confondu avec une caméra figée, qui elle a DÉJÀ
/// produit un horodatage identique deux fois de suite.
///
/// CORRIGÉ (2026-09-13, débranchement réel testé par Jay) : un `None` après un `Some` DOIT
/// compter comme figé, jamais comme « pas encore démarrée ». Un débranchement physique fait
/// cesser `obs_source_get_frame` de rendre quoi que ce soit — il ne répète pas la dernière
/// image, il n'en rend plus AUCUNE. La version précédente ne comptait que le cas « même
/// horodatage en boucle » (une caméra qui gèle sans se déconnecter), et le test réel de Jay
/// n'a jamais déclenché la relance automatique : il a dû cliquer le bouton à la main.
pub fn sample_frame(previous: Option<u64>, current: Option<u64>) -> FrameSample {
    match current {
        Some(ts) if previous == Some(ts) => FrameSample::Stale,
        Some(_) => FrameSample::Fresh,
        None if previous.is_none() => FrameSample::NotStarted,
        None => FrameSample::Stale,
    }
}

/// Combien de lectures `Stale` CONSÉCUTIVES avant de relancer automatiquement la caméra.
///
/// Jay a validé le principe le 2026-09-13 : « je pense que 3 à 6 secondes pour une caméra,
/// c'est ok » — au tick de 3 s (voir `CAMERA_WATCHDOG_TICK` côté moteur), 2 lectures figées
/// de suite couvrent exactement cette fenêtre. Sur l'ÂGE consécutif, jamais sur un compteur
/// qui se remet à zéro à la moindre image parasite — même principe que
/// `mask_retry::decide_mask_retry`, qui compte l'âge plutôt que les tentatives.
pub const STALE_SAMPLES_BEFORE_RESTART: u32 = 2;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_report_not_started_when_no_frame_was_ever_decoded() {
        assert_eq!(sample_frame(None, None), FrameSample::NotStarted);
    }

    #[test]
    fn should_report_fresh_on_the_very_first_decoded_frame() {
        // Le premier horodatage jamais lu n'a rien à comparer — jamais confondu avec figé.
        assert_eq!(sample_frame(None, Some(42)), FrameSample::Fresh);
    }

    #[test]
    fn should_report_fresh_when_the_timestamp_advanced() {
        assert_eq!(sample_frame(Some(100), Some(133)), FrameSample::Fresh);
    }

    #[test]
    fn should_report_stale_when_the_timestamp_repeats() {
        assert_eq!(sample_frame(Some(100), Some(100)), FrameSample::Stale);
    }

    #[test]
    fn should_report_stale_when_a_running_camera_stops_reporting_frames_at_all() {
        // Le cas RÉEL d'un débranchement physique (testé par Jay, 2026-09-13) : plus
        // AUCUNE image, jamais la même en boucle — la première version confondait ça avec
        // « pas encore démarrée » et ne relançait jamais rien.
        assert_eq!(sample_frame(Some(100), None), FrameSample::Stale);
    }

    #[test]
    fn should_report_fresh_when_a_disconnected_camera_starts_producing_frames_again() {
        // Reconnecter l'appareil doit être vu comme une reprise, pas comme un nouveau
        // gel — même si le compteur venait d'atteindre le plafond côté moteur.
        assert_eq!(sample_frame(Some(100), Some(250)), FrameSample::Fresh);
    }
}
