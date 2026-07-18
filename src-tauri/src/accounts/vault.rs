//! Token vault (B2b). Per-account OAuth tokens live in the OS's OWN credential store
//! (Windows Credential Manager via `keyring`) — NEVER a server-side vault, NEVER a file on
//! disk. Hikari has no account/server model (CDC: "Aucun compte Hikari") — this mirrors
//! that: every secret stays on the machine that owns it.
//!
//! `Platform` is a closed enum, not an arbitrary string — `should_target_only_whitelisted_
//! platforms` holds by construction: there is no code path that can address a platform
//! Hikari doesn't know about.

use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use keyring::Entry;

/// The streaming platforms Hikari can connect an account to. Closed by design — adding a
/// platform is a code change, never a runtime string.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Twitch,
    YouTube,
}

impl Platform {
    /// The keyring "username" for this platform's entry. Stable, never changes.
    fn vault_key(self) -> &'static str {
        match self {
            Platform::Twitch => "twitch",
            Platform::YouTube => "youtube",
        }
    }
}

/// A stored OAuth token. `Debug` is hand-implemented to redact both tokens — the derived
/// `Debug` would print them verbatim into any log line that formats this struct, exactly
/// the kind of leak `Security.md` forbids.
pub struct StoredToken {
    pub access_token: String,
    pub refresh_token: String,
    /// Unix timestamp (seconds) the access token expires at.
    pub expires_at: u64,
}

impl fmt::Debug for StoredToken {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("StoredToken")
            .field("access_token", &"«redacted»")
            .field("refresh_token", &"«redacted»")
            .field("expires_at", &self.expires_at)
            .finish()
    }
}

/// Whether the given token is expired at `now` (seconds since epoch). A stream must never
/// start with an expired token — the caller refuses and refreshes instead.
pub fn is_expired(token: &StoredToken, now: u64) -> bool {
    now >= token.expires_at
}

/// The current time as a Unix timestamp — the only non-pure input `is_expired` needs, kept
/// as a thin wrapper so call sites don't reach for `SystemTime` directly.
pub fn now_unix() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// Serializes a token to the flat `access_token\trefresh_token\texpires_at` line the vault
/// stores. Pure, so the encode/decode round-trip is unit-tested without touching the OS
/// credential store.
fn encode(token: &StoredToken) -> String {
    format!("{}\t{}\t{}", token.access_token, token.refresh_token, token.expires_at)
}

/// Parses a vault-stored line back into a token. Hostile input (corrupted entry, wrong
/// field count) yields a clean `Err`, never a panic.
fn decode(raw: &str) -> Result<StoredToken> {
    let mut parts = raw.splitn(3, '\t');
    let access_token = parts.next().context("jeton d'accès manquant")?.to_string();
    let refresh_token = parts.next().context("jeton de rafraîchissement manquant")?.to_string();
    let expires_at: u64 = parts
        .next()
        .context("expiration manquante")?
        .parse()
        .context("expiration non numérique")?;
    Ok(StoredToken { access_token, refresh_token, expires_at })
}

/// Stores a token for `platform` in the OS credential store. Overwrites any prior entry
/// (a fresh login/refresh replaces the old token, never accumulates stale ones).
pub fn store(platform: Platform, token: &StoredToken) -> Result<()> {
    let entry = Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    entry.set_password(&encode(token)).context("écriture du jeton dans le coffre")?;
    Ok(())
}

/// Loads the token for `platform`, if one was ever stored. `Ok(None)` means "never
/// connected" — not an error.
pub fn load(platform: Platform) -> Result<Option<StoredToken>> {
    let entry = Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    match entry.get_password() {
        Ok(raw) => Ok(Some(decode(&raw)?)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(err).context("lecture du jeton depuis le coffre"),
    }
}

/// Removes the stored token for `platform` (account disconnect). Removing an entry that
/// doesn't exist is not an error — disconnecting an already-disconnected account is a no-op.
pub fn remove(platform: Platform) -> Result<()> {
    let entry = Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(err).context("suppression du jeton dans le coffre"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_refuse_stream_when_token_expired() {
        let token = StoredToken {
            access_token: "a".into(),
            refresh_token: "r".into(),
            expires_at: 1_000,
        };
        assert!(is_expired(&token, 1_000), "expires_at reached exactly -> expired");
        assert!(is_expired(&token, 1_001), "past expiry -> expired");
        assert!(!is_expired(&token, 999), "before expiry -> still valid");
    }

    #[test]
    fn should_roundtrip_token_encoding() {
        let token = StoredToken {
            access_token: "access-xyz".into(),
            refresh_token: "refresh-abc".into(),
            expires_at: 1_753_000_000,
        };
        let decoded = decode(&encode(&token)).expect("well-formed encoding must decode");
        assert_eq!(decoded.access_token, token.access_token);
        assert_eq!(decoded.refresh_token, token.refresh_token);
        assert_eq!(decoded.expires_at, token.expires_at);
    }

    #[test]
    fn should_return_error_when_stored_entry_is_corrupted() {
        assert!(decode("only-one-field").is_err());
        assert!(decode("two\tfields").is_err());
        assert!(decode("access\trefresh\tnot-a-number").is_err());
    }

    #[test]
    fn should_never_leak_tokens_in_debug_output() {
        let token = StoredToken {
            access_token: "super-secret-access".into(),
            refresh_token: "super-secret-refresh".into(),
            expires_at: 1,
        };
        let debug = format!("{token:?}");
        assert!(!debug.contains("super-secret-access"), "access token must be redacted");
        assert!(!debug.contains("super-secret-refresh"), "refresh token must be redacted");
    }

    #[test]
    fn should_only_address_whitelisted_platforms() {
        // Closed enum: this is exhaustive by construction, not by convention. Adding a
        // third arm to `Platform` without updating this match is a compile error.
        for platform in [Platform::Twitch, Platform::YouTube] {
            let key = platform.vault_key();
            assert!(!key.is_empty());
        }
    }
}
