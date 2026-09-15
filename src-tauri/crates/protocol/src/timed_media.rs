//! Médias pop-up et bandeaux (F-033/F-034, CDC §3quinquies) — les règles pures qui
//! décident si une source PEUT disparaître d'elle-même, et pendant combien de temps.
//!
//! Ce que le moteur en fait (poser le fichier, programmer le retrait) vit dans le crate
//! `engine`, non testable (lien libobs) — cette logique-ci reste ici pour être vérifiée
//! sans lui.

use crate::sources::SourceKind;

/// Un média pop-up refusé parce que sa famille ne peut pas disparaître d'elle-même — une
/// capture live ou la caméra partagée n'ont pas de fin naturelle, contrairement à un
/// fichier posé pour un temps.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TimedMediaError {
    NotAFile(SourceKind),
}

impl std::fmt::Display for TimedMediaError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TimedMediaError::NotAFile(kind) => write!(
                f,
                "« {kind:?} » n'est pas un média ponctuel — seuls une image ou une vidéo \
                 peuvent disparaître d'elles-mêmes"
            ),
        }
    }
}

/// Whether `kind` peut servir de média pop-up (F-033) : une image ou une vidéo, les deux
/// seules familles qui sont des FICHIERS choisis pour un instant — jamais une capture live
/// (rien à "finir") ni la caméra, source physique partagée entre scènes (B10, 2026-09-15).
pub fn validate_timed_media_kind(kind: SourceKind) -> Result<(), TimedMediaError> {
    if kind.is_file() {
        Ok(())
    } else {
        Err(TimedMediaError::NotAFile(kind))
    }
}

/// Plancher d'affichage d'un média pop-up, en millisecondes : en dessous, il disparaît
/// avant qu'un spectateur ait pu le voir — aucun usage distinguable de « rien du tout ».
pub const TIMED_MEDIA_MIN_DURATION_MS: u64 = 500;

/// Plafond d'affichage : au-delà, ce n'est plus un média « ponctuel » (F-033) mais un
/// habillage permanent (F-020), qui a déjà son propre chemin, sans expiration forcée.
pub const TIMED_MEDIA_MAX_DURATION_MS: u64 = 5 * 60 * 1000;

/// Une durée de média pop-up utilisable — jamais une valeur tapée de travers qui
/// disparaîtrait trop vite pour être vue, ou resterait aussi longtemps qu'une source
/// permanente.
pub fn clamp_timed_media_duration_ms(ms: u64) -> u64 {
    ms.clamp(TIMED_MEDIA_MIN_DURATION_MS, TIMED_MEDIA_MAX_DURATION_MS)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_accept_image_and_video_as_timed_media() {
        assert_eq!(validate_timed_media_kind(SourceKind::Image), Ok(()));
        assert_eq!(validate_timed_media_kind(SourceKind::Video), Ok(()));
    }

    #[test]
    fn should_reject_live_captures_and_camera_as_timed_media() {
        for kind in [
            SourceKind::Game,
            SourceKind::Window,
            SourceKind::Monitor,
            SourceKind::Camera,
            SourceKind::Text,
        ] {
            assert_eq!(
                validate_timed_media_kind(kind),
                Err(TimedMediaError::NotAFile(kind))
            );
        }
    }

    #[test]
    fn should_raise_a_duration_below_the_floor() {
        assert_eq!(clamp_timed_media_duration_ms(0), TIMED_MEDIA_MIN_DURATION_MS);
        assert_eq!(
            clamp_timed_media_duration_ms(499),
            TIMED_MEDIA_MIN_DURATION_MS
        );
    }

    #[test]
    fn should_cap_a_duration_above_the_ceiling() {
        assert_eq!(
            clamp_timed_media_duration_ms(u64::MAX),
            TIMED_MEDIA_MAX_DURATION_MS
        );
    }

    #[test]
    fn should_keep_a_duration_already_inside_bounds() {
        assert_eq!(clamp_timed_media_duration_ms(5_000), 5_000);
    }
}
