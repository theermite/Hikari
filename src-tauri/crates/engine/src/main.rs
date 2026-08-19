//! Hikari — engine process (ADR-013). Loads `libobs` in ITS OWN process (the controller
//! launches it by path, never links it) and reports over the JSON-line wire protocol
//! (`hikari-protocol`, ADR-011).
//!
//! B1a: initialize libobs, build a scene with a screen (monitor) capture, emit the scene's
//! sources. B1b: create a native preview window (`obs_display`), announce its HWND
//! (`PreviewReady`), stay alive so the controller can graft that window into the Tauri app
//! (cross-process `SetParent`, proven at the `spikes/b1b-preview` spike). B2a (this file,
//! extended): real RTMP streaming on `StartStream`/`StopStream`, target read from the
//! engine's OWN environment (never over the wire — OAuth/vault target is B2b).
//!
//! API transcribed from the proven spikes (B0.0 for the scene/sources/streaming, B1b for
//! the preview window + wire announcement). This is the integrated port, not throwaway code.
//!
//! Split by domain (2026-08-20, file over the 500-line ceiling): [`lifecycle_ops`] (startup,
//! stream/multistream) · [`scene_ops`] (create/switch/delete scene) · [`camera_ops`] (the
//! physical webcam) · [`source_ops`] (captures in a scene) · [`audio_ops`] (the mixer) ·
//! [`drag_ops`] (mouse placement, B7) · [`event_loop`] (the winit `ApplicationHandler`) ·
//! [`stdin_reader`] (parses `ControllerCommand` lines) · [`bootstrap`] (`run()` + the two
//! one-shot detection modes). Every `impl App` block below is one MORE inherent impl of the
//! same type — Rust merges them at compile time, so nothing here changed behaviour.

mod audio;
mod audio_ops;
mod bootstrap;
mod camera;
mod camera_ops;
mod drag_ops;
mod event_loop;
mod filters;
mod lifecycle_ops;
mod multistream;
mod outline;
mod scene_ops;
mod scenes;
mod source_ops;
mod sources;
mod stdin_reader;
mod stream;

use std::io::Write;

use anyhow::Result;
use hikari_protocol::{ControllerCommand, EngineMessage};
use libobs_wrapper::display::ObsDisplayRef;
use libobs_wrapper::scenes::ObsSceneItemRef;
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::unsafe_send::Sendable;
use multistream::PlatformStream;
use stream::StreamState;
use winit::window::Window;

/// The display name given to the scene's screen-capture source.
const MONITOR_CAPTURE_NAME: &str = "Monitor Capture";
/// Preview window's own resolution before it is grafted (the controller resizes it to
/// fit the app once grafted — this is just a sane starting size).
const PREVIEW_START_WIDTH: u32 = 960;
const PREVIEW_START_HEIGHT: u32 = 540;
const TARGET_ASPECT: f32 = 16.0 / 9.0;
/// How often the mixer's level bars are refreshed (B6). Fast enough that a bar tracks the
/// voice rather than lagging behind it, slow enough not to flood the pipe — the frame
/// counters' two-second beat would make the bars lurch, hence a separate cadence.
const AUDIO_LEVEL_INTERVAL: std::time::Duration = std::time::Duration::from_millis(50);

/// Emit one protocol message as a single JSON line on stdout. A serialization failure is
/// reported on stderr rather than swallowed (it must never crash the engine). `pub(crate)`
/// so every domain module can report the same way.
pub(crate) fn emit(msg: &EngineMessage) {
    match hikari_protocol::to_line(msg) {
        Ok(line) => println!("{line}"),
        Err(err) => eprintln!("[engine] failed to serialize {msg:?}: {err}"),
    }
}

/// Keeps the 16:9 aspect ratio when the controller resizes the grafted window (cross-process
/// `MoveWindow`, proven at the spike). Pure aspect-fit math, transcribed unchanged.
pub(crate) fn fit_size(win_w: u32, win_h: u32) -> (u32, u32) {
    // Clamp BOTH dimensions before any arithmetic — see the sibling `fit_size` in
    // `preview_bridge.rs` (a test there caught a 0×0 defect from clamping only the ratio
    // comparison, not the branch arithmetic).
    let win_w = win_w.max(1);
    let win_h = win_h.max(1);
    if win_w as f32 / win_h as f32 > TARGET_ASPECT {
        ((((win_h as f32) * TARGET_ASPECT) as u32).max(1), win_h)
    } else {
        (win_w, (((win_w as f32) / TARGET_ASPECT) as u32).max(1))
    }
}

