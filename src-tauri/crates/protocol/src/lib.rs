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

/// What one scene currently holds, as the engine really sees it (multi-scene, tranche 3).
///
/// WHY per scene rather than "the active one": the Scenes panel shows the whole list at
/// once, so it must say what EACH scene carries without the user having to switch to it
/// just to find out — switching is a live cut on the output channel, never a free peek.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SceneInfo {
    pub name: String,
    /// Whether the ONE physical webcam is shown in this scene (`AddCamera`/`RemoveCamera`).
    pub has_camera: bool,
    /// This scene's OWN desired state for the NVIDIA background-removal filter — the value
    /// applied to the shared filter whenever this scene becomes live, not the filter's
    /// current global state (which belongs to whichever scene is live right now).
    pub background_removal: bool,
    /// This scene's OWN desired state for the circular mask filter. Same contract.
    pub circle_mask: bool,
}

impl SceneInfo {
    /// A scene that holds no camera and no filter preference — the shape every scene has
    /// the moment `CreateScene` makes it. Pure, so tests and the engine agree on "empty"
    /// instead of each spelling out four fields.
    pub fn empty(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            has_camera: false,
            background_removal: false,
            circle_mask: false,
        }
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
    /// The camera's current position/scale in `scene` after `NudgeCamera` or `ScaleCamera`
    /// (B7) — emitted with the real, clamped values (never presumed), so the panel reflects
    /// what actually happened rather than optimistically applying the requested delta.
    CameraTransform { scene: String, x: i32, y: i32, scale_percent: i32 },
    /// One multistream target failed — recoverable, reported instead of silently dropping
    /// that platform (B3 acceptance: "aucun échec silencieux"). The other targets are
    /// unaffected and keep streaming.
    PlatformError { id: String, message: String },
    /// Every scene the engine currently knows about (with what each one holds, tranche 3)
    /// and which one is live on the output channel — emitted after `CreateScene`,
    /// `SwitchScene`, `DeleteScene`, any camera/filter change, and once at startup, so a
    /// late-opening panel sees the real state, never an assumed one.
    SceneList { scenes: Vec<SceneInfo>, active: String },
}

/// Commands the controller sends to the engine (controller -> engine), one per line.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ControllerCommand {
    /// Create a scene with the given name.
    CreateScene { name: String },
    /// Ask the engine to emit the current scene's sources.
    ListSources,
    /// Puts the ONE physical webcam into `scene` (B-cam, multi-scene tranche 2). The same
    /// source is reused if it already exists elsewhere — never a 2nd device capture (Jay,
    /// 2026-07-24: "la caméra est unique"). `device_id` (from `EngineMessage::Cameras`,
    /// never guessed) matters only the very first time; later calls for a new scene reuse
    /// whatever device is already open.
    AddCamera { device_id: String, scene: String },
    /// Sets whether the real NVIDIA background-removal filter is enabled for `scene`
    /// (B-cam, F-036, multi-scene tranche 2). The filter itself is created once per camera
    /// and toggled in place (`obs_source_set_enabled`, real OBS per-filter switch — never a
    /// rebuild) — each scene keeps its OWN desired on/off state, applied whenever THAT scene
    /// becomes live (`SwitchScene`), exactly the "scene automation toggles my filters" flow
    /// Jay already uses in OBS today.
    SetBackgroundRemoval { scene: String, enabled: bool },
    /// Sets whether the circular alpha mask filter is enabled for `scene`. Same per-scene,
    /// per-filter toggle contract as `SetBackgroundRemoval`.
    SetCircleMask { scene: String, enabled: bool },
    /// Removes the webcam from `scene` only — other scenes keep showing it with their own
    /// filter state untouched. The physical source (and its filters) is only fully released
    /// once no scene shows it anymore. A no-op if `scene` doesn't show the camera.
    RemoveCamera { scene: String },
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
    /// Moves the webcam's placement WITHIN `scene` by `(dx, dy)` pixels (B7) — a fixed step
    /// decided by the panel's arrow buttons, never a raw drag delta (dockview's own drag
    /// broke silently in this WebView2 build, session 2026-07-23). Position is per scene
    /// (the same physical source can sit differently in each scene it appears in). A no-op
    /// if `scene` doesn't show the camera.
    NudgeCamera { scene: String, dx: i32, dy: i32 },
    /// Grows (`true`) or shrinks (`false`) the webcam's placement within `scene` by one
    /// fixed step (B7). Same per-scene scope as `NudgeCamera`.
    ScaleCamera { scene: String, grow: bool },
    /// Switches the live scene (multi-scene, tranche 1) — an instant cut on the output
    /// channel (`obs_set_output_source`), never a transition (that's B7's remaining scope).
    SwitchScene { name: String },
    /// Deletes the scene named `name` and everything scene-local it carried (its camera
    /// placement, its own filter preferences). The shared physical webcam survives as long
    /// as another scene still shows it — same release rule as `RemoveCamera`.
    ///
    /// The engine re-checks [`validate_scene_deletion`] and answers `Error` rather than
    /// obeying blindly: deleting the last scene, or the live one with nowhere to fall back
    /// to, would leave the output channel with nothing to render.
    DeleteScene { name: String },
}

