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

/// A secret string that CANNOT be printed by accident: `Debug` and `Display` are both
/// redacted at the TYPE level, not by convention on the struct that happens to embed it
/// (review finding: a `pub String` field is one careless `format!`/frontend echo away from
/// leaking — this makes that mistake a type error's worth of harder, not just a style rule).
/// `expose()` is the one, explicit escape hatch — every read site names itself as reading
/// a secret.
#[derive(Clone, PartialEq, Eq)]
pub struct Secret(String);

impl Secret {
    pub fn new(value: impl Into<String>) -> Self {
        Self(value.into())
    }

    /// The only way to read the secret value — deliberately named so every call site is
    /// grep-able and self-documents that it is handling a secret.
    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl fmt::Debug for Secret {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "«redacted»")
    }
}

impl fmt::Display for Secret {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "«redacted»")
    }
}

/// A stored OAuth token. Both secrets are `Secret`, not `String` — redaction holds even if
/// a future caller derives `Debug`/logs this struct through a wrapper that doesn't know
/// about the hand-written impl below.
#[derive(Debug)]
pub struct StoredToken {
    pub access_token: Secret,
    pub refresh_token: Secret,
    /// Unix timestamp (seconds) the access token expires at.
    pub expires_at: u64,
    /// Le nom LISIBLE du compte connecté — « KromKam », pas un identifiant.
    ///
    /// Pourquoi il vit ici : Jay a plusieurs comptes Twitch, un de test et son compte
    /// principal, et « connecté » ne lui dit pas lequel (2026-09-07). Rangé avec le jeton,
    /// il s'affiche sans appel réseau, donc aussi hors ligne.
    ///
    /// `Option` et non `String` : les jetons rangés AVANT cette version n'en portent pas,
    /// et les refuser déconnecterait tout le monde à la mise à jour.
    ///
    /// Ce n'est PAS un secret : c'est le nom que la plateforme affiche publiquement. Il est
    /// donc un `String` nu, et peut traverser vers l'interface — au contraire des deux
    /// champs au-dessus.
    pub account_name: Option<String>,
}

/// Whether the given token is expired at `now` (seconds since epoch). A stream must never
/// start with an expired token — the caller refuses and refreshes instead.
pub fn is_expired(token: &StoredToken, now: u64) -> bool {
    now >= token.expires_at
}

/// The current time as a Unix timestamp — the only non-pure input `is_expired` needs, kept
/// as a thin wrapper so call sites don't reach for `SystemTime` directly.
pub fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Serializes a token to the flat `access_token\trefresh_token\texpires_at` line the vault
/// stores. Pure, so the encode/decode round-trip is unit-tested without touching the OS
/// credential store. A `\t`/`\n` inside a token field shifts the delimiters, but the last
/// field (`expires_at`) then fails to parse as a number — a clean `Err`, never a silent
/// corruption (verified by `should_fail_loudly_when_a_token_field_contains_the_delimiter`).
/// OAuth access/refresh tokens are restricted to the `VSCHAR` charset by RFC 6749 §1.4/
/// Appendix A (0x20-0x7E), which excludes tab and newline — a legitimate token never hits
/// this path in practice.
fn encode(token: &StoredToken) -> String {
    format!(
        "{}\t{}\t{}\t{}",
        token.access_token.expose(),
        token.refresh_token.expose(),
        token.expires_at,
        token.account_name.as_deref().unwrap_or(""),
    )
}

/// Parses a vault-stored line back into a token. Hostile input (corrupted entry, wrong
/// field count) yields a clean `Err`, never a panic.
fn decode(raw: &str) -> Result<StoredToken> {
    // `splitn(4)` et non `splitn(3)` : un 4ᵉ champ, le nom du compte, est arrivé le
    // 2026-09-07. Les entrées écrites avant n'en ont que 3 — elles restent lisibles, et le
    // nom vaut alors `None`. Sans cette tolérance, la mise à jour qui ajoute le nom
    // déconnecterait tout le monde : elle produirait exactement le défaut qu'elle suit.
    let mut parts = raw.splitn(4, '\t');
    let access_token = Secret::new(parts.next().context("jeton d'accès manquant")?);
    let refresh_token = Secret::new(parts.next().context("jeton de rafraîchissement manquant")?);
    let expires_at: u64 = parts
        .next()
        .context("expiration manquante")?
        .parse()
        .context("expiration non numérique")?;
    let account_name = parts
        .next()
        .filter(|nom| !nom.is_empty())
        .map(str::to_string);
    Ok(StoredToken {
        access_token,
        refresh_token,
        expires_at,
        account_name,
    })
}

/// Stores a token for `platform` in the OS credential store. Overwrites any prior entry
/// (a fresh login/refresh replaces the old token, never accumulates stale ones).
pub fn store(platform: Platform, token: &StoredToken) -> Result<()> {
    let entry =
        Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    entry
        .set_password(&encode(token))
        .context("écriture du jeton dans le coffre")?;
    Ok(())
}

