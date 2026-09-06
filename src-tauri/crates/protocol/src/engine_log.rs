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
    let (marker, rest) = if let Some(rest) = trimmed.strip_prefix("[Error]") {
        ("[Error]", rest)
    } else if let Some(rest) = trimmed.strip_prefix("[Warning]") {
        ("[Warning]", rest)
    } else {
        return None;
    };
    let text = rest.trim();
    if text.is_empty() {
        return None;
    }
    // Un avertissement n'est montré que s'il annonce un échec — sinon c'est du confort.
    if marker == "[Warning]" && !text.to_lowercase().contains("failed") {
        return None;
    }
    Some(text.to_string())
}
