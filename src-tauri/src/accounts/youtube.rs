//! YouTube account connection — Authorization Code + PKCE (Google's "Desktop app" installed-
//! app flow), NOT Twitch's Device Code Flow. Verified at the source (developers.google.com,
//! raw page text) that Google's model differs from Twitch's on two points:
//!
//! 1. **A client secret exists** even for a Desktop app — Google's own docs state "installed
//!    apps cannot keep secrets" and treat the Desktop-app secret as not-really-confidential
//!    (unlike a server-side confidential client). Embedding it here mirrors Google's own
//!    accepted practice for this client type — it is NOT equivalent to Twitch's zero-secret
//!    Public client, but it is Google's documented model, not an invented workaround.
//! 2. **No device-code UX** — Google's Device flow (TV/limited-input) exists but REQUIRES a
//!    client secret at poll time AND restricts scopes to a short allowlist (`youtube`,
//!    `youtube.readonly` happen to be in it, but the secret requirement makes it no better
//!    than Authorization Code for our case) — so it buys nothing over the standard flow here.
//!    Authorization Code + PKCE needs a local HTTP listener (`tiny_http`, 53M+ downloads,
//!    used instead of hand-parsing raw HTTP) to receive the one redirect, then shuts down.
//!
//! Scope: `youtube.readonly` — confirmed the minimum accepted scope for `liveStreams.list`
//! (the endpoint that returns `cdn.ingestionInfo.streamName`, the stream key) directly from
//! Google's own `liveStreams/list` reference page ("requires ... at least one of: youtube.readonly,
//! youtube, youtube.force-ssl" — the first is the least-privileged of the three).
//!
//! PKCE mechanics (verifier/state/challenge) are NOT duplicated here — see `accounts::oauth`,
//! built provider-agnostic for exactly this reuse.

use std::fmt;

use serde::Deserialize;

use crate::accounts::oauth::{code_challenge_from_verifier, generate_code_verifier, generate_state};
use crate::accounts::vault::{now_unix, Secret, StoredToken};

/// Fixed loopback port for the local redirect listener. Google requires the exact redirect
/// URI to be pre-registered in Cloud Console (no documented wildcard-port exception found
/// in Google's own reference for Desktop apps) — so this MUST match what Jay registers.
pub const REDIRECT_PORT: u16 = 8731;
/// The one scope Hikari needs — read-only access to list live streams (stream key lookup).
/// Confirmed as the least-privileged of the 3 scopes `liveStreams.list` accepts.
const SCOPE: &str = "https://www.googleapis.com/auth/youtube.readonly";
const AUTH_ENDPOINT: &str = "https://accounts.google.com/o/oauth2/v2/auth";
const TOKEN_ENDPOINT: &str = "https://oauth2.googleapis.com/token";

fn redirect_uri() -> String {
    format!("http://127.0.0.1:{REDIRECT_PORT}/callback")
}

/// Why the YouTube connection flow failed — mirrors `TwitchAuthError`'s intent (let a
/// future UI branch behavior), scoped to what this flow can actually distinguish.
#[derive(Debug)]
pub enum YouTubeAuthError {
    /// The redirect's `state` didn't match what we sent — a real CSRF signal, never ignore.
    StateMismatch,
    /// The user's browser redirect carried an error instead of a code (e.g. they declined).
    Denied(String),
    /// The local loopback listener couldn't bind (port in use) or the redirect was malformed.
    CallbackFailed(String),
    /// The token exchange with Google failed (network, or Google returned an error body).
    TokenExchangeFailed(String),
    /// Google didn't return a refresh token — happens if the user already granted consent
    /// before without `access_type=offline`; we always request it, so this signals a bug.
    MissingRefreshToken,
}

impl fmt::Display for YouTubeAuthError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            YouTubeAuthError::StateMismatch => write!(f, "réponse Google suspecte (state incohérent)"),
            YouTubeAuthError::Denied(msg) => write!(f, "autorisation refusée: {msg}"),
            YouTubeAuthError::CallbackFailed(msg) => write!(f, "réception de la redirection échouée: {msg}"),
            YouTubeAuthError::TokenExchangeFailed(msg) => write!(f, "échange du jeton échoué: {msg}"),
            YouTubeAuthError::MissingRefreshToken => write!(f, "Google n'a pas rendu de jeton de rafraîchissement"),
        }
    }
}

