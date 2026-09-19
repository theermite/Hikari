//! Twitch account connection — Device Code Grant flow (`twitch_oauth2` crate), NOT the
//! Authorization Code flow. Confirmed at the source (dev.twitch.tv's own Authorization
//! Code docs quote `client_id, client_secret, code, grant_type, redirect_uri` as required)
//! that flow needs a client secret — a real problem for Hikari, an OPEN-SOURCE desktop app:
//! anyone can extract a secret embedded in a published binary/repo. The Device Code flow
//! needs only a public `client_id` (Jay confirmed 2026-07-18, cross-checked against the
//! `twitch_oauth2` crate source: `DeviceUserTokenBuilder::set_secret` takes an `Option`,
//! `None` by default — no secret required).
//!
//! Flow: `start_device_flow` gets a `user_code` + `verification_uri` to show in the UI ;
//! the user opens that URL on ANY device/browser, enters the code, authorizes ; Hikari
//! polls (`wait_for_authorization`) until Twitch reports success — no local callback
//! server, no redirect URI to register.
//!
//! Scope: `channel:read:stream_key` (fetches the ingest key) + `chat:read`/`chat:edit`
//! (read and send chat over the same IRC connection) + `moderator:manage:banned_users`
//! (timeout/ban) + `moderator:read:followers`/`channel:read:subscriptions`/`bits:read`
//! (alerts — follow, subscribe/gift/resub, cheer ; raid needs no scope at all) — all from
//! the chat brick, 2026-09-14, verified via the crate's own `Scope` constants, matching
//! Twitch's documented scope strings.

use std::fmt;

use anyhow::{Context, Result};
use twitch_oauth2::tokens::DeviceUserTokenBuilder;
use twitch_oauth2::Scope;

use crate::accounts::vault::{self, merge_refreshed, now_unix, Platform, Secret, StoredToken};

/// Hikari's own Twitch application identity — a "Public" client type (dev.twitch.tv
/// console), registered 2026-07-18 by Jay. A `client_id` identifies the APP, not a user
/// or a secret: Twitch issues no client secret at all for a Public client (verified in
/// the console), so this is safe to commit in a public repo — the same way any published
/// open-source app's OAuth client_id is public (only a client SECRET would need hiding,
/// and this flow has none — see this file's header).
pub const TWITCH_CLIENT_ID: &str = "5ez59v2hqqihv3z13rkyg6m9eoqt41";

/// Why authorization didn't produce a token — distinguished from a generic error so the
/// eventual UI (B4/B-shell) can react differently: `Expired` means "generate a new code",
/// anything else means "something went wrong, try again". The crate's own error enum
/// doesn't expose a clean "user declined" variant (Twitch surfaces that as a parse error
/// on a Twitch-specific message, same mechanism the crate's own `is_pending()` uses) — this
/// keeps only the distinction the crate actually supports, rather than inventing precision
/// it can't back up.
#[derive(Debug)]
pub enum TwitchAuthError {
    /// The user never finished authorizing before the device code's `expires_in` elapsed.
    Expired,
    /// Any other failure (network, Twitch-side error, missing refresh token) — the real
    /// cause is preserved in the message, just not distinguished as its own variant.
    Other(String),
}

impl fmt::Display for TwitchAuthError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TwitchAuthError::Expired => write!(f, "le code a expiré avant l'autorisation"),
            TwitchAuthError::Other(message) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for TwitchAuthError {}

/// The stream key scope, chat read/send, moderation, plus alerts — widened 2026-09-14 for
/// the chat brick (Jay: widening OAuth scope so Hikari can manage chat inside the app is
/// the whole point of owning the cockpit end to end). `ModeratorManageBannedUsers` is the
/// scope the "Ban User" Helix endpoint documents (covers both timeout and permanent ban —
/// verified against the crate's own `Scope` constant and two independent third-party
/// clients mirroring Twitch's reference, `channel:moderate` was NOT the right name here —
/// that scope covers reading moderation events, not acting on them). The three alert
/// scopes each gate one EventSub family (verified against the crate's own `Scope`
/// constants and Twitch's own EventSub subscription-types reference, 2026-09-14):
/// `ModeratorReadFollowers` (`channel.follow`), `ChannelReadSubscriptions`
/// (`channel.subscribe`/`.gift`/`.message`), `BitsRead` (`channel.cheer`). `channel.raid`
/// needs no scope at all — not added here, there is nothing to add.
fn required_scopes() -> Vec<Scope> {
    vec![
        Scope::ChannelReadStreamKey,
        Scope::ChatRead,
        Scope::ChatEdit,
        Scope::ModeratorManageBannedUsers,
        Scope::ModeratorReadFollowers,
        Scope::ChannelReadSubscriptions,
        Scope::BitsRead,
    ]
}