/// The state that must be dropped in this exact order: the display FIRST, then the OBS
/// context. Field declaration order IS drop order in Rust — this used to be reversed
/// (`context` declared before `display`), which freed the context while the display still
/// held references, causing an extra libobs memory leak (2 instead of the 1 documented,
/// upstream-known leak). Found + fixed after the spike (dette noted in its README).
struct ObsInner {
    display: ObsDisplayRef,
    context: libobs_wrapper::context::ObsContext,
    /// The real, currently-composed scene sources — grown by `handle_add_camera`. Kept
    /// here (never re-derived from libobs) so every `Sources` emission reflects the whole
    /// scene, never just the last-added delta.
    sources: Vec<hikari_protocol::SourceInfo>,
    /// The ONE physical webcam source (Jay, 2026-07-24: "la caméra est unique"), created the
    /// first time any scene adds a camera. Reused (never rebuilt) for every later scene.
    camera_source: Option<ObsSourceRef>,
    /// L'appareil derrière la caméra — retenu pour que l'app puisse la recréer au lancement
    /// suivant. Une seule caméra physique, donc une seule valeur.
    camera_device_id: Option<String>,
    /// The two one-way filters attached to `camera_source`, created once alongside it and
    /// toggled in place per scene (`camera::set_filter_enabled`) — never removed/rebuilt.
    camera_filters: Option<CameraFilters>,
    /// Which scenes currently show the camera, and their own scene item (position/scale
    /// are per scene — the same source can sit differently in each). Keyed by scene name.
    camera_items: std::collections::HashMap<String, ObsSceneItemRef<ObsSourceRef>>,
    /// Each scene's OWN desired filter state (fond IA, masque) — applied to the shared
    /// filters only when that scene is the one live on the output channel (`SwitchScene`),
    /// the "scene automation toggles my filters" flow Jay already uses in OBS today.
    scene_filter_state: std::collections::HashMap<String, (bool, bool)>,
    /// The scene currently live on the output channel (multi-scene, tranche 1) — libobs
    /// exposes no "which scene is on this channel" getter, so this is the one piece of
    /// state the engine must track itself rather than read back.
    active_scene: String,
    /// Every source of the ACTIVE scene with its rectangle, FRONT-FIRST — cached (B7).
    ///
    /// WHY front-first: a click designates the source the user actually sees, so the hit
    /// test walks the stack from the top down and stops at the first match.
    ///
    /// WHY a cache: the cursor shape is decided on EVERY mouse move, and measuring one
    /// source costs four round-trips to the OBS thread (position, scale, size, stack
    /// order). Doing that per source per move made the preview stutter. The cache is exact
    /// rather than approximate because nothing but this engine moves these sources — every
    /// writer clears it through `scene_layout_changed`.
    item_rects: Option<Vec<ItemRect>>,
    /// The mixer (B6) — audio sources in insertion order, so a source keeps its channel and
    /// its place in the panel for its whole life.
    audio: Vec<MixerSource>,
    /// What each scene holds (brique Sources), in the order the user added it. Keyed by
    /// scene name. The camera lives in `camera_items` instead — it is ONE physical source
    /// shared across scenes, a rule this generic list would break.
    scene_sources: std::collections::HashMap<String, Vec<SceneSource>>,
    /// The `(scene, source name)` pairs locked against the mouse (brique Sources).
    ///
    /// Keyed by the PAIR rather than stored on `SceneSource`, so the camera obeys the same
    /// lock without being pulled into that list — it is one physical source shared across
    /// scenes, and its lock is per scene like its placement. Absent from the set = free.
    locked: std::collections::HashSet<(String, String)>,
}

/// Where one source of the active scene sits, in canvas pixels.
struct ItemRect {
    name: String,
    x: f32,
    y: f32,
    width: f32,
    height: f32,
}

