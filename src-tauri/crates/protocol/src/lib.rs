//! Hikari wire protocol (ADR-011) — the JSON-line interface between the controller
//! (the Tauri app) and the engine process (`hikari-engine`).
//!
//! WHY this crate is separate: the engine runs in its OWN process (ADR-013, fault
//! isolation) and must never link the Tauri app. Both sides need the exact same wire
//! types, so those types live here — a pure crate with zero libobs/tauri dependency.
//! This is the single source of truth B4/B5 (the decks) will consume.
//!
//! WIRE FORMAT: one JSON object per line on stdio. `type` tags the variant
//! (`{"type":"ready"}`, `{"type":"frames","dropped":0,"total":900}`). Unknown fields
//! are tolerated on purpose (additive forward-compat as the protocol grows); an unknown
//! `type` is rejected by the tagged enum.
//!
//! Split by theme (2026-08-20, file over the 500-line ceiling): [`sources`] (what a scene
//! can hold), [`scenes`] (what one scene holds + name validation), [`audio`] (the mixer's
//! vocabulary), [`geometry`] (pure canvas math for the mouse-driven camera), [`wire`] (the
//! two tagged enums + line (de)serialization). Every type stays reachable at the crate
//! root (`hikari_protocol::SourceInfo`, not `hikari_protocol::sources::SourceInfo`) via the
//! re-exports below — no caller had to change.

pub mod audio;
pub mod geometry;
pub mod platform;
pub mod scenes;
pub mod sources;
pub mod wire;

pub use audio::*;
pub use geometry::*;
pub use platform::*;
pub use scenes::*;
pub use sources::*;
pub use wire::*;
