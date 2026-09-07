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
    pub twitch: Connection,
    pub youtube: Connection,
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

/// L'etat d'un compte, tel qu'il doit etre DIT a l'utilisateur.
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Connection {
    /// Aucun jeton range : jamais connecte, ou deconnecte.
    Absent,
    /// Utilisable — maintenant, ou apres un renouvellement que la machine sait faire seule.
    Live,
    /// Un jeton existe, il est perime, et rien ici ne sait le renouveler. Le compte est
    /// mort : le dire « connecte » enverrait l'utilisateur diffuser vers un refus.
    ARenouveler,
}

/// Un compte est-il utilisable, et si non, pourquoi ?
///
/// `renewable` est passe et non devine : Twitch sait se renouveler tout seul
/// (`twitch::refresh`), YouTube non — pas encore. Un jeton YouTube perime affichait
/// pourtant « connecte » (Jay, 2026-09-07 : « YouTube dit que je suis connecte alors que
/// je ne me suis connecte a rien du tout »). Un mensonge d'affichage sur un compte coute
/// une diffusion qui ne part pas.
///
/// Fonction pure, prise a part du coffre : elle porte la seule DECISION du sujet, et le
/// coffre systeme ne se prete pas a un test automatique.
pub fn connection_state(
    stored: Option<&vault::StoredToken>,
    now: u64,
    renewable: bool,
) -> Connection {
    match stored {
        None => Connection::Absent,
        Some(token) if vault::is_expired(token, now) && !renewable => Connection::ARenouveler,
        Some(_) => Connection::Live,
    }
}

/// Lit l'etat des deux comptes dans le coffre.
///
/// Une lecture qui echoue est tracee et compte comme « non connecte » : un coffre illisible
/// n'est pas un compte connecte, et le silence ferait chercher au mauvais endroit.
pub fn read_status() -> AccountStatus {
    let now = vault::now_unix();
    // `true` pour Twitch, `false` pour YouTube : c'est la realite du code, pas une
    // preference. Le jour ou YouTube saura se renouveler, ce booleen passe a `true` et
    // l'affichage suit — un seul endroit a changer.
    let (twitch, twitch_account) = read_one(vault::Platform::Twitch, now, true);
    let (youtube, youtube_account) = read_one(vault::Platform::YouTube, now, false);
    AccountStatus { twitch, youtube, twitch_account, youtube_account }
}

fn read_one(
    platform: vault::Platform,
    now: u64,
    renewable: bool,
) -> (Connection, Option<String>) {
    match vault::load(platform) {
        Ok(stored) => (
            connection_state(stored.as_ref(), now, renewable),
            stored.and_then(|t| t.account_name),
        ),
        Err(err) => {
            eprintln!("[comptes] coffre illisible pour {platform:?} ({err})");
            (Connection::Absent, None)
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
    fn should_report_absent_when_no_token_is_stored() {
        assert_eq!(connection_state(None, 100, true), Connection::Absent);
    }

    #[test]
    fn should_report_live_when_a_valid_token_is_stored() {
        assert_eq!(connection_state(Some(&token(200)), 100, false), Connection::Live);
    }

    #[test]
    fn should_report_live_when_an_expired_token_can_renew_itself() {
        // Twitch : un jeton perime se renouvelle tout seul. L'annoncer deconnecte
        // enverrait l'utilisateur refaire un geste dont la machine n'a pas besoin.
        assert_eq!(connection_state(Some(&token(50)), 100, true), Connection::Live);
    }

    #[test]
    fn should_ask_for_a_new_connection_when_an_expired_token_cannot_renew() {
        // YouTube, 2026-09-07 : un jeton de juillet affichait « connecte » alors que rien
        // ne sait le renouveler. Jay : « YouTube dit que je suis connecte alors que je ne
        // me suis connecte a rien du tout. » Diffuser depuis la aurait echoue sans raison
        // lisible.
        assert_eq!(connection_state(Some(&token(50)), 100, false), Connection::ARenouveler);
    }
}
