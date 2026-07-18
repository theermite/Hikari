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
//! Scope: `channel:read:stream_key` (the one Twitch scope that lets Hikari fetch the
//! ingest key — verified via the crate's own `Scope::ChannelReadStreamKey` constant,
//! matching Twitch's documented scope string `channel:read:stream_key`).

use anyhow::{Context, Result};
use twitch_oauth2::tokens::DeviceUserTokenBuilder;
use twitch_oauth2::Scope;

use crate::accounts::vault::{now_unix, Secret, StoredToken};

/// The one scope Hikari asks for — reading the stream key. Nothing broader (chat, channel
/// management, etc.) until a feature actually needs it (F-030+ chat integration, later).
fn required_scopes() -> Vec<Scope> {
    vec![Scope::ChannelReadStreamKey]
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
    let code = builder.start(http).await.context("démarrage du flux Twitch (device code)")?;
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
) -> Result<StoredToken> {
    let token = builder
        .wait_for_code(http, tokio::time::sleep)
        .await
        .map_err(|err| anyhow::anyhow!("autorisation Twitch échouée ou expirée: {err}"))?;
    let refresh_token = token
        .refresh_token
        .as_ref()
        .context("Twitch n'a pas rendu de jeton de rafraîchissement")?;
    Ok(StoredToken {
        access_token: Secret::new(token.access_token.secret()),
        refresh_token: Secret::new(refresh_token.secret()),
        expires_at: now_unix() + token_expires_in_secs(&token),
    })
}

/// `UserToken::expires_in()` is a private crate method reachable only via the public
/// `TwitchToken` trait; isolated here so the rest of this module reads cleanly.
fn token_expires_in_secs(token: &twitch_oauth2::UserToken) -> u64 {
    use twitch_oauth2::TwitchToken;
    token.expires_in().as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_request_only_the_stream_key_scope() {
        // Hikari asks for the minimum scope it needs today — a regression guard: if a
        // future change silently widens this (e.g. adding chat scopes without deciding
        // to), this test catches it. Widening scope is a deliberate choice, not a drift.
        let scopes = required_scopes();
        assert_eq!(scopes, vec![Scope::ChannelReadStreamKey]);
    }
}
