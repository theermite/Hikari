//! OAuth PKCE mechanics (B2b), provider-agnostic — RFC 7636. The Twitch/YouTube-specific
//! wiring (client ID, redirect URI, exact scopes) is NOT here: that needs a real developer
//! app registration, confirmed by Jay before the first platform goes live (PET fiche B2b:
//! "la 1ʳᵉ intégration OAuth mérite une validation humaine"). This module is the reusable,
//! provider-independent half — pure and unit-tested, no network, no platform secret.

use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use rand::RngCore;
use sha2::{Digest, Sha256};

/// PKCE code verifiers/state must draw from unreserved URL-safe characters (RFC 7636 §4.1).
/// 32 random bytes, base64url-no-pad encoded, land at 43 characters — the RFC's minimum
/// and a common default across OAuth providers (Twitch and Google both accept it).
const RANDOM_BYTES: usize = 32;

/// Generates a fresh PKCE code verifier: a high-entropy random string the app keeps secret
/// until it redeems the authorization code — this is what defeats a stolen auth code
/// (RFC 7636's entire purpose).
pub fn generate_code_verifier() -> String {
    random_url_safe_token()
}

/// Generates a fresh CSRF `state` value — a second, independent random string (never
/// derived from the verifier) that the callback handler checks matches what was sent.
pub fn generate_state() -> String {
    random_url_safe_token()
}

fn random_url_safe_token() -> String {
    let mut bytes = [0u8; RANDOM_BYTES];
    rand::rng().fill_bytes(&mut bytes);
    URL_SAFE_NO_PAD.encode(bytes)
}

/// Derives the PKCE code challenge (S256 method) from a verifier: `BASE64URL(SHA256(verifier))`,
/// exactly RFC 7636 §4.2. Pure — the same verifier always yields the same challenge.
pub fn code_challenge_from_verifier(verifier: &str) -> String {
    let digest = Sha256::digest(verifier.as_bytes());
    URL_SAFE_NO_PAD.encode(digest)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_generate_verifier_within_rfc7636_length_bounds() {
        // RFC 7636 §4.1: 43-128 characters, unreserved [A-Z a-z 0-9 - . _ ~].
        let verifier = generate_code_verifier();
        assert!(verifier.len() >= 43, "too short: {}", verifier.len());
        assert!(verifier.len() <= 128, "too long: {}", verifier.len());
        assert!(
            verifier.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_'),
            "base64url-no-pad only ever emits [A-Za-z0-9-_], verified against RFC's charset: {verifier:?}"
        );
    }

    #[test]
    fn should_generate_distinct_verifiers_each_call() {
        // Two calls must never collide — a repeated verifier would defeat the whole point
        // of PKCE (an attacker could predict/replay it).
        let a = generate_code_verifier();
        let b = generate_code_verifier();
        assert_ne!(a, b, "verifiers must be independently random");
    }

    #[test]
    fn should_generate_state_independently_from_verifier() {
        let verifier = generate_code_verifier();
        let state = generate_state();
        assert_ne!(verifier, state, "state must never be derivable from the verifier");
    }

    #[test]
    fn should_derive_deterministic_challenge_from_verifier() {
        // Same verifier -> same challenge, always (the platform re-derives it server-side
        // to check the auth code redemption — this MUST be deterministic).
        let verifier = "a-fixed-test-verifier-for-determinism-check";
        let challenge_a = code_challenge_from_verifier(verifier);
        let challenge_b = code_challenge_from_verifier(verifier);
        assert_eq!(challenge_a, challenge_b);
    }

    #[test]
    fn should_derive_different_challenges_for_different_verifiers() {
        let challenge_a = code_challenge_from_verifier("verifier-one");
        let challenge_b = code_challenge_from_verifier("verifier-two");
        assert_ne!(challenge_a, challenge_b);
    }

    #[test]
    fn should_match_known_rfc7636_test_vector() {
        // RFC 7636 Appendix B's own worked example — verifies our SHA256+base64url
        // implementation against the spec's published vector, not just internal
        // consistency (the tests above would all pass even with a wrong but consistent hash).
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        let challenge = code_challenge_from_verifier(verifier);
        assert_eq!(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
    }
}