/// What the UI shows the user to complete authorization: a code to type and the page to
/// type it on. Contains no secret — safe to display/log freely.
pub struct DeviceFlowPrompt {
    pub verification_uri: String,
    pub user_code: String,
}

/// Starts the device flow: asks Twitch for a code, returns what to show the user. The
/// returned `DeviceUserTokenBuilder` must be passed to `wait_for_authorization` next — it
/// carries the device code Twitch needs to recognize the follow-up poll requests.
pub async fn start_device_flow(
    client_id: &str,
    http: &reqwest::Client,
) -> Result<(DeviceUserTokenBuilder, DeviceFlowPrompt)> {
    let mut builder = DeviceUserTokenBuilder::new(client_id.to_string(), required_scopes());
    let code = builder
        .start(http)
        .await
        .context("démarrage du flux Twitch (device code)")?;
    let prompt = DeviceFlowPrompt {
        verification_uri: code.verification_uri.clone(),
        user_code: code.user_code.clone(),
    };
    Ok((builder, prompt))
}

/// Polls Twitch until the user finishes authorizing (or the code expires). Blocks the
/// caller for the duration of the wait — call this from a background task, never the UI
/// thread. Converts the crate's `UserToken` into Hikari's own `StoredToken` immediately —
/// the crate's `UserToken` is never held onto or logged beyond this function (see
/// `vault::Secret` — the conversion is the ONLY place a raw Twitch token briefly exists
/// outside a redacted wrapper).
pub async fn wait_for_authorization(
    builder: &mut DeviceUserTokenBuilder,
    http: &reqwest::Client,
) -> Result<StoredToken, TwitchAuthError> {
    use twitch_oauth2::tokens::errors::DeviceUserTokenExchangeError;

    let token = builder
        .wait_for_code(http, tokio::time::sleep)
        .await
        .map_err(|err| match err {
            DeviceUserTokenExchangeError::Expired => TwitchAuthError::Expired,
            other => TwitchAuthError::Other(other.to_string()),
        })?;
    let refresh_token = token.refresh_token.as_ref().ok_or_else(|| {
        TwitchAuthError::Other("Twitch n'a pas rendu de jeton de rafraîchissement".into())
    })?;
    Ok(StoredToken {
        access_token: Secret::new(token.access_token.secret()),
        refresh_token: Secret::new(refresh_token.secret()),
        expires_at: now_unix() + token_expires_in_secs(&token),
        // Le nom arrive juste apres, par `GET /helix/users` : le flux d'autorisation ne le
        // porte pas. Il est rempli par l'appelant (voir `commands.rs`).
        account_name: None,
    })
}

/// Renouvelle un jeton Twitch arrive a expiration, a partir du jeton de rafraichissement
/// deja range dans le coffre.
///
/// Le flux « device code » d'Hikari est un client PUBLIC : il n'a pas de secret client, et
/// Twitch accepte le renouvellement sans (`client_secret` est un `Option` dans le pont, et
/// vaut `None` ici — meme raison que pour la connexion, voir l'en-tete de ce fichier).
///
/// Rend une erreur quand le renouvellement echoue vraiment : jeton revoque cote Twitch,
/// reseau injoignable. L'appelant redemande alors une connexion — c'est le seul cas ou
/// deranger l'utilisateur est justifie.
pub async fn refresh(
    stored: &StoredToken,
    client_id: &str,
    http: &reqwest::Client,
) -> Result<StoredToken> {
    use twitch_oauth2::{ClientId, RefreshToken};

    let refresh_token = RefreshToken::from(stored.refresh_token.expose().to_string());
    let client_id = ClientId::from(client_id.to_string());
    let (access_token, expires_in, new_refresh) = refresh_token
        .refresh_token(http, &client_id, None)
        .await
        .context("renouvellement du jeton Twitch")?;

    Ok(merge_refreshed(
        stored,
        access_token.secret(),
        expires_in.as_secs(),
        new_refresh.as_ref().map(|token| token.secret()),
        now_unix(),
    ))
}

