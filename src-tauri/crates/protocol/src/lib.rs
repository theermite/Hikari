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

/// The libobs source-kind identifier for a game / fullscreen-application capture — the id
/// the real win-capture plugin registers (verified 2026-08-05 in `libobs-simple` 8.0.1,
/// which mirrors obs-studio's own).
pub const GAME_CAPTURE_KIND: &str = "game_capture";

/// The libobs source-kind identifier for a single-window capture. Same verification.
pub const WINDOW_CAPTURE_KIND: &str = "window_capture";

/// What a capture source points at (brique Sources).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    /// A game or fullscreen application — the fast path, hooks the app directly.
    Game,
    /// One window, whatever it is. Works where the game hook cannot.
    Window,
    /// A whole screen.
    Monitor,
    /// A still image on disk — logo, overlay, waiting screen.
    Image,
    /// A video file on disk, played in a loop.
    Video,
}

impl SourceKind {
    /// The libobs source id to build. A wrong id yields a source libobs silently refuses.
    pub fn libobs_id(self) -> &'static str {
        match self {
            SourceKind::Game => GAME_CAPTURE_KIND,
            SourceKind::Window => WINDOW_CAPTURE_KIND,
            SourceKind::Monitor => MONITOR_CAPTURE_KIND,
            SourceKind::Image => IMAGE_SOURCE_KIND,
            SourceKind::Video => VIDEO_SOURCE_KIND,
        }
    }

    /// Whether this kind designates a FILE on disk rather than something to capture live.
    /// The panel asks for a file instead of listing targets.
    pub fn is_file(self) -> bool {
        matches!(self, SourceKind::Image | SourceKind::Video)
    }
}

/// The libobs source-kind identifier for a still image — the real obs-studio image-source
/// plugin id (verified 2026-08-05 against its source).
pub const IMAGE_SOURCE_KIND: &str = "image_source";
/// The property carrying the image's path.
pub const IMAGE_PATH_PROPERTY: &str = "file";

/// The libobs source-kind identifier for a media file. Same verification, obs-ffmpeg plugin.
pub const VIDEO_SOURCE_KIND: &str = "ffmpeg_source";
/// The property carrying the video's path. Different from the image's — a shared name would
/// have been convenient and is simply not what OBS uses.
pub const VIDEO_PATH_PROPERTY: &str = "local_file";

/// One thing the user can capture: a game, a window, or a screen. `id` is the exact value
/// libobs expects in the source's own setting, never rebuilt by hand; `label` is what the
/// user reads.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CaptureTarget {
    pub id: String,
    pub label: String,
}

/// Which way a source moves in the stack of a scene (brique Sources).
///
/// Said in what the user sees — in front of or behind the others — never in list-index
/// terms, which nobody can picture.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceOrder {
    /// Closer to the viewer: drawn over the others.
    Front,
    /// Further away: drawn under the others.
    Back,
}

/// One source inside a scene, as the engine really holds it.
///
/// Carries everything needed to RECREATE it identically at the next launch — kind, what it
/// points at, and where it sits. Anything missing here is a setting the user would have to
/// redo by hand, so the completeness of this struct IS the persistence guarantee.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SceneSourceInfo {
    pub name: String,
    /// The libobs source-kind id, so a panel can show the right icon without guessing.
    pub kind: String,
    /// Which family it belongs to — what a rebuild needs, the libobs id alone being a
    /// display detail.
    pub source_kind: SourceKind,
    /// What it captures: a window id, a monitor id, or a file path.
    pub target_id: String,
    /// Where it sits in the canvas, and how big — the placement the user chose with the
    /// mouse, worth exactly as much as the source itself.
    pub x: i32,
    pub y: i32,
    pub scale_percent: i32,
}

/// Validates a candidate source name against the sources ALREADY IN THAT SCENE.
///
/// Same two rules as a scene name, and the same reason to enforce them early: libobs
/// silently renames a duplicate ("Webcam 2"), after which the panel no longer finds the
/// source it thinks it is naming.
pub fn validate_source_name(name: &str, existing: &[String]) -> Result<(), SceneNameError> {
    validate_scene_name(name, existing)
}

/// What one scene currently holds, as the engine really sees it (multi-scene, tranche 3).
///
/// WHY per scene rather than "the active one": the Scenes panel shows the whole list at
/// once, so it must say what EACH scene carries without the user having to switch to it
/// just to find out — switching is a live cut on the output channel, never a free peek.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    /// Everything this scene holds, in the order it was added — so the panel shows a
    /// scene's contents without switching to it (switching is a live cut, never a peek).
    pub sources: Vec<SceneSourceInfo>,
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
            sources: Vec::new(),
        }
    }
}

