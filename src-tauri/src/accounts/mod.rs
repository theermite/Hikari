//! Account connections (B2b) — OAuth + the local token vault (OS credential store, never
//! a server-side store — see `vault.rs`).
//!
//! `oauth.rs` holds provider-agnostic PKCE mechanics (RFC 7636) — kept for a future
//! platform that uses Authorization Code + PKCE (Google/YouTube supports it for installed
//! apps). `twitch.rs` uses Twitch's Device Code flow instead (PKCE isn't Twitch's model —
//! their Authorization Code flow requires a client secret, unsuitable for an open-source
//! desktop app; verified against Twitch's own docs and the `twitch_oauth2` crate source).

pub mod oauth;
pub mod twitch;
pub mod twitch_stream;
pub mod vault;
pub mod youtube;

/// L'etat d'un compte, tel que l'ecran Comptes doit l'afficher a l'ouverture.
///
/// Il n'existe que deux etats, et c'est voulu : un jeton EXPIRE compte comme connecte,
/// parce que le coffre garde de quoi le renouveler tout seul (`twitch::refresh`). Afficher
/// « deconnecte » sur un compte que la machine sait reparer demanderait a l'utilisateur un
/// geste inutile, et lui ferait croire que sa connexion n'a pas tenu.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct AccountStatus {
    pub twitch: bool,
    pub youtube: bool,
    /// Le nom LISIBLE du compte Twitch connecte, quand on le connait.
    ///
    /// Pourquoi (Jay, 2026-09-07) : il a plusieurs comptes Twitch — un pour les essais
    /// techniques, sans public, et son compte principal. « J'ai besoin de savoir sur quel
    /// compte je suis. » « Connecte » tout court ne repond pas a la question qui compte
    /// juste avant un direct.
    ///
    /// `None` pour un compte connecte AVANT que ce champ n'existe : le nom se remplit tout
    /// seul au prochain demarrage du moteur, sans appel reseau supplementaire.
    pub twitch_account: Option<String>,
    pub youtube_account: Option<String>,
}

/// Un compte est connecte des qu'un jeton est range pour lui, expire ou non.
///
/// Fonction pure, prise a part du coffre : elle porte la seule DECISION du sujet, et le
/// coffre systeme ne se prete pas a un test automatique.
pub fn is_connected(stored: Option<&vault::StoredToken>) -> bool {
    stored.is_some()
}

/// Lit l'etat des deux comptes dans le coffre.
///
/// Une lecture qui echoue est tracee et compte comme « non connecte » : un coffre illisible
/// n'est pas un compte connecte, et le silence ferait chercher au mauvais endroit.
pub fn read_status() -> AccountStatus {
    let (twitch, twitch_account) = read_one(vault::Platform::Twitch);
    let (youtube, youtube_account) = read_one(vault::Platform::YouTube);
    AccountStatus { twitch, youtube, twitch_account, youtube_account }
}

fn read_one(platform: vault::Platform) -> (bool, Option<String>) {
    match vault::load(platform) {
        Ok(stored) => (is_connected(stored.as_ref()), stored.and_then(|t| t.account_name)),
        Err(err) => {
            eprintln!("[comptes] coffre illisible pour {platform:?} ({err})");
            (false, None)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::accounts::vault::{Secret, StoredToken};

    fn token(expires_at: u64) -> StoredToken {
        StoredToken {
            access_token: Secret::new("a"),
            refresh_token: Secret::new("r"),
            expires_at,
            account_name: None,
        }
    }

    #[test]
    fn should_report_disconnected_when_no_token_is_stored() {
        assert!(!is_connected(None));
    }

    #[test]
    fn should_report_connected_when_a_token_is_stored() {
        assert!(is_connected(Some(&token(u64::MAX))));
    }

    #[test]
    fn should_report_connected_even_when_the_token_is_expired() {
        // Le defaut vecu le 2026-09-07 : l'ecran repartait de « pas connecte » a chaque
        // affichage. Un jeton perime se renouvelle tout seul — l'annoncer deconnecte
        // enverrait l'utilisateur refaire un geste dont la machine n'a pas besoin.
        let perime = token(0);
        assert!(vault::is_expired(&perime, vault::now_unix()), "le jeton du test doit etre expire");
        assert!(is_connected(Some(&perime)));
    }
}
