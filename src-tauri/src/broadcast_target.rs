//! Résout la destination de diffusion du compte connecté — extrait de
//! `engine_lifecycle.rs` (2026-09-12, plafond de 500 lignes dépassé) : un seul sujet,
//! séparable du reste du cycle de vie du moteur (démarrage/arrêt/greffe de l'aperçu).

use crate::accounts::twitch::{self, TWITCH_CLIENT_ID};
use crate::accounts::twitch_stream;
use crate::accounts::vault::{self, Platform, Secret, StoredToken};

/// La destination de diffusion du compte connecté, s'il y en a un.
///
/// Rend `None` sans bruit quand aucun compte n'est connecté ou que le renouvellement a
/// échoué : ouvrir Hikari sans compte est un usage normal, et cette partie ne parle qu'au
/// moteur — c'est `chat/mod.rs::chat_connect` qui porte le SEUL chemin où un renouvellement
/// refusé doit être dit à Jay (`chat-error`), voir `accounts::twitch::usable_token`.
pub(crate) async fn resolve_broadcast_target() -> Option<(String, Secret)> {
    let http = reqwest::Client::new();
    let token = match twitch::usable_token(&http).await {
        Ok(Some(token)) => token,
        Ok(None) => return None,
        Err(err) => {
            eprintln!("[twitch] {err} — diffusion sans destination");
            return None;
        }
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