/// The libobs source-kind identifier for a Windows microphone / line-in capture — the id
/// the real win-wasapi plugin registers (verified 2026-08-04 against obs-studio source).
pub const AUDIO_INPUT_KIND: &str = "wasapi_input_capture";

/// The libobs source-kind identifier for a Windows speaker / desktop-audio capture. Same
/// source, same verification.
pub const AUDIO_OUTPUT_KIND: &str = "wasapi_output_capture";

/// Which side of the sound card an audio source listens to (B6).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioSourceKind {
    /// A microphone or line-in — what the streamer says.
    Input,
    /// Desktop audio — what the machine plays (game, music, calls).
    Output,
}

impl AudioSourceKind {
    /// The libobs source id to build for this side.
    pub fn libobs_id(self) -> &'static str {
        match self {
            AudioSourceKind::Input => AUDIO_INPUT_KIND,
            AudioSourceKind::Output => AUDIO_OUTPUT_KIND,
        }
    }

    /// Whether offering noise suppression on this side makes sense.
    ///
    /// Only a microphone carries room noise — fan, keyboard, street. Desktop sound is an
    /// already-digital signal: the filter has nothing to remove there, and would damage
    /// music while trying to clean up a voice it cannot find.
    pub fn supports_noise_suppression(self) -> bool {
        matches!(self, AudioSourceKind::Input)
    }
}

/// The libobs filter id for noise suppression — the real obs-filters plugin id, verified
/// 2026-08-04 against obs-studio source.
pub const NOISE_SUPPRESS_FILTER_KIND: &str = "noise_suppress_filter";

/// How the room noise is removed (B6).
///
/// Counter-intuitive but verified twice in the obs-filters source (2026-08-04): the
/// *machine-learning* method is the one with NO dial, and the *older* one is the adjustable
/// one. OBS itself hides the level field when RNNoise is picked.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NoiseMethod {
    /// Speex — the adjustable one. Lighter on the CPU, and its strength is a dial.
    Speex,
    /// RNNoise — the machine-learning one. Cleaner result, no setting at all, costs more CPU.
    Rnnoise,
}

impl NoiseMethod {
    /// The exact value the filter's `method` property expects.
    pub fn libobs_value(self) -> &'static str {
        match self {
            NoiseMethod::Speex => "speex",
            NoiseMethod::Rnnoise => "rnnoise",
        }
    }

    /// Whether this method exposes a strength to set. Only Speex does — showing a dial for
    /// RNNoise would be inventing a setting that does not exist.
    pub fn has_level(self) -> bool {
        matches!(self, NoiseMethod::Speex)
    }
}

/// The libobs property name carrying Speex's strength.
pub const NOISE_LEVEL_PROPERTY: &str = "suppress_level";
/// Strongest suppression Speex accepts, in decibels (obs-filters source, 2026-08-04).
pub const NOISE_LEVEL_MIN_DB: f32 = -60.0;
/// Weakest suppression Speex accepts.
pub const NOISE_LEVEL_MAX_DB: f32 = 0.0;
/// OBS's own default, kept so a Hikari user and an OBS user hear the same thing.
pub const NOISE_LEVEL_DEFAULT_DB: f32 = -30.0;

/// Clamps a Speex strength into the range the filter accepts. A non-finite value falls back
/// to the default rather than reaching libobs.
pub fn clamp_noise_level(level_db: f32) -> f32 {
    if !level_db.is_finite() {
        return NOISE_LEVEL_DEFAULT_DB;
    }
    level_db.clamp(NOISE_LEVEL_MIN_DB, NOISE_LEVEL_MAX_DB)
}

/// One audio device libobs reports on this machine. `device_id` is the exact value the
/// wasapi source's `device_id` property expects, never hand-built.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AudioDevice {
    pub name: String,
    pub device_id: String,
}

