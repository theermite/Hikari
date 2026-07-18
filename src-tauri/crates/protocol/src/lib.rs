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

use serde::{Deserialize, Serialize};
use serde::de::DeserializeOwned;

/// The libobs source-kind identifier for a monitor (screen) capture — shared vocabulary
/// so a deck can render the right icon without guessing.
pub const MONITOR_CAPTURE_KIND: &str = "monitor_capture";

/// One source inside a scene (e.g. a monitor capture). `kind` names the libobs source
/// family so a deck can render an icon without guessing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceInfo {
    pub name: String,
    pub kind: String,
}

impl SourceInfo {
    /// Describe a monitor (screen) capture source. Pure: no libobs, so the engine's
    /// source-listing logic is unit-testable without the OBS runtime.
    pub fn monitor_capture(name: impl Into<String>) -> Self {
        Self { name: name.into(), kind: MONITOR_CAPTURE_KIND.to_string() }
    }
}

/// Messages the engine emits toward the controller (engine -> controller), one per line.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EngineMessage {
    /// libobs is initialized; the engine is ready to receive commands.
    Ready,
    /// The current scene's sources, answering a `ListSources` command or a scene build.
    Sources { items: Vec<SourceInfo> },
    /// The video encoders libobs reports as available on this machine.
    Encoders { available: Vec<String> },
    /// The chosen video encoder and whether it is hardware-accelerated (never a silent
    /// software fallback — the controller is told).
    VideoEncoder { kind: String, hardware: bool },
    /// The RTMP service target was attached (server only; a key is never wired here).
    Service { server: String },
    /// Streaming started for the given duration in seconds.
    Started { secs: u64 },
    /// Network frame counters — `dropped` is the real health indicator.
    Frames { dropped: i32, total: i32 },
    /// Streaming stopped cleanly.
    Stopped,
    /// A recoverable engine error, reported instead of dying silently.
    Error { message: String },
}

/// Commands the controller sends to the engine (controller -> engine), one per line.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ControllerCommand {
    /// Create a scene with the given name.
    CreateScene { name: String },
    /// Ask the engine to emit the current scene's sources.
    ListSources,
    /// Ask the engine to stop and exit cleanly.
    Stop,
}

/// Serialize any protocol value to a single JSON line (no trailing newline).
///
/// `serde_json::to_string` never emits a newline, so the "one object per line"
/// invariant of the wire format holds; callers add the `\n` line separator.
pub fn to_line<T: Serialize>(value: &T) -> Result<String, serde_json::Error> {
    serde_json::to_string(value)
}

/// Parse one JSON line into `T`. Invalid or unknown input yields an `Err`, never a panic
/// (the pipe is treated as hostile by default).
pub fn parse_line<T: DeserializeOwned>(line: &str) -> Result<T, serde_json::Error> {
    serde_json::from_str(line.trim_end())
}

/// Parse one line emitted by the engine.
pub fn parse_engine_message(line: &str) -> Result<EngineMessage, serde_json::Error> {
    parse_line(line)
}

/// Parse one command sent to the engine.
pub fn parse_controller_command(line: &str) -> Result<ControllerCommand, serde_json::Error> {
    parse_line(line)
}