/// One capture the user put into a scene.
struct SceneSource {
    name: String,
    /// The libobs source-kind id, kept so the panel can show what it is without asking.
    kind: String,
    /// Sa famille et ce qu'elle capture — gardés pour que l'app puisse la RECRÉER au
    /// lancement suivant. Sans eux, une session sauvegardée ne serait pas rejouable.
    source_kind: hikari_protocol::SourceKind,
    target_id: String,
    item: ObsSceneItemRef<ObsSourceRef>,
}

/// One libobs capture behind a mixer entry, with everything the engine must free later.
struct LiveCapture {
    source: ObsSourceRef,
    /// The libobs output channel it occupies. Kept explicitly so removing it frees the right
    /// channel — recomputing it from list order would free the wrong one once any earlier
    /// capture has been removed.
    channel: u32,
    /// The room-noise suppression filter, created alongside the capture when the kind
    /// supports it, then toggled in place. `None` on desktop sound, which has no room noise.
    noise_filter: Option<libobs_wrapper::sources::ObsFilterRef>,
}

/// One entry in the mixer — what the user sees as a single device.
///
/// It can be backed by TWO libobs captures of the same device. WHY: libobs has ONE volume
/// per source, applied to both the stream and the headphones, so a single capture cannot
/// have an audience volume and a headphone volume at once (OBS has the same limit). When the
/// user asks for "both hear it", the engine opens a second capture routed to the headphones
/// only — each capture then carries its own volume. Decision Jay, 2026-08-05: the second
/// capture costs CPU, and a few devices refuse to be opened twice; that is accepted, because
/// the alternative is the multi-tool assembly Hikari exists to remove.
struct MixerSource {
    name: String,
    kind: hikari_protocol::AudioSourceKind,
    /// The capture the AUDIENCE hears. Absent when only the streamer listens.
    public: Option<LiveCapture>,
    /// The capture the STREAMER hears. Absent when only the audience listens.
    monitor: Option<LiveCapture>,
    /// The live level meter, attached to whichever capture exists. `None` when libobs
    /// refused — a missing bar costs a display, never the sound.
    meter: Option<audio::LevelMeter>,
    /// Slider positions, remembered so unmuting restores exactly what the user chose.
    volume_percent: i32,
    monitor_volume_percent: i32,
    muted: bool,
    monitoring: hikari_protocol::AudioMonitoring,
    noise_suppression: bool,
    noise_method: hikari_protocol::NoiseMethod,
    noise_level_db: f32,
    /// The device this entry captures, kept so a second capture can be opened later without
    /// asking the panel again.
    device_id: String,
}

impl MixerSource {
    /// Every capture currently open behind this entry.
    fn captures(&self) -> impl Iterator<Item = &LiveCapture> {
        self.public.iter().chain(self.monitor.iter())
    }
}

/// An in-progress camera gesture (B7, souris) — a move or a resize, decided at press time
/// by where the cursor was.
enum DragState {
    /// Moving. `grab_offset` is where inside the source the user grabbed it, in canvas
    /// pixels. Keeping that offset is what makes the source follow the cursor instead of
    /// jumping so its corner snaps under the pointer on the first move.
    Move { name: String, grab_offset_x: f32, grab_offset_y: f32 },
    /// Resizing from a corner. `anchor` is the OPPOSITE corner, in canvas pixels — it stays
    /// pinned for the whole gesture, so the source grows away from a fixed point instead of
    /// sliding while it resizes. Read once at press time: re-deriving it from the live
    /// rectangle each move would chase its own changes.
    Resize {
        name: String,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    },
}

/// The two one-way filters a camera source carries once created — kept together since
/// they're always created/toggled as a pair alongside `camera_source`.
struct CameraFilters {
    background_removal: libobs_wrapper::sources::ObsFilterRef,
    circle_mask: libobs_wrapper::sources::ObsFilterRef,
}