/// One entry in the mixer, and its live settings.
///
/// One entry can be backed by TWO libobs sources — see [`ControllerCommand::SetMonitorVolume`]
/// for why. The panel never sees that: it reads one row with two volumes.
///
/// `PartialEq` but not `Eq`: `noise_level_db` is a float.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioSourceInfo {
    pub name: String,
    pub kind: AudioSourceKind,
    /// 0–100, the slider position for what the AUDIENCE hears — never the raw libobs
    /// multiplier, so the panel never has to know the audio scale.
    pub volume_percent: i32,
    /// 0–100, the slider position for what the STREAMER hears in their headphones.
    /// Meaningful only when `monitoring` includes them.
    pub monitor_volume_percent: i32,
    pub muted: bool,
    /// Whether the streamer hears this source, and whether the audience does.
    pub monitoring: AudioMonitoring,
    /// Whether room-noise suppression is on. Always `false` on a source whose kind does not
    /// support it (see [`AudioSourceKind::supports_noise_suppression`]).
    pub noise_suppression: bool,
    pub noise_method: NoiseMethod,
    /// Speex's strength. Carried even when the method is RNNoise, so switching back and
    /// forth does not lose what the user had set.
    pub noise_level_db: f32,
}

/// One source's current loudness, as libobs measures it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioLevel {
    pub name: String,
    /// Magnitude in decibels, ALWAYS finite. `0` is the loudest undistorted signal;
    /// silence is [`METER_FLOOR_DB`]. Build it with [`AudioLevel::new`], never by hand.
    pub magnitude_db: f32,
}

impl AudioLevel {
    /// Builds a level the wire can actually carry, clamping silence and broken readings to
    /// [`METER_FLOOR_DB`].
    ///
    /// WHY this exists (regression 2026-08-04): libobs reports silence as `-inf`, and JSON
    /// has no way to write a non-finite number — `serde_json` emits `null`, which then fails
    /// to parse back as `f32`. The failure is not local: the WHOLE `AudioLevels` message is
    /// rejected, so one muted source froze every other source's bar. A level is clamped at
    /// the boundary rather than trusted from the caller.
    pub fn new(name: impl Into<String>, magnitude_db: f32) -> Self {
        Self {
            name: name.into(),
            magnitude_db: if magnitude_db.is_finite() {
                magnitude_db
            } else if magnitude_db == f32::INFINITY {
                0.0
            } else {
                METER_FLOOR_DB
            },
        }
    }
}

/// Whether a source is played back to the streamer's own ears, and whether the audience
/// hears it too (B6). Mirrors libobs's own three monitoring states.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioMonitoring {
    /// The audience hears it, the streamer does not (their ears already hear the room).
    /// libobs's default, and the right one for a microphone on speakers — monitoring a mic
    /// out loud is how a feedback loop starts.
    None,
    /// The streamer hears it, the audience does not. For checking a source privately.
    MonitorOnly,
    /// Both hear it. For a source the machine plays but the streamer's headphones do not
    /// already receive.
    MonitorAndOutput,
}

/// The quietest level the meter shows. Below this the bar is simply empty — a meter that
/// stretched to `-inf` would spend its whole length on silence nobody can hear.
pub const METER_FLOOR_DB: f32 = -60.0;

/// Turns a decibel reading into a `0.0..=1.0` bar length. Linear in decibels, which is how
/// loudness is actually perceived — a linear-in-amplitude bar would sit near zero for every
/// normal speaking level.
pub fn db_to_meter_fraction(db: f32) -> f32 {
    if !db.is_finite() {
        // libobs reports silence as -inf; NaN would come from a broken reading. Both mean
        // "show nothing" rather than "crash the bar".
        return if db == f32::INFINITY { 1.0 } else { 0.0 };
    }
    (1.0 - db / METER_FLOOR_DB).clamp(0.0, 1.0)
}

/// Turns a 0–100 slider into the multiplier libobs applies to the signal. Clamped, so a
/// malformed command can never boost the sound past unity or invert it.
pub fn percent_to_volume(percent: i32) -> f32 {
    percent.clamp(0, 100) as f32 / 100.0
}

/// Turns a libobs multiplier back into a 0–100 slider position.
pub fn volume_to_percent(volume: f32) -> i32 {
    if !volume.is_finite() {
        return 0;
    }
    (volume * 100.0).round().clamp(0.0, 100.0) as i32
}

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
    /// The engine re-checks [`validate_scene_deletion`] and answers `Error` rather than
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

/// Distance d'accroche de l'aimantation, en pixels de canevas (B7).
///
/// Assez large pour attraper sans viser, assez courte pour qu'une source posée volontairement
/// à 30 pixels d'un bord y reste.
pub const SNAP_DISTANCE: f32 = 16.0;

