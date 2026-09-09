//! Confirme que la taille annoncée par une caméra est bien celle qui produit vraiment ses
//! images, avant de s'en servir pour dessiner un masque (2026-09-09, relecture indépendante
//! avant publication, SEPTIÈME passage).
//!
//! Vérifié dans le code source réel de libobs et de win-dshow (2026-09-09, branche master) :
//! `obs_source_get_width` pour une source vidéo asynchrone rend la taille de la DERNIÈRE
//! image reçue, jamais 0, tant que la source n'a pas explicitement signalé « plus d'image »
//! (`obs_source_output_video2(source, nullptr)`, qui met `async_active` à faux). Relancer une
//! caméra (`obs_source_update` → `DShowInput::Activate`) ne déclenche PAS ce signal — seul un
//! vrai arrêt (`Deactivate`) le fait. Une lecture juste après une relance peut donc rendre une
//! taille NON NULLE mais PÉRIMÉE, celle d'avant la relance, tant qu'aucune image de la
//! nouvelle configuration n'est encore arrivée.

/// Ce qu'une lecture de taille permet de conclure, comparée à la précédente.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SizeConfirmation {
    /// La caméra n'a encore produit aucune image (taille nulle) — cas d'une source qui vient
    /// tout juste de s'ouvrir, jamais vue avant.
    NotYetKnown,
    /// Une taille non nulle a été lue, mais soit c'est la toute première lecture, soit elle
    /// diffère de la précédente. Ne pas encore en dessiner un masque — une deuxième lecture
    /// IDENTIQUE est nécessaire avant de faire confiance à la géométrie.
    Unconfirmed,
    /// La même taille a été lue deux fois de suite — assez stable pour dessiner le masque.
    Confirmed,
}

/// `previous` est le dernier échantillon retenu pour cette caméra (`None` si aucun n'existe
/// encore), `current` la taille lue maintenant. Zéro l'emporte toujours sur toute comparaison
/// — une taille nulle n'est jamais confirmée, quel que soit `previous`.
pub fn confirm_camera_size(previous: Option<(u32, u32)>, current: (u32, u32)) -> SizeConfirmation {
    if current == (0, 0) {
        return SizeConfirmation::NotYetKnown;
    }
    match previous {
        Some(previous) if previous == current => SizeConfirmation::Confirmed,
        _ => SizeConfirmation::Unconfirmed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_report_not_yet_known_for_a_zero_size_with_no_previous_sample() {
        assert_eq!(
            confirm_camera_size(None, (0, 0)),
            SizeConfirmation::NotYetKnown
        );
    }

    #[test]
    fn should_report_not_yet_known_for_a_zero_size_even_with_a_previous_sample() {
        // Zéro l'emporte toujours : une caméra qui s'est remise à ne plus rien produire n'est
        // jamais "confirmée" sur la base d'un souvenir périmé.
        assert_eq!(
            confirm_camera_size(Some((640, 480)), (0, 0)),
            SizeConfirmation::NotYetKnown
        );
    }

    #[test]
    fn should_report_unconfirmed_on_the_first_real_sample() {
        assert_eq!(
            confirm_camera_size(None, (640, 480)),
            SizeConfirmation::Unconfirmed
        );
    }

    #[test]
    fn should_report_unconfirmed_when_the_size_changed_since_the_last_sample() {
        // Le cas exact du défaut fermé ici : une relance dont la caméra revient dans une
        // autre définition ne doit jamais être prise pour argent comptant sur une seule
        // lecture.
        assert_eq!(
            confirm_camera_size(Some((640, 480)), (1280, 720)),
            SizeConfirmation::Unconfirmed
        );
    }

    #[test]
    fn should_report_confirmed_when_the_same_size_repeats() {
        assert_eq!(
            confirm_camera_size(Some((640, 480)), (640, 480)),
            SizeConfirmation::Confirmed
        );
    }
}
