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

/// The libobs source-kind identifier for a webcam (DirectShow) source — same id the real
/// win-dshow OBS plugin registers, never invented (B-cam).
pub const CAMERA_KIND: &str = "dshow_input";

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

    /// Describe a webcam (DirectShow) source. Pure, same reason as `monitor_capture`.
    pub fn camera(name: impl Into<String>) -> Self {
        Self { name: name.into(), kind: CAMERA_KIND.to_string() }
    }
}

/// One camera (DirectShow) device libobs reports as available on this machine — `device_id`
/// is the exact encoded value (`"name:path"`) the `dshow_input` source's `video_device_id`
/// property expects, never hand-built (B-cam, real win-dshow plugin behavior).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CameraDevice {
    pub name: String,
    pub device_id: String,
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
    /// The camera (DirectShow) devices libobs reports as available on this machine
    /// (B-cam tranche 1) — never a hardcoded/presumed list.
    Cameras { devices: Vec<CameraDevice> },
    /// The chosen video encoder and whether it is hardware-accelerated (never a silent
    /// software fallback — the controller is told).
    VideoEncoder { kind: String, hardware: bool },
    /// The RTMP service target was attached (server only; a key is never wired here).
    Service { server: String },
    /// Streaming started. No fixed duration — a real stream runs until `StopStream`
    /// (B0.0's spike used a fixed `secs` for its own bounded measurement; production
    /// streams don't know their length in advance).
    Started,
    /// Network frame counters, reported periodically while streaming — `dropped` is the
    /// real health indicator (B2a: continuous, not the spike's single end-of-run sample).
    Frames { dropped: i32, total: i32 },
    /// The stream was stopped cleanly (`StopStream`) — the engine process itself, and its
    /// preview, stay alive. Distinct from `Stopped`, which means the whole engine process
    /// is exiting.
    StreamStopped,
    /// The whole engine process is exiting cleanly (`Stop`).
    Stopped,
    /// A recoverable engine error, reported instead of dying silently.
    Error { message: String },
    /// The engine created its native preview window (`obs_display`, B1b) and it is ready
    /// to be grafted into the app's window. `hwnd` is the raw Win32 window handle, cast to
    /// `i64` for the wire (JSON has no 64-bit unsigned integer type, and a HWND is always
    /// representable in `i64` on the platforms Hikari targets).
    PreviewReady { hwnd: i64 },
    /// One multistream target (B3) started successfully — reported per platform so a
    /// failure on one target never hides the others' success (`should_report_per_platform_status`).
    PlatformStarted { id: String, hardware: bool },
    /// Network frame counters for one multistream target, reported periodically (mirrors
    /// `Frames`, but tagged by `id` since B3 runs several outputs at once).
    PlatformFrames { id: String, dropped: i32, total: i32 },
    /// One multistream target was stopped cleanly.
    PlatformStopped { id: String },
    /// The camera's current position/scale after `NudgeCamera` or `ScaleCamera` (B7) —
    /// emitted with the real, clamped values (never presumed), so the panel reflects what
    /// actually happened rather than optimistically applying the requested delta.
    CameraTransform { x: i32, y: i32, scale_percent: i32 },
    /// One multistream target failed — recoverable, reported instead of silently dropping
    /// that platform (B3 acceptance: "aucun échec silencieux"). The other targets are
    /// unaffected and keep streaming.
    PlatformError { id: String, message: String },
}