/// Colle une source aux repères du cadre quand elle en approche : les quatre bords, et les
/// deux axes centraux.
///
/// L'aimantation CORRIGE, elle ne téléporte pas — une position ne bouge jamais de plus de
/// [`SNAP_DISTANCE`], propriété épinglée par un proptest. Loin de tout repère, la source suit
/// la souris au pixel près : aimanter ce qu'on place volontairement de travers serait pire
/// que ne rien aimanter.
pub fn snap_position(
    x: f32,
    y: f32,
    width: f32,
    height: f32,
    canvas_w: u32,
    canvas_h: u32,
) -> (f32, f32) {
    let snap_axis = |value: f32, targets: [f32; 3]| {
        targets
            .into_iter()
            .filter(|target| target.is_finite() && (value - target).abs() <= SNAP_DISTANCE)
            // Le repère le plus proche gagne, jamais le premier trouvé : deux repères
            // voisins (un bord et le centre sur une petite source) doivent départager.
            .min_by(|a, b| {
                (value - a).abs().total_cmp(&(value - b).abs())
            })
            .unwrap_or(value)
    };
    let (canvas_w, canvas_h) = (canvas_w as f32, canvas_h as f32);
    (
        snap_axis(x, [0.0, canvas_w - width, (canvas_w - width) / 2.0]),
        snap_axis(y, [0.0, canvas_h - height, (canvas_h - height) / 2.0]),
    )
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

/// Which corner of the camera the cursor is over (B7, redimensionnement à la souris).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Corner {
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
}

impl Corner {
    /// Whether the corner OPPOSITE this one — the one that stays put while resizing — is on
    /// the left, and on the top. Those two flags are all `resize_box` needs to place the
    /// rectangle without a second match.
    pub fn anchor_side(self) -> (bool, bool) {
        match self {
            Corner::TopLeft => (false, false),
            Corner::TopRight => (true, false),
            Corner::BottomLeft => (false, true),
            Corner::BottomRight => (true, true),
        }
    }
}

/// How close to a corner the cursor must be to grab it, in canvas pixels. Big enough to hit
/// comfortably, small enough that the middle of a small camera still means "move me".
pub const CORNER_GRAB_MARGIN: f32 = 32.0;

/// The corner under `(px, py)`, or `None` if the cursor is not near one — in which case the
/// caller treats the gesture as a move.
///
/// A corner wins over the body on purpose: on a small camera the four margins can cover most
/// of the surface, and resizing is the more precise intent. The rectangle must be at least
/// twice the margin on both axes for corners to be offered at all, otherwise a tiny camera
/// could never be moved again.
pub fn corner_at(px: f32, py: f32, x: f32, y: f32, w: f32, h: f32, margin: f32) -> Option<Corner> {
    if w < margin * 2.0 || h < margin * 2.0 || !is_inside(px, py, x, y, w, h) {
        return None;
    }
    let left = px <= x + margin;
    let right = px >= x + w - margin;
    let top = py <= y + margin;
    let bottom = py >= y + h - margin;
    match (left, right, top, bottom) {
        (true, _, true, _) => Some(Corner::TopLeft),
        (_, true, true, _) => Some(Corner::TopRight),
        (true, _, _, true) => Some(Corner::BottomLeft),
        (_, true, _, true) => Some(Corner::BottomRight),
        _ => None,
    }
}

/// The scale a resize gesture asks for: the cursor's horizontal distance from the anchor,
/// divided by the camera's native width. Width drives it alone so the aspect ratio is kept —
/// a webcam squashed on one axis is never what the user meant.
///
/// A zero base width yields `0.0` rather than infinity; the caller clamps the result anyway
/// (`clamp_camera_scale`), so a degenerate source can't produce an absurd size.
pub fn resize_scale(anchor_x: f32, cursor_x: f32, base_w: u32) -> f32 {
    if base_w == 0 {
        return 0.0;
    }
    (cursor_x - anchor_x).abs() / base_w as f32
}

/// Where the resized rectangle starts, given the anchor corner that must stay put. The
/// anchor is the corner OPPOSITE the one being dragged: grabbing bottom-right pins top-left,
/// so the camera grows away from a fixed point instead of sliding while it resizes.
pub fn resize_box(
    anchor_x: f32,
    anchor_y: f32,
    anchor_is_left: bool,
    anchor_is_top: bool,
    new_w: f32,
    new_h: f32,
) -> (f32, f32) {
    (
        if anchor_is_left { anchor_x } else { anchor_x - new_w },
        if anchor_is_top { anchor_y } else { anchor_y - new_h },
    )
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
