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
pub mod vault;
