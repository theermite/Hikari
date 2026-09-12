//! Résout la destination de diffusion du compte connecté — extrait de
//! `engine_lifecycle.rs` (2026-09-12, plafond de 500 lignes dépassé) : un seul sujet,
//! séparable du reste du cycle de vie du moteur (démarrage/arrêt/greffe de l'aperçu).

use crate::accounts::twitch::{self, TWITCH_CLIENT_ID};
use crate::accounts::twitch_stream;
use crate::accounts::vault::{self, Platform, Secret, StoredToken};

/// La destination de diffusion du compte connecté, s'il y en a un.
///
/// Rend `None` sans bruit quand aucun compte n'est connecté : ouvrir Hikari sans compte est
/// un usage normal. Un échec de lecture, lui, est TRACÉ — sinon une clé illisible
/// ressemblerait à une absence de compte, et Jay chercherait au mauvais endroit.
pub(crate) async fn resolve_broadcast_target() -> Option<(String, Secret)> {
    let token = match vault::load(Platform::Twitch) {
        Ok(Some(token)) => token,
        Ok(None) => return None,
        Err(err) => {
            eprintln!("[twitch] coffre illisible ({err}) — diffusion sans destination");
            return None;
        }
    };
    let http = reqwest::Client::new();
    // Un jeton expiré n'est PAS un compte perdu : le coffre garde le jeton de
    // rafraîchissement depuis la connexion. Abandonner ici (ce que faisait la version
    // précédente) demandait à l'utilisateur de se reconnecter à la main toutes les quelques
    // heures, pour une opération que la machine sait faire seule.
    //
    // On ne redemande une connexion QUE si Twitch refuse vraiment le renouvellement —
    // jeton révoqué de son côté, ou réseau injoignable.
    let token = if vault::is_expired(&token, vault::now_unix()) {
        match twitch::refresh(&token, TWITCH_CLIENT_ID, &http).await {
            Ok(renewed) => {
                if let Err(err) = vault::store(Platform::Twitch, &renewed) {
                    // Le renouvellement a marché, l'écriture non : on diffuse quand même
                    // avec le jeton neuf, mais la trace dit pourquoi ça recommencera au
                    // prochain lancement.
                    eprintln!("[twitch] jeton renouvelé mais non rangé ({err})");
                }
                renewed
            }
            Err(err) => {
                eprintln!(
                    "[twitch] renouvellement refusé ({err}) — reconnecte le compte dans Paramètres"
                );
                return None;
            }
        }
    } else {
        token
    };
    match twitch_stream::fetch_target(&http, TWITCH_CLIENT_ID, &token.access_token).await {
        Ok((server, key, nom)) => {
            // Le nom du compte arrive dans la meme reponse que la cle : le ranger ici le
            // remplit pour les comptes connectes AVANT que ce champ n'existe, sans un seul
            // appel reseau supplementaire. Un echec d'ecriture n'empeche pas de diffuser —
            // c'est un confort d'affichage, jamais une condition.
            if let Some(nom) = nom {
                if token.account_name.as_deref() != Some(nom.as_str()) {
                    let renseigne = StoredToken {
                        account_name: Some(nom),
                        ..token
                    };
                    if let Err(err) = vault::store(Platform::Twitch, &renseigne) {
                        eprintln!("[twitch] nom du compte non range ({err})");
                    }
                }
            }
            Some((server, key))
        }
        Err(err) => {
            eprintln!("[twitch] destination illisible ({err})");
            None
        }
    }
}