/// Commands forwarded from the stdin-reader thread to the event loop (winit's
/// `EventLoopProxy` is the documented cross-thread wake-up mechanism — libobs calls only
/// ever happen on the winit/event-loop thread, never on the stdin-reader thread itself).
enum EngineEvent {
    Exit,
    StartStream,
    StopStream,
    StartMultistream { targets: Vec<hikari_protocol::StreamTarget> },
    StopMultistream,
    AddCamera { device_id: String, scene: String },
    SetBackgroundRemoval { scene: String, enabled: bool },
    SetCircleMask { scene: String, enabled: bool },
    RemoveCamera { scene: String },
    NudgeCamera { scene: String, dx: i32, dy: i32 },
    ScaleCamera { scene: String, grow: bool },
    CreateScene { name: String },
    SwitchScene { name: String },
    DeleteScene { name: String },
    ListAudioDevices,
    AddAudioSource { device_id: String, kind: hikari_protocol::AudioSourceKind, name: String },
    RemoveAudioSource { name: String },
    SetAudioVolume { name: String, percent: i32 },
    SetAudioMuted { name: String, muted: bool },
    SetAudioMonitoring { name: String, monitoring: hikari_protocol::AudioMonitoring },
    SetNoiseSettings {
        name: String,
        enabled: bool,
        method: hikari_protocol::NoiseMethod,
        level_db: f32,
    },
    SetMonitorVolume { name: String, percent: i32 },
    ListCaptureTargets,
    AddCaptureSource {
        scene: String,
        kind: hikari_protocol::SourceKind,
        target_id: String,
        name: String,
    },
    RemoveSource { scene: String, name: String },
    ReorderSource { scene: String, name: String, direction: hikari_protocol::SourceOrder },
    SetSourceTransform { scene: String, name: String, x: i32, y: i32, scale_percent: i32 },
    SetSourceLocked { scene: String, name: String, locked: bool },
}

/// `stream` and `multistream` MUST be declared before `obs`: their outputs depend on
/// `obs.context` (same libobs context), and Rust drops struct fields in declaration order
/// (see `ObsInner`'s own comment for the exact class of bug this prevents — an
/// `ObsOutputRef` dropped after its parent context would either leak or touch an
/// already-destroyed context). The normal exit path (`exiting()`) already stops both and
/// clears `obs` in the right order; this field order is the belt-and-braces guard for an
/// abnormal drop (e.g. a future winit
/// callback panic) that would skip `exiting()` and drop `App` directly.
struct App {
    window: Option<Sendable<Window>>,
    stream: Option<StreamState>,
    multistream: Vec<PlatformStream>,
    /// When multistream frame stats were last reported — a single shared tick for the
    /// whole batch (unlike `StreamState`, `PlatformStream` doesn't carry its own timer,
    /// since every target reports on the same cadence).
    multistream_last_stats_at: std::time::Instant,
    /// When the mixer's levels were last reported (B6) — its own beat, much faster than the
    /// frame counters'.
    audio_last_levels_at: std::time::Instant,
    /// Last known cursor position in the preview window, in physical pixels. winit reports
    /// press/release WITHOUT coordinates, so the position has to be remembered from the
    /// preceding move event.
    cursor: Option<(f32, f32)>,
    /// The preview's fitted size, kept in step with `Resized` — the divisor that turns a
    /// preview pixel into a canvas pixel.
    fitted: (u32, u32),
    /// The drag in progress, if any (B7, glisser-souris).
    drag: Option<DragState>,
    obs: Option<ObsInner>,
}

fn main() -> Result<()> {
    let outcome = if std::env::args().any(|arg| arg == "--detect-encoders") {
        bootstrap::detect_encoders_and_exit()
    } else if std::env::args().any(|arg| arg == "--detect-cameras") {
        bootstrap::detect_cameras_and_exit()
    } else {
        bootstrap::run()
    };
    if let Err(err) = outcome {
        // Report the failure on the wire before dying, so the controller never sees a
        // silent death (B0.0 lesson: a mute failure costs a day).
        emit(&EngineMessage::Error { message: err.to_string() });
        std::io::stdout().flush().ok();
        return Err(err);
    }
    Ok(())
}

// No `cargo test` target here: `test = false` in Cargo.toml disables the harness because
// linking libobs (obs.dll) prevents a test binary from even loading headless. The pure,
// headless-testable protocol logic is covered in the `hikari-protocol` crate; the pure
// preview graft math (`fit_size`, `child_style_bits`) is duplicated (tiny, 3-5 lines) on
// the controller side in `preview_bridge.rs`, where it IS unit-tested (no libobs there).
// The real libobs scene + preview build is validated by RUNNING `hikari-engine` with the
// OBS runtime (integration regime, like the B0.0/B1b spikes).
