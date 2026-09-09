//! La décision pure derrière la nouvelle tentative d'un masque de caméra (2026-09-09,
//! relecture indépendante avant publication — QUATRIÈME passage). Extraite ici, sans aucune
//! dépendance libobs, précisément parce que le crate `engine` n'a AUCUN test (`test =
//! false`, voir CLAUDE.md « hardware floor ») — une machine à états qui a déjà produit
//! plusieurs verdicts FAIL ne peut être fiabilisée qu'en devenant testable, donc en
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
    /// Abandonne SANS RIEN DIRE : le plafond est dépassé, mais aucune tentative réelle n'a
    /// jamais eu lieu (sa scène n'a jamais été à l'antenne pendant l'attente). Accuser la
    /// caméra ici serait un mensonge — elle n'a jamais été mise à l'épreuve. `apply_
    /// scene_filter_state` la remettra en file, avec une horloge neuve, la prochaine fois
    /// que sa scène redevient active (2026-09-09, quatrième passage : le défaut trouvé au
    /// troisième — un message d'erreur accusant une caméra jamais testée).
    Abandon,
    /// Abandonne AVEC un message : sa scène ÉTAIT à l'antenne, la caméra a vraiment été
    /// tentée, et elle n'a toujours pas produit d'image après le plafond. Un vrai échec,
    /// qui mérite un vrai message.
    GiveUp,
}

/// Décide du sort d'une entrée en attente, sans connaître libobs ni l'horloge réelle —
/// `age` est déjà calculé par l'appelant (`Instant::elapsed()`).
///
/// Le plafond porte sur l'ÂGE de l'attente, jamais sur un compteur de tentatives actives
/// (défaut du second passage : changer de scène remettait un tel compteur à zéro à chaque
/// bascule, et une entrée dont la scène n'était jamais active n'était jamais comptée —
/// l'attente ne se terminait donc jamais). Mais l'âge seul ne suffit pas à décider s'il faut
/// PRÉVENIR l'utilisateur (troisième passage) : dépasser le plafond sans que la scène ait
/// jamais été active n'est la faute de personne, et ne doit produire aucun message — la
/// scène est vérifiée EN PREMIER, avant l'âge, précisément pour distinguer les deux sorties.
pub fn decide_mask_retry(
    is_active_scene: bool,
    age: Duration,
    max_age: Duration,
) -> MaskRetryDecision {
    if !is_active_scene {
        return if age >= max_age {
            MaskRetryDecision::Abandon
        } else {
            MaskRetryDecision::Skip
        };
    }
    if age >= max_age {
        return MaskRetryDecision::GiveUp;
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
    fn should_give_up_with_a_message_once_the_ceiling_is_reached_on_the_live_scene() {
        // Ici seulement un message est mérité : la scène était à l'antenne, la caméra a été
        // réellement tentée et a réellement échoué à démarrer.
        assert_eq!(decide_mask_retry(true, MAX, MAX), MaskRetryDecision::GiveUp);
    }

    #[test]
    fn should_abandon_silently_a_scene_that_was_never_live_once_the_ceiling_is_reached() {
        // Le défaut du quatrième passage : sans cette distinction, une entrée jamais tentée
        // (sa scène n'a jamais été à l'antenne) recevait le même message accusateur qu'une
        // caméra réellement en panne — un mensonge pendant un direct.
        assert_eq!(
            decide_mask_retry(false, MAX, MAX),
            MaskRetryDecision::Abandon
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
    fn should_abandon_silently_past_the_ceiling_not_only_exactly_at_it() {
        assert_eq!(
            decide_mask_retry(false, MAX + Duration::from_secs(1), MAX),
            MaskRetryDecision::Abandon
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
