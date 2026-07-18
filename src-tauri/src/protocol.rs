//! Wire protocol for the app side (ADR-011).
//!
//! The types themselves live in the pure `hikari-protocol` crate so the engine process
//! (which must NOT link the Tauri app) shares the exact same definitions — one source of
//! truth for B4/B5 (the decks). This module re-exports them at the documented app path so
//! `engine_bridge` and future Tauri commands reference `crate::protocol::…`.

pub use hikari_protocol::{
    ControllerCommand, EngineMessage, SourceInfo, parse_controller_command, parse_engine_message,
    parse_line, to_line,
};