/// Why a scene could not be deleted (multi-scene, tranche 3).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SceneDeleteError {
    /// No scene by that name exists — a stale panel, or a name that was already deleted.
    Unknown,
    /// It is the only scene left. Deleting it would leave the output channel empty, so
    /// the preview and the live stream would go black with nothing explaining why.
    LastScene,
}

/// Validates a deletion request against the scenes that exist. Pure and total — no libobs —
/// so both sides (panel before sending, engine before obeying) enforce the same two rules
/// from one implementation, same split as [`validate_scene_name`].
pub fn validate_scene_deletion(name: &str, existing: &[String]) -> Result<(), SceneDeleteError> {
    if !existing.iter().any(|s| s == name) {
        return Err(SceneDeleteError::Unknown);
    }
    if existing.len() <= 1 {
        return Err(SceneDeleteError::LastScene);
    }
    Ok(())
}

/// Why a candidate scene name was rejected before ever reaching the engine.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SceneNameError {
    /// An empty (or whitespace-only) name — not a name a person can recognize in a list.
    Empty,
    /// A scene with this exact name already exists.
    Duplicate,
}

/// Validates a candidate scene name against the scenes that already exist — pure and
/// total, so "no duplicate, no blank name" is proven by unit tests without a real engine
/// process (same split as `validate_targets`, B3).
pub fn validate_scene_name(name: &str, existing: &[String]) -> Result<(), SceneNameError> {
    if name.trim().is_empty() {
        return Err(SceneNameError::Empty);
    }
    if existing.iter().any(|s| s == name) {
        return Err(SceneNameError::Duplicate);
    }
    Ok(())
}

/// Clamp bounds for camera moves (B7) — a generous sanity range, not exact canvas
/// containment: it stops the camera drifting to absurd coordinates, it never guarantees
/// "stays inside the frame".
///
/// An earlier note here claimed the live canvas size was unreadable outside libobs's render
/// thread (`obs_get_video_info` behind a private dispatch). That was wrong:
/// `ObsRuntime::run_with_obs_result` is public, and `camera::canvas_size` reads it that way
/// since the drag brick (2026-08-04). The bound stays a deliberate sanity range all the
/// same — clamping to the exact canvas would forbid a camera deliberately parked
/// half-offscreen, which OBS allows.
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

/// Converts a point in the preview window into canvas coordinates (B7, glisser-souris).
///
/// The preview shows the whole canvas shrunk to the fitted area, so one preview pixel is
/// worth `canvas / fitted` canvas pixels — without that factor the camera would trail the
/// cursor at the wrong speed. Each axis scales independently: the fitted area keeps the
/// canvas aspect in practice, but nothing here depends on it.
///
/// A zero-sized preview really happens while a window is being minimized; it is treated as
/// one pixel so the result stays finite instead of becoming infinity or NaN.
pub fn window_to_canvas(
    cursor_x: f32,
    cursor_y: f32,
    fitted_w: u32,
    fitted_h: u32,
    canvas_w: u32,
    canvas_h: u32,
) -> (f32, f32) {
    let fitted_w = fitted_w.max(1) as f32;
    let fitted_h = fitted_h.max(1) as f32;
    (
        cursor_x * (canvas_w as f32) / fitted_w,
        cursor_y * (canvas_h as f32) / fitted_h,
    )
}

/// Whether `(px, py)` falls within the rectangle at `(x, y)` of size `w × h`. Edges count as
/// inside: grabbing the camera exactly on its border must work, otherwise the gesture
/// misses by one pixel for no visible reason. An empty rectangle contains nothing.
pub fn is_inside(px: f32, py: f32, x: f32, y: f32, w: f32, h: f32) -> bool {
    w > 0.0 && h > 0.0 && px >= x && px <= x + w && py >= y && py <= y + h
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
