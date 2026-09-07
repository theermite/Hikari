//! Ce que le MOTEUR OBS écrit dans son propre journal, et que l'utilisateur doit voir.
//!
//! Le moteur mêle deux choses sur la même sortie : nos messages de protocole (du JSON) et
//! le journal de `libobs` (du texte). Tout ce qui n'était pas du JSON était jeté dans la
//! console de développement — donc invisible pour qui utilise l'application.
//!
//! C'est ainsi qu'une troisième caméra a pu rester noire sans un mot chez Jay le
//! 2026-09-06, alors que `libobs` avait écrit la raison exacte :
//! « A camera interface doesn't have the desired bandwidth for data transfer. »
//! La cause était sur le disque depuis le début ; rien ne la remontait.

/// La source que l'on crée puis détruit juste pour INTERROGER les appareils disponibles.
/// Ses échecs sont attendus — c'est ainsi qu'on découvre ce qui ne répond pas.
const PROBE_SOURCE: &str = "hikari-camera-probe";

/// Ce qu'il faut montrer d'une ligne de journal du moteur, s'il y a lieu.
///
/// Rendu `None` pour tout ce qui est du bruit : `libobs` écrit des centaines de lignes
/// d'information par lancement, et les remonter toutes ferait un bandeau que personne ne
/// lirait — donc un bandeau qui ne dirait plus rien quand ça compte.
///
/// Retenu : ce que `libobs` classe lui-même en erreur, et les avertissements qui annoncent
/// un ÉCHEC. Un avertissement de confort (un horodatage audio qui dérive) ne concerne pas
/// l'utilisateur.
pub fn user_visible_engine_log(line: &str) -> Option<String> {
    let trimmed = line.trim();
    // La sonde échoue par construction : elle demande à chaque appareil s'il répond.
    if trimmed.contains(PROBE_SOURCE) {
        return None;
    }
    let (marker, rest) = match trimmed.strip_prefix("[Error]") {
        Some(rest) => ("[Error]", rest),
        None => ("[Warning]", trimmed.strip_prefix("[Warning]")?),
    };
    let text = rest.trim();
    if text.is_empty() {
        return None;
    }
    let lowered = text.to_lowercase();
    // Un avertissement n'est montré que s'il annonce un échec — sinon c'est du confort.
    if marker == "[Warning]" && !lowered.contains("failed") {
        return None;
    }
    // Faire l'inventaire des appareils, c'est demander « qui répond ? ». Une absence de
    // réponse EST la réponse, pas une panne — même nature que la sonde caméra ci-dessus.
    // Ces lignes arrivent en rafale et remplissaient le bandeau de Jay le 2026-09-06.
    if lowered.contains("enumerate") {
        return None;
    }
    // « (null) » est littéralement le message manquant : le greffon a signalé une erreur
    // sans dire laquelle. L'afficher alarme sans rien apprendre.
    if lowered.contains("(null)") {
        return None;
    }
    Some(text.to_string())
}

/// Faut-il montrer cette ligne, compte tenu de l'ETAT du moteur ?
///
/// Trois phases, et non deux. Le demarrage etait deja silencieux ; l'ARRET ne l'etait pas,
/// et c'est ce qui a produit « Le moteur a refuse : Number of memory leaks: 10 » chez Jay
/// le 2026-09-07, juste apres « OBS context shutdown ». Un moteur qui s'eteint ne refuse
/// rien : il fait son inventaire de fin de vie, et ce decompte s'adresse a celui qui
/// developpe, jamais a celui qui diffuse.
///
/// Le cout d'un faux bandeau n'est pas le bandeau : c'est qu'on cesse de les lire.
pub fn engine_log_to_show(line: &str, initialized: bool, stopping: bool) -> Option<String> {
    if !initialized || stopping {
        return None;
    }
    user_visible_engine_log(line)
}

#[cfg(test)]
mod phase_tests {
    use super::*;

    const ARRET: &str = "[Error] Number of memory leaks: 10";
    const VRAI_REFUS: &str =
        "[Error] DShow: Run failed (0x800718CF): A camera interface doesn't have the desired bandwidth";

    #[test]
    fn should_stay_silent_while_the_engine_is_shutting_down() {
        assert_eq!(engine_log_to_show(ARRET, true, true), None);
    }

    #[test]
    fn should_stay_silent_before_the_engine_is_ready() {
        assert_eq!(engine_log_to_show(VRAI_REFUS, false, false), None);
    }

    #[test]
    fn should_speak_a_real_failure_while_the_engine_runs() {
        assert!(engine_log_to_show(VRAI_REFUS, true, false).is_some());
    }

    #[test]
    fn should_stay_silent_on_a_shutdown_diagnostic_even_when_it_says_error() {
        // La ligne qui a menti a Jay. Elle porte bien le mot « Error » de `libobs`, et
        // n'est pourtant l'annonce d'aucun refus : c'est un decompte de fin de vie.
        assert_eq!(engine_log_to_show(ARRET, true, true), None);
    }
}