/// `UserToken::expires_in()` is a private crate method reachable only via the public
/// `TwitchToken` trait; isolated here so the rest of this module reads cleanly.
fn token_expires_in_secs(token: &twitch_oauth2::UserToken) -> u64 {
    use twitch_oauth2::TwitchToken;
    token.expires_in().as_secs()
}

/// Le jeton Twitch RÉELLEMENT utilisable maintenant — chargé, renouvelé s'il a expiré,
/// rangé si le renouvellement a marché. Point d'entrée unique pour toute partie qui a
/// besoin d'appeler Twitch (diffusion, chat) : avant cette fonction, `broadcast_target.rs`
/// portait ce geste en entier et `chat/mod.rs` s'arrêtait au seul `is_expired`, sans
/// jamais tenter le renouvellement — un compte que l'écran Comptes annonce « connecté »
/// (`Connection::Live`, `accounts/mod.rs`, car renouvelable) coupait donc le chat en
/// silence, exactement le symptôme rapporté par Jay le 2026-09-19 (« rien ne s'affiche,
/// dans les deux sens »).
///
/// `Ok(None)` = aucun compte rangé, rien à signaler (ouvrir Hikari sans compte est normal).
/// `Ok(Some(_))` = un jeton utilisable, éventuellement tout juste renouvelé.
/// `Err(_)` = un compte existe mais est mort (renouvellement refusé par Twitch, ou réseau
/// injoignable) — le SEUL cas où prévenir l'utilisateur est justifié, il doit se
/// reconnecter dans Paramètres.
pub async fn usable_token(http: &reqwest::Client) -> Result<Option<StoredToken>, String> {
    let token = match vault::load(Platform::Twitch) {
        Ok(Some(token)) => token,
        Ok(None) => return Ok(None),
        Err(err) => {
            eprintln!("[twitch] coffre illisible ({err})");
            return Ok(None);
        }
    };

    if !vault::is_expired(&token, now_unix()) {
        return Ok(Some(token));
    }

    match refresh(&token, TWITCH_CLIENT_ID, http).await {
        Ok(renewed) => {
            if let Err(err) = vault::store(Platform::Twitch, &renewed) {
                // Le renouvellement a marché, l'écriture non : on rend quand même le jeton
                // neuf à l'appelant, mais la trace dit pourquoi ça recommencera au prochain
                // lancement (même choix que `resolve_broadcast_target` avant l'extraction).
                eprintln!("[twitch] jeton renouvelé mais non rangé ({err})");
            }
            Ok(Some(renewed))
        }
        Err(err) => Err(format!("renouvellement refusé ({err})")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Le comportement de fusion lui-même (nom conservé, ancien jeton de rafraîchissement
    // gardé quand la plateforme n'en redonne pas, jamais de fuite en debug) est testé une
    // seule fois, dans `vault.rs` — `merge_refreshed` est partagé, pas propre à Twitch
    // (extrait le 2026-09-09 pour que YouTube l'utilise aussi).

    #[test]
    fn should_request_stream_key_chat_moderation_and_alert_scopes() {
        // Hikari asks for exactly the scopes it needs today — a regression guard: if a
        // future change silently widens this further, this test catches it. Widening
        // scope is a deliberate choice, not a drift — all made 2026-09-14, same session
        // (read/send, then moderation, then alerts).
        let scopes = required_scopes();
        assert_eq!(
            scopes,
            vec![
                Scope::ChannelReadStreamKey,
                Scope::ChatRead,
                Scope::ChatEdit,
                Scope::ModeratorManageBannedUsers,
                Scope::ModeratorReadFollowers,
                Scope::ChannelReadSubscriptions,
                Scope::BitsRead,
            ]
        );
    }
}
