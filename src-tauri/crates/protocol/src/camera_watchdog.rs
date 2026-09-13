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
    /// Aucune image encore décodée — une caméra qui vient de s'ouvrir, jamais un échec.
    NotStarted,
    /// Même horodatage qu'au tick précédent : aucune image neuve n'est arrivée.
    Stale,
}

/// Compare l'horodatage précédent au courant. `previous` est `None` au tout premier
/// contrôle d'une caméra neuve — jamais confondu avec une caméra figée, qui elle a DÉJÀ
/// produit un horodatage identique deux fois de suite.
pub fn sample_frame(previous: Option<u64>, current: Option<u64>) -> FrameSample {
    match current {
        None => FrameSample::NotStarted,
        Some(ts) if previous == Some(ts) => FrameSample::Stale,
        Some(_) => FrameSample::Fresh,
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
    fn should_report_not_started_when_a_running_camera_stops_reporting_frames_at_all() {
        // Un cas distinct de figé : plus AUCUNE image, pas la même en boucle. Un pilote qui
        // se déconnecte proprement peut cesser d'en rendre plutôt que de répéter la
        // dernière — ce n'est ni une preuve de vie ni un gel confirmé, donc ça ne compte
        // jamais comme un échec (le compteur reste à zéro, voir la doc de
        // `STALE_SAMPLES_BEFORE_RESTART`).
        assert_eq!(sample_frame(Some(100), None), FrameSample::NotStarted);
    }
}