/// Commands the controller sends to the engine (controller -> engine), one per line.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ControllerCommand {
    /// Create a scene with the given name.
    CreateScene { name: String },
    /// Ask the engine to emit the current scene's sources.
    ListSources,
    /// Adds a webcam (DirectShow) source to the "main" scene. `device_id` must be the
    /// exact value `EngineMessage::Cameras` reported — never guessed (B-cam).
    AddCamera { device_id: String },
    /// Sets whether the real NVIDIA background-removal filter (`nv_greenscreen_filter`) is
    /// applied to the camera (B-cam, F-036). `libobs-wrapper` 9.0.4 has no public API to
    /// detach an applied filter (verified in its own source) — so toggling this REBUILDS
    /// the whole camera source (remove + re-add + reapply whichever effects are still on),
    /// the only verified-safe way to simulate on/off. Causes a brief camera reinit blip,
    /// disclosed to Jay (2026-07-23).
    SetBackgroundRemoval { enabled: bool },
    /// Sets whether a circular alpha mask (`mask_filter`) is applied to the camera
    /// (B-cam, F-036). Same rebuild-based toggle as `SetBackgroundRemoval`.
    SetCircleMask { enabled: bool },
    /// Removes the webcam source from the "main" scene entirely (B-cam) — its filters
    /// (background removal, mask) go with it, since libobs owns them on the source. The
    /// real way to "turn the camera off" today, given filters themselves have no public
    /// removal API (see `EnableBackgroundRemoval`'s doc). A no-op if no camera is present.
    RemoveCamera,
    /// Start streaming to the RTMP target the engine reads from its OWN environment
    /// (`HIKARI_RTMP_SERVER`/`HIKARI_RTMP_KEY`, B2a scope). The wire NEVER carries a key —
    /// account-sourced targets (B2b, OAuth + vault) will replace the env-var mechanism,
    /// not add a secret-over-IPC path this brick would have to un-build later.
    StartStream,
    /// Stop the current stream. The engine process and its preview stay alive. If no
    /// stream is running, this is a silent no-op — no `StreamStopped` is emitted, since
    /// nothing was actually stopped (revisit before B4/B5 if a deck needs an ack either way).
    StopStream,
    /// Start streaming to N platforms at once (B3, horizontal only — vertical is its own
    /// spike, see PET B3/B0.2). Each target's key is resolved by the engine from its OWN
    /// environment (`HIKARI_RTMP_KEY_<ID>`, uppercased), never carried on the wire — same
    /// rule as `StartStream`. `targets` must pass [`validate_targets`] before being sent;
    /// the engine re-validates and reports a `PlatformError` per rejected target rather
    /// than refusing the whole batch silently.
    StartMultistream { targets: Vec<StreamTarget> },
    /// Stop every multistream target currently running. A target already stopped is a
    /// no-op for that target (mirrors `StopStream`).
    StopMultistream,
    /// Ask the engine to stop and exit cleanly.
    Stop,
    /// Moves the webcam by `(dx, dy)` scene pixels (B7) — a fixed step decided by the
    /// panel's arrow buttons, never a raw drag delta (dockview's own drag broke silently
    /// in this WebView2 build, see session 2026-07-23; buttons are the provably-safe path).
    /// A no-op if no camera is present.
    NudgeCamera { dx: i32, dy: i32 },
    /// Grows (`true`) or shrinks (`false`) the webcam by one fixed step (B7). A no-op if
    /// no camera is present.
    ScaleCamera { grow: bool },
}

/// Clamp bounds for `NudgeCamera` (B7) — a generous sanity range, not exact canvas
/// containment: the wrapper exposes no safe way to read the live canvas size outside
/// libobs's own render thread (`obs_get_video_info` needs the crate's private
/// `run_with_obs!` dispatch), so this only stops the camera drifting to absurd
/// coordinates after many clicks, never a "stays inside the frame" guarantee.
pub const CAMERA_POSITION_BOUND: i32 = 4000;

/// Multiplicative step applied per `ScaleCamera` click (B7) — ±10%, small enough that a
/// misclick is easy to undo with the opposite button.
pub const CAMERA_SCALE_STEP: f32 = 0.1;
/// Scale floor for `ScaleCamera` (B7) — below this the camera would be too small to see.
pub const CAMERA_SCALE_MIN: f32 = 0.2;
/// Scale ceiling for `ScaleCamera` (B7) — above this a single webcam would dwarf the canvas.
pub const CAMERA_SCALE_MAX: f32 = 3.0;

/// Clamps a candidate camera position to `CAMERA_POSITION_BOUND` on both axes. Pure, so
/// the sanity bound is proven by unit tests without a real engine process.
pub fn clamp_camera_position(x: i32, y: i32) -> (i32, i32) {
    (x.clamp(-CAMERA_POSITION_BOUND, CAMERA_POSITION_BOUND), y.clamp(-CAMERA_POSITION_BOUND, CAMERA_POSITION_BOUND))
}

/// Clamps a candidate camera scale factor to `[CAMERA_SCALE_MIN, CAMERA_SCALE_MAX]`. Pure,
/// same reason as `clamp_camera_position`.
pub fn clamp_camera_scale(scale: f32) -> f32 {
    scale.clamp(CAMERA_SCALE_MIN, CAMERA_SCALE_MAX)
}

/// One destination for `StartMultistream` (B3): a platform id (`"twitch"`, `"youtube"`) and
/// its RTMP server, both non-secret. The stream key never travels here — the engine reads
/// it from `HIKARI_RTMP_KEY_<ID>` (uppercased `id`), exactly the pattern `StartStream`
/// already uses for its single target.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StreamTarget {
    pub id: String,
    pub server: String,
}

/// Why a target list was rejected before ever reaching the engine — checked on the
/// controller side so a malformed batch never even gets sent.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MultistreamError {
    /// `targets` was empty: multistream with 0 destinations is not a valid request.
    NoTargets,
    /// Two (or more) targets shared the same `id` — the engine could not tell their
    /// `PlatformStarted`/`PlatformError` reports apart.
    DuplicateId { id: String },
}

/// Validates a target list before it is sent as `StartMultistream` (B3). Pure and total —
/// no I/O, no libobs — so the business rule ("at least 1 target, ids unique") is proven by
/// unit tests without a real engine process. Duplicate-id detection happens in a single
/// pass with a `HashSet`, which the roundtrip `Vec` order does not affect.
pub fn validate_targets(targets: &[StreamTarget]) -> Result<(), MultistreamError> {
    if targets.is_empty() {
        return Err(MultistreamError::NoTargets);
    }
    let mut seen = std::collections::HashSet::new();
    for target in targets {
        if !seen.insert(&target.id) {
            return Err(MultistreamError::DuplicateId { id: target.id.clone() });
        }
    }
    Ok(())
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
