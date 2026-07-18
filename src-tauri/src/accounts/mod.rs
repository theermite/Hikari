//! Account connections (B2b) — OAuth (provider-agnostic PKCE mechanics) + the local token
//! vault (OS credential store, never a server-side store — see `vault.rs`).

pub mod oauth;
pub mod vault;