impl std::error::Error for YouTubeAuthError {}

/// What `start_authorization` hands back: the URL to open in a browser, plus the PKCE/CSRF
/// material `finish_authorization` needs to validate the redirect and redeem the code.
/// `code_verifier` is a `Secret` — it must stay confidential until the token exchange (RFC
/// 7636's entire point), even though it never leaves this machine.
pub struct PendingAuthorization {
    pub authorization_url: String,
    code_verifier: Secret,
    state: String,
}

/// Builds the authorization URL to open in the user's browser. Pure string construction —
/// no network yet. `client_id` comes from Jay's Google Cloud Console registration, never
/// hardcoded (unlike `TWITCH_CLIENT_ID`, this project's YouTube client isn't wired yet).
pub fn start_authorization(client_id: &str) -> PendingAuthorization {
    let code_verifier = generate_code_verifier();
    let state = generate_state();
    let challenge = code_challenge_from_verifier(&code_verifier);
    let authorization_url = build_authorization_url(client_id, &redirect_uri(), &state, &challenge);
    PendingAuthorization { authorization_url, code_verifier: Secret::new(code_verifier), state }
}

/// Pure URL construction, split out from `start_authorization` so it's unit-testable without
/// generating real random PKCE material each time.
fn build_authorization_url(client_id: &str, redirect_uri: &str, state: &str, code_challenge: &str) -> String {
    let params = [
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("response_type", "code"),
        ("scope", SCOPE),
        ("access_type", "offline"), // required to receive a refresh token
        ("prompt", "consent"),      // forces a fresh refresh token even on a repeat connect
        ("state", state),
        ("code_challenge", code_challenge),
        ("code_challenge_method", "S256"),
    ];
    let query: String = params
        .iter()
        .map(|(k, v)| format!("{k}={}", urlencoding::encode(v)))
        .collect::<Vec<_>>()
        .join("&");
    format!("{AUTH_ENDPOINT}?{query}")
}

/// The two fields Google's redirect carries — extracted from the raw query string so the
/// parsing itself is a pure, testable function (the network listener below is a thin shell
/// around it, same split as the rest of this module). `code` is NOT wrapped in `Secret`
/// here: it's a single-use authorization code (redeemed once at `exchange_code_for_token`,
/// then worthless), not a long-lived credential like the resulting access/refresh tokens —
/// `Debug` on it is fine, this struct never survives past this module either way.
#[derive(Debug)]
struct CallbackParams {
    code: String,
    state: String,
}

/// Parses `code`/`state` (or an `error` param) out of a redirect's raw query string. Hostile
/// or malformed input yields a clean `Err`, never a panic — this parses whatever a browser
/// sends, which this process does not control.
fn parse_callback_query(query: &str) -> Result<CallbackParams, YouTubeAuthError> {
    let mut code = None;
    let mut state = None;
    let mut error = None;
    for pair in query.split('&') {
        let Some((key, value)) = pair.split_once('=') else { continue };
        let value = urlencoding::decode(value).map(|v| v.into_owned()).unwrap_or_default();
        match key {
            "code" => code = Some(value),
            "state" => state = Some(value),
            "error" => error = Some(value),
            _ => {}
        }
    }
    if let Some(error) = error {
        return Err(YouTubeAuthError::Denied(error));
    }
    Ok(CallbackParams {
        code: code.ok_or_else(|| YouTubeAuthError::CallbackFailed("code manquant".into()))?,
        state: state.ok_or_else(|| YouTubeAuthError::CallbackFailed("state manquant".into()))?,
    })
}

