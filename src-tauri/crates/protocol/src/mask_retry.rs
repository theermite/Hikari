//! La décision pure derrière la nouvelle tentative d'un masque de caméra (2026-09-09,
//! relecture indépendante avant publication, TROISIÈME passage — deuxième FAIL de suite sur
//! la même famille de défaut : une attente qui ne se termine jamais). Extraite ici, sans
//! aucune dépendance libobs, précisément parce que le crate `engine` n'a AUCUN test
//! (`test = false`, voir CLAUDE.md « hardware floor ») — la logique qui a produit deux
//! verdicts FAIL d'affilée ne peut être fiabilisée qu'en devenant testable, donc en
//! quittant ce crate.

use std::time::Duration;

/// Ce que fait `retry_pending_masks` pour UNE entrée en attente, à CE tick.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MaskRetryDecision {
    /// Tente de poser le masque maintenant : sa scène est celle réellement à l'antenne, et
    /// l'attente n'a pas dépassé le plafond.
    Attempt,
    /// Ne touche à rien ce tick-ci : sa scène n'est pas à l'antenne. Le filtre étant PARTAGÉ
    /// par appareil entre toutes les scènes qui le montrent, y toucher maintenant écrirait
    /// sur ce que la scène en direct affiche réellement — défaut fermé au second passage.
    Skip,
    /// Abandonne : l'attente dépasse le plafond. L'appelant retire l'entrée et prévient
    /// l'utilisateur au lieu de la laisser attendre pour toujours en silence.
    GiveUp,
}

/// Décide du sort d'une entrée en attente, sans connaître libobs ni l'horloge réelle —
/// `age` est déjà calculé par l'appelant (`Instant::elapsed()`).
///
/// Le plafond porte sur l'ÂGE de l'attente, jamais sur un compteur de tentatives actives
/// (défaut du second passage : changer de scène remettait un tel compteur à zéro à chaque
/// bascule, et une entrée dont la scène n'était jamais active n'était jamais comptée —
/// l'attente ne se terminait donc jamais). L'âge, lui, avance que la scène soit active ou
/// non : une entrée abandonnée finit TOUJOURS par l'être, quel que soit le comportement de
/// l'utilisateur entre-temps.
pub fn decide_mask_retry(
    is_active_scene: bool,
    age: Duration,
    max_age: Duration,
) -> MaskRetryDecision {
    if age >= max_age {
        return MaskRetryDecision::GiveUp;
    }
    if !is_active_scene {
        return MaskRetryDecision::Skip;
    }
    MaskRetryDecision::Attempt
}

#[cfg(test)]
mod tests {
    use super::*;

    const MAX: Duration = Duration::from_secs(10);

    #[test]
    fn should_attempt_when_the_scene_is_live_and_the_wait_is_fresh() {
        assert_eq!(
            decide_mask_retry(true, Duration::from_secs(1), MAX),
            MaskRetryDecision::Attempt
        );
    }

    #[test]
    fn should_skip_when_the_scene_is_not_live_but_the_wait_is_still_fresh() {
        assert_eq!(
            decide_mask_retry(false, Duration::from_secs(1), MAX),
            MaskRetryDecision::Skip
        );
    }

    #[test]
    fn should_give_up_once_the_ceiling_is_reached_even_on_the_live_scene() {
        assert_eq!(decide_mask_retry(true, MAX, MAX), MaskRetryDecision::GiveUp);
    }

    #[test]
    fn should_give_up_a_scene_that_was_never_live_once_the_ceiling_is_reached() {
        // Le défaut fermé ici : sans ce cas, une scène jamais réactivée ne voyait jamais son
        // compteur progresser — l'ancien plafond, posé sur les tentatives actives, ne se
        // déclenchait donc jamais pour elle.
        assert_eq!(
            decide_mask_retry(false, MAX, MAX),
            MaskRetryDecision::GiveUp
        );
    }

    #[test]
    fn should_give_up_past_the_ceiling_not_only_exactly_at_it() {
        assert_eq!(
            decide_mask_retry(true, MAX + Duration::from_secs(1), MAX),
            MaskRetryDecision::GiveUp
        );
    }

    #[test]
    fn should_not_be_affected_by_switching_scenes_back_and_forth() {
        // L'âge ne dépend que du temps écoulé, jamais de la séquence active/inactive — la
        // même entrée, retentée en alternance active/inactive, ne redémarre pas son horloge.
        let mid = Duration::from_secs(5);
        assert_eq!(
            decide_mask_retry(true, mid, MAX),
            MaskRetryDecision::Attempt
        );
        assert_eq!(decide_mask_retry(false, mid, MAX), MaskRetryDecision::Skip);
    }
}