/// Loads the token for `platform`, if one was ever stored. `Ok(None)` means "never
/// connected" — not an error.
pub fn load(platform: Platform) -> Result<Option<StoredToken>> {
    let entry =
        Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    match entry.get_password() {
        Ok(raw) => Ok(Some(decode(&raw)?)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(err).context("lecture du jeton depuis le coffre"),
    }
}

/// Removes the stored token for `platform` (account disconnect). Removing an entry that
/// doesn't exist is not an error — disconnecting an already-disconnected account is a no-op.
pub fn remove(platform: Platform) -> Result<()> {
    let entry =
        Entry::new("hikari", platform.vault_key()).context("ouverture du coffre système")?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(err).context("suppression du jeton dans le coffre"),
    }
}

#[cfg(test)]
mod tests {

    #[test]
    fn should_still_read_a_token_stored_before_the_account_name_existed() {
        // Compatibilite ASCENDANTE, et elle n'est pas un detail : sans elle, la mise a jour
        // qui ajoute le nom du compte DECONNECTE tout le monde — le correctif produirait
        // exactement le defaut qu'il vient de fermer.
        let ancien = "acces	rafraichissement	1753000000";
        let decode = decode(ancien).expect("un jeton d'avant doit rester lisible");
        assert_eq!(decode.access_token.expose(), "acces");
        assert_eq!(decode.expires_at, 1_753_000_000);
        assert_eq!(decode.account_name, None);
    }

    #[test]
    fn should_roundtrip_a_token_carrying_an_account_name() {
        let mut t = token("acces", "rafraichissement", 42);
        t.account_name = Some("KromKam".to_string());
        let decode = decode(&encode(&t)).expect("doit se relire");
        assert_eq!(decode.account_name.as_deref(), Some("KromKam"));
    }

    #[test]
    fn should_never_leak_a_secret_through_the_account_name_field() {
        // Le nom n'est PAS un secret, mais il voyage dans la meme ligne que deux secrets :
        // une erreur de decoupe le remplirait avec un morceau de jeton.
        let mut t = token("acces-secret", "rafraichissement-secret", 1);
        t.account_name = Some("Public".to_string());
        let decode = decode(&encode(&t)).expect("doit se relire");
        assert_eq!(decode.account_name.as_deref(), Some("Public"));
    }
    use super::*;

    fn token(access: &str, refresh: &str, expires_at: u64) -> StoredToken {
        StoredToken {
            access_token: Secret::new(access),
            refresh_token: Secret::new(refresh),
            expires_at,
            account_name: None,
        }
    }

    #[test]
    fn should_refuse_stream_when_token_expired() {
        let t = token("a", "r", 1_000);
        assert!(
            is_expired(&t, 1_000),
            "expires_at reached exactly -> expired"
        );
        assert!(is_expired(&t, 1_001), "past expiry -> expired");
        assert!(!is_expired(&t, 999), "before expiry -> still valid");
    }

    #[test]
    fn should_roundtrip_token_encoding() {
        let t = token("access-xyz", "refresh-abc", 1_753_000_000);
        let decoded = decode(&encode(&t)).expect("well-formed encoding must decode");
        assert_eq!(decoded.access_token.expose(), t.access_token.expose());
        assert_eq!(decoded.refresh_token.expose(), t.refresh_token.expose());
        assert_eq!(decoded.expires_at, t.expires_at);
    }

    #[test]
    fn should_return_error_when_stored_entry_is_corrupted() {
        assert!(decode("only-one-field").is_err());
        assert!(decode("two\tfields").is_err());
        assert!(decode("access\trefresh\tnot-a-number").is_err());
    }

    #[test]
    fn should_fail_loudly_when_a_token_field_contains_the_delimiter() {
        // A `\t` inside access_token shifts every field right by one. The shifted last
        // field ("real-expiry", non-numeric) must fail to parse — never a silent, wrong
        // round-trip. Adversarial input from the review, verified rather than assumed.
        let raw = format!("evil\taccess\trefresh\t{}", "not-real-expiry");
        assert!(
            decode(&raw).is_err(),
            "shifted fields must fail to parse, never corrupt silently"
        );
    }

    #[test]
    fn should_never_leak_tokens_in_debug_output() {
        let t = token("super-secret-access", "super-secret-refresh", 1);
        let debug = format!("{t:?}");
        assert!(
            !debug.contains("super-secret-access"),
            "access token must be redacted"
        );
        assert!(
            !debug.contains("super-secret-refresh"),
            "refresh token must be redacted"
        );
    }

    #[test]
    fn should_never_leak_secret_in_display_output() {
        // The type-level guard the review asked for: Display is redacted too, not just
        // Debug — a future `println!("{}", token.access_token)` still can't leak.
        let secret = Secret::new("super-secret-value");
        let displayed = format!("{secret}");
        assert!(!displayed.contains("super-secret-value"));
        assert_eq!(
            secret.expose(),
            "super-secret-value",
            "expose() is still the true value"
        );
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

    #[test]
    fn should_use_distinct_vault_keys_per_platform() {
        assert_ne!(Platform::Twitch.vault_key(), Platform::YouTube.vault_key());
    }
}