/// Blocks waiting for Google's ONE redirect on the local loopback listener, validates the
/// CSRF `state`, then exchanges the code for a token. Call from a background task — this
/// blocks the calling thread until the browser redirect arrives.
pub async fn finish_authorization(
    pending: PendingAuthorization,
    client_id: &str,
    client_secret: &Secret,
    http: &reqwest::Client,
) -> Result<StoredToken, YouTubeAuthError> {
    let code = receive_redirect(&pending.state)?;
    exchange_code_for_token(client_id, client_secret, &code, pending.code_verifier.expose(), http).await
}

/// The exact path segment of the redirect URI (`redirect_uri()` ends in this) — used to
/// tell Google's real callback apart from any other local request that might land on this
/// port first (a browser's automatic favicon fetch, a stray local scan; found in review:
/// treating the FIRST request received as authoritative let an unrelated request consume
/// the single `recv()`, silently dropping the real callback that arrived right after).
const CALLBACK_PATH: &str = "/callback";
/// How long `receive_redirect` waits for the real callback before giving up — bounds an
/// abandoned flow (user closes the browser tab) so the port is freed for a retry instead
/// of blocking the calling thread forever (found in review: the original `server.recv()`
/// had no timeout at all).
const AUTHORIZATION_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(300);

/// Binds the fixed loopback port and waits for the ONE request whose path matches
/// `CALLBACK_PATH`, validates its `state`, responds with a page telling the user to return
/// to Hikari, then shuts the listener down. Any other request received in the meantime
/// (path mismatch) is answered 404 and ignored — the wait continues, bounded by
/// `AUTHORIZATION_TIMEOUT`.
fn receive_redirect(expected_state: &str) -> Result<String, YouTubeAuthError> {
    let server = tiny_http::Server::http(("127.0.0.1", REDIRECT_PORT))
        .map_err(|err| YouTubeAuthError::CallbackFailed(format!("port {REDIRECT_PORT} indisponible: {err}")))?;
    receive_redirect_on(&server, expected_state, AUTHORIZATION_TIMEOUT)
}

/// The actual wait/filter/validate loop, taking the server as a parameter so tests can bind
/// an ephemeral port instead of the fixed production one (see the `tests` module below).
fn receive_redirect_on(
    server: &tiny_http::Server,
    expected_state: &str,
    timeout: std::time::Duration,
) -> Result<String, YouTubeAuthError> {
    let deadline = std::time::Instant::now() + timeout;

    let params = loop {
        let remaining = deadline.saturating_duration_since(std::time::Instant::now());
        if remaining.is_zero() {
            return Err(YouTubeAuthError::CallbackFailed(format!("délai d'autorisation dépassé ({}s)", timeout.as_secs())));
        }
        let request = server
            .recv_timeout(remaining)
            .map_err(|err| YouTubeAuthError::CallbackFailed(format!("erreur réseau: {err}")))?
            .ok_or_else(|| YouTubeAuthError::CallbackFailed("délai d'autorisation dépassé (5 min)".into()))?;

        let (path, query) = request.url().split_once('?').unwrap_or((request.url(), ""));
        if path != CALLBACK_PATH {
            let _ = request.respond(tiny_http::Response::from_string("").with_status_code(404));
            continue;
        }

        let params = parse_callback_query(query);
        let (status, body) = match &params {
            Ok(_) => (200, "<html><body>Connexion YouTube réussie — vous pouvez fermer cette fenêtre et revenir à Hikari.</body></html>"),
            Err(_) => (400, "<html><body>La connexion a échoué — revenez à Hikari et réessayez.</body></html>"),
        };
        let response = tiny_http::Response::from_string(body)
            .with_status_code(status)
            .with_header(tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"text/html; charset=utf-8"[..]).unwrap());
        let _ = request.respond(response);
        break params;
    };

    let params = params?;
    if params.state != expected_state {
        return Err(YouTubeAuthError::StateMismatch);
    }
    Ok(params.code)
}

/// Google's expected token-endpoint response shape (only the fields Hikari needs).
#[derive(Deserialize)]
struct TokenResponse {
    access_token: String,
    refresh_token: Option<String>,
    expires_in: u64,
}

