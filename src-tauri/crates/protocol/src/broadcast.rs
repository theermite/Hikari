//! Où diffuser — et le refus de diffuser vers nulle part.
//!
//! Ce que ça règle (Jay, 2026-09-06) : compte Twitch connecté, clic sur « Démarrer »,
//! l'application annonce « en direct »… et rien n'arrive sur Twitch. La cible se repliait
//! en silence sur un serveur local qui n'existe pas.
//!
//! Un repli silencieux vers une adresse invalide est pire qu'un refus : il produit une
//! séance entière que personne ne voit, et on ne l'apprend qu'après. La destination est
//! donc EXIGÉE, et son absence est dite.

/// Pourquoi une diffusion ne peut pas commencer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TargetError {
    /// Aucune destination : aucun compte connecté, ou sa clé n'a pas pu être lue.
    Missing,
    /// Une moitié seulement — un serveur sans clé, ou l'inverse. Diffuser avec l'une des
    /// deux échouerait plus loin, sans dire laquelle manque.
    Incomplete,
}

impl TargetError {
    /// Le message montré à l'utilisateur. En français : il finit sur son écran.
    pub fn message(&self) -> &'static str {
        match self {
            TargetError::Missing => {
                "Aucune destination de diffusion — connecte un compte dans Paramètres."
            }
            TargetError::Incomplete => {
                "Destination de diffusion incomplète — il manque le serveur ou la clé."
            }
        }
    }
}

/// La destination à utiliser, à partir de ce que l'environnement du moteur porte.
///
/// Rend une erreur plutôt qu'un repli : c'est tout l'objet de ce module. Les deux valeurs
/// vides comptent comme absentes — une variable posée à vide est une variable oubliée, pas
/// une intention.
pub fn resolve_target(
    server: Option<&str>,
    key: Option<&str>,
) -> Result<(String, String), TargetError> {
    let server = server.map(str::trim).filter(|value| !value.is_empty());
    let key = key.map(str::trim).filter(|value| !value.is_empty());
    match (server, key) {
        (Some(server), Some(key)) => Ok((server.to_string(), key.to_string())),
        (None, None) => Err(TargetError::Missing),
        _ => Err(TargetError::Incomplete),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_use_the_destination_it_was_given() {
        assert_eq!(
            resolve_target(Some("rtmp://x.example/app"), Some("cle")).unwrap(),
            ("rtmp://x.example/app".to_string(), "cle".to_string())
        );
    }

    #[test]
    fn should_refuse_when_there_is_no_destination_at_all() {
        // LE défaut du 2026-09-06 : la diffusion partait vers un serveur local inexistant,
        // et l'application annonçait « en direct ».
        assert_eq!(resolve_target(None, None), Err(TargetError::Missing));
    }

    #[test]
    fn should_refuse_when_only_half_the_destination_is_there() {
        assert_eq!(
            resolve_target(Some("rtmp://x.example/app"), None),
            Err(TargetError::Incomplete)
        );
        assert_eq!(
            resolve_target(None, Some("cle")),
            Err(TargetError::Incomplete)
        );
    }

    #[test]
    fn should_treat_an_empty_value_as_a_forgotten_one() {
        assert_eq!(
            resolve_target(Some(""), Some("")),
            Err(TargetError::Missing)
        );
        assert_eq!(
            resolve_target(Some("   "), Some("cle")),
            Err(TargetError::Incomplete)
        );
    }

    #[test]
    fn should_say_what_is_missing_in_plain_words() {
        // Ce texte finit sur l'écran de l'utilisateur : il doit dire quoi faire.
        assert!(TargetError::Missing.message().contains("Paramètres"));
        assert!(!TargetError::Missing.message().is_empty());
    }
}
