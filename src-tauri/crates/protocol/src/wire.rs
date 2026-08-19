//! The JSON-line wire itself (ADR-011): the two tagged enums exchanged between the
//! controller and the engine, multistream target validation, and line (de)serialization.

use serde::{Deserialize, Serialize};
use serde::de::DeserializeOwned;

use crate::audio::{AudioDevice, AudioMonitoring, AudioSourceInfo, AudioLevel, AudioSourceKind, NoiseMethod};
use crate::scenes::SceneInfo;
use crate::sources::{CameraDevice, CaptureTarget, SourceInfo, SourceKind, SourceOrder};

/// Messages the engine emits toward the controller (engine -> controller), one per line.
///
/// `PartialEq` but not `Eq`: `AudioLevel` carries a decibel reading, and a float has no
/// total equality. Comparisons (tests, dedup) still work; only a `HashSet`-style use would
/// need `Eq`, and nothing compares engine messages that way.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    /// The audio devices libobs reports on this machine (B6) — answering `ListAudioDevices`.
    /// Never a presumed list, same rule as `Cameras`.
    AudioDevices { inputs: Vec<AudioDevice>, outputs: Vec<AudioDevice> },
    /// Every audio source in the mixer with its live settings — emitted after any mixer
    /// change, so a late-opening panel sees the real state.
    AudioSources { items: Vec<AudioSourceInfo> },
    /// Live loudness per source, emitted on a periodic tick while sources exist. Sent as a
    /// batch rather than one message per source: they are read on the same tick, and one
    /// line per source per tick would flood the pipe.
    AudioLevels { levels: Vec<AudioLevel> },
    /// Everything the machine can capture right now (brique Sources) — answering
    /// `ListCaptureTargets`. Read live from the system, never a presumed list: a game that
    /// was not running a minute ago must appear without restarting anything.
    CaptureTargets {
        games: Vec<CaptureTarget>,
        windows: Vec<CaptureTarget>,
        monitors: Vec<CaptureTarget>,
    },
}

/// Commands the controller sends to the engine (controller -> engine), one per line.
///
/// `PartialEq` but not `Eq`: `SetNoiseSettings` carries a decibel level, and a float has no
/// total equality. Comparisons still work; nothing hashes a command.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    /// The engine re-checks [`crate::scenes::validate_scene_deletion`] and answers `Error` rather than
    /// obeying blindly: deleting the last scene, or the live one with nowhere to fall back
    /// to, would leave the output channel with nothing to render.
    DeleteScene { name: String },
    /// Ask the engine to emit the machine's real audio devices (B6).
    ListAudioDevices,
    /// Adds a microphone or a desktop-audio capture to the mixer under `name`. `device_id`
    /// comes from `AudioDevices`, never guessed. Audio sources live on their own libobs
    /// channels, independent of scenes: sound keeps playing across a scene switch, exactly
    /// like OBS's own global audio mixer.
    AddAudioSource { device_id: String, kind: AudioSourceKind, name: String },
    /// Removes an audio source from the mixer and frees its channel.
    RemoveAudioSource { name: String },
    /// Sets a source's volume from a 0–100 slider position.
    SetAudioVolume { name: String, percent: i32 },
    /// Mutes or unmutes a source. Distinct from a zero volume: unmuting restores the slider
    /// where the user left it, so muting is never a destructive act.
    SetAudioMuted { name: String, muted: bool },
    /// Sets whether the streamer hears this source, and whether the audience does.
    SetAudioMonitoring { name: String, monitoring: AudioMonitoring },
    /// Sets room-noise suppression for a microphone: on/off, which method, and Speex's
    /// strength. One command rather than three because the settings panel edits them
    /// together, and a half-applied combination (RNNoise + a level) means nothing.
    ///
    /// The filter is attached once and toggled in place (`obs_source_set_enabled`), never
    /// rebuilt — a rebuild would interrupt the sound, exactly the blip the camera filters
    /// used to have.
    SetNoiseSettings { name: String, enabled: bool, method: NoiseMethod, level_db: f32 },
    /// Ask the engine for everything the machine can capture right now (brique Sources).
    ListCaptureTargets,
    /// Adds a capture of `target_id` into `scene`, named `name`.
    ///
    /// Sources belong to a SCENE, unlike audio which lives on global channels: that is the
    /// whole point of scenes — showing the game in one and a waiting screen in another.
    /// `target_id` comes from `CaptureTargets`, never guessed.
    AddCaptureSource { scene: String, kind: SourceKind, target_id: String, name: String },
    /// Removes a source from `scene` only. Other scenes keep theirs.
    RemoveSource { scene: String, name: String },
    /// Moves a source one step in front of, or behind, the others in `scene`. Which source
    /// hides which is a composition decision, so it belongs to the scene, not to the source.
    ReorderSource { scene: String, name: String, direction: SourceOrder },
    /// Places a source exactly, without going through the mouse.
    ///
    /// C'est ce qui rend une session REJOUABLE : au démarrage suivant, l'app recrée les
    /// sources puis les repose là où elles étaient. Sans cette commande, tout le placement
    /// serait à refaire à chaque lancement.
    SetSourceTransform { scene: String, name: String, x: i32, y: i32, scale_percent: i32 },
    /// Locks or unlocks `name` in `scene` against the mouse (brique Sources). A locked
    /// source is skipped by the click hit test, so it can be neither moved nor resized —
    /// it stays visible, still reorderable and still removable, because locking guards
    /// against the accidental gesture, never against the deliberate decision.
    ///
    /// Applies to the camera too, under its own name: it is the item most often nudged by
    /// accident, and excluding it would make the lock feel arbitrary.
    SetSourceLocked { scene: String, name: String, locked: bool },
    /// Sets the volume the STREAMER hears, independently of what the audience hears.
    ///
    /// WHY it needs its own command and its own plumbing: libobs has ONE volume per source,
    /// applied to both the stream and the headphones — verified in the raw bindings
    /// (2026-08-04), and OBS itself has the same limit. To make the two independent, an
    /// entry set to "both hear it" is backed by TWO libobs sources on the same device: one
    /// sent to the audience, one played back to the streamer, each carrying its own volume.
    /// The cost is a second capture of the device, which a few devices refuse.
    SetMonitorVolume { name: String, percent: i32 },
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