/// Exchanges the authorization code for a token — the PKCE `code_verifier` proves this
/// request came from the same process that started the flow (RFC 7636), so a stolen code
/// alone can't be redeemed by an attacker.
async fn exchange_code_for_token(
    client_id: &str,
    client_secret: &Secret,
    code: &str,
    code_verifier: &str,
    http: &reqwest::Client,
) -> Result<StoredToken, YouTubeAuthError> {
    let params = [
        ("client_id", client_id),
        ("client_secret", client_secret.expose()),
        ("code", code),
        ("code_verifier", code_verifier),
        ("grant_type", "authorization_code"),
        ("redirect_uri", &redirect_uri()),
    ];
    let response = http
        .post(TOKEN_ENDPOINT)
        .form(&params)
        .send()
        .await
        .map_err(|err| YouTubeAuthError::TokenExchangeFailed(err.to_string()))?;
    if !response.status().is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(YouTubeAuthError::TokenExchangeFailed(body));
    }
    let token: TokenResponse =
        response.json().await.map_err(|err| YouTubeAuthError::TokenExchangeFailed(err.to_string()))?;
    let refresh_token = token.refresh_token.ok_or(YouTubeAuthError::MissingRefreshToken)?;
    Ok(StoredToken {
        access_token: Secret::new(token.access_token),
        refresh_token: Secret::new(refresh_token),
        expires_at: now_unix() + token.expires_in,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_build_authorization_url_with_pkce_and_offline_access() {
        let url = build_authorization_url("my-client-id", "http://127.0.0.1:8731/callback", "the-state", "the-challenge");
        assert!(url.starts_with(AUTH_ENDPOINT));
        assert!(url.contains("client_id=my-client-id"));
        assert!(url.contains("code_challenge=the-challenge"));
        assert!(url.contains("code_challenge_method=S256"));
        assert!(url.contains("access_type=offline"), "must request offline access for a refresh token");
        assert!(url.contains(&urlencoding::encode(SCOPE).into_owned()));
    }

    #[test]
    fn should_parse_successful_callback_query() {
        let params = parse_callback_query("code=abc123&state=xyz789&scope=foo").expect("valid query parses");
        assert_eq!(params.code, "abc123");
        assert_eq!(params.state, "xyz789");
    }

    #[test]
    fn should_report_denial_when_error_param_present() {
        let err = parse_callback_query("error=access_denied&state=xyz789").unwrap_err();
        assert!(matches!(err, YouTubeAuthError::Denied(_)));
    }

    #[test]
    fn should_fail_cleanly_on_missing_code() {
        let err = parse_callback_query("state=xyz789").unwrap_err();
        assert!(matches!(err, YouTubeAuthError::CallbackFailed(_)));
    }

    #[test]
    fn should_fail_cleanly_on_missing_state() {
        let err = parse_callback_query("code=abc123").unwrap_err();
        assert!(matches!(err, YouTubeAuthError::CallbackFailed(_)));
    }

    #[test]
    fn should_decode_url_encoded_values() {
        // Google URL-encodes state/code in practice — a raw '%' in an unencoded value must
        // not be assumed; verify decoding actually happens rather than passing through raw.
        let params = parse_callback_query("code=a%2Bb&state=hello%20world").expect("encoded query parses");
        assert_eq!(params.code, "a+b");
        assert_eq!(params.state, "hello world");
    }

    // `receive_redirect_on`'s path-filtering and timeout behavior (both fixed after the
    // Gate 2 review — see its doc comments) are NOT covered by an automated test here: a
    // real loopback TCP test hung the whole suite for 10+ minutes on this dev machine, most
    // likely WSL2's Hyper-V virtual switch silently blocking connections on ephemeral ports
    // (`vmmemWSL` was active; several Windows-reserved TCP exclusion ranges overlap the
    // ephemeral port range `bind("127.0.0.1:0")` draws from — confirmed via `netsh interface
    // ipv4 show excludedportrange protocol=tcp`). Same regime as the `engine` crate's real
    // libobs calls (`crates/engine/Cargo.toml`, `test = false`): validated by RUNNING the
    // real flow once (manual OAuth connect through Hikari), not an automated headless test.
}
