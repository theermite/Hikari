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

mod audio;
mod camera;
mod filters;
mod multistream;
mod outline;
mod scenes;
mod sources;
mod stream;

use std::io::{BufRead, Write};
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use hikari_protocol::{ControllerCommand, EngineMessage, SceneInfo, SourceInfo};
use libobs_simple::sources::windows::MonitorCaptureSourceBuilder;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::encoders::ObsContextEncoders;
use libobs_wrapper::display::{ObsDisplayCreationData, ObsDisplayRef, ObsWindowHandle, WindowPositionTrait};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::unsafe_send::Sendable;
use libobs_wrapper::utils::StartupInfo;
use multistream::{PlatformStream, report_platform_frame_stats, start_multistream, stop_one};
use stream::{FRAME_STATS_INTERVAL, StreamState, report_frame_stats, start_stream};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::{ElementState, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::{CursorIcon, Window, WindowId};

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
const AUDIO_LEVEL_INTERVAL: Duration = Duration::from_millis(50);

/// Emit one protocol message as a single JSON line on stdout. A serialization failure is
/// reported on stderr rather than swallowed (it must never crash the engine). `pub(crate)`
/// so `stream.rs` can report streaming events the same way.
pub(crate) fn emit(msg: &EngineMessage) {
    match hikari_protocol::to_line(msg) {
        Ok(line) => println!("{line}"),
        Err(err) => eprintln!("[engine] failed to serialize {msg:?}: {err}"),
    }
}

/// Build the "main" scene with a screen capture, as an ORDINARY source.
///
/// Elle passe par le même chemin que toute source ajoutée à la main (2026-08-05) : avant, la
/// capture de démarrage était construite à part et rangée dans un champ dédié, ce qui la
/// rendait ni retirable, ni saisissable à la souris, ni listée comme les autres. Jay l'a
/// signalé — « il y a une source que je ne peux pas supprimer ». Une exception dans le
/// modèle finit toujours par se voir à l'écran.
fn build_scene_with_capture(
    context: &mut ObsContext,
) -> Result<(Vec<SourceInfo>, ObsSceneItemRef<ObsSourceRef>, String)> {
    context.scene("main", Some(0))?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let first = monitors.first().context("no monitor available to capture")?;
    let monitor_id = first.0.name.clone();
    let item = sources::add_capture_to_scene(
        context,
        hikari_protocol::SourceKind::Monitor,
        &monitor_id,
        MONITOR_CAPTURE_NAME,
        "main",
    )?;
    // Mise au cadre : un écran 4K sur un canevas 1080p déborderait sans ça.
    item.fit_source_to_screen()?;
    Ok((vec![SourceInfo::monitor_capture(MONITOR_CAPTURE_NAME)], item, monitor_id))
}

/// Creates the preview window + its `obs_display`. Transcribed from the B1b spike
/// (jalon 1, `spikes/b1b-preview/src/main.rs`), proven GO 2026-07-18.
fn create_preview(context: &mut ObsContext, window: &Window) -> Result<ObsDisplayRef> {
    let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
        anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
    };
    let obs_handle = ObsWindowHandle::new_from_handle(handle.hwnd.get() as *mut _);
    let size = window.inner_size();
    let data = ObsDisplayCreationData::new(obs_handle, 0, 0, size.width, size.height);
    Ok(context.display(data)?)
}

/// Keeps the 16:9 aspect ratio when the controller resizes the grafted window (cross-process
/// `MoveWindow`, proven at the spike). Pure aspect-fit math, transcribed unchanged.
fn fit_size(win_w: u32, win_h: u32) -> (u32, u32) {
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
    context: ObsContext,
    /// The real, currently-composed scene sources — grown by `handle_add_camera`. Kept
    /// here (never re-derived from libobs) so every `Sources` emission reflects the whole
    /// scene, never just the last-added delta.
    sources: Vec<SourceInfo>,
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
    multistream_last_stats_at: Instant,
    /// When the mixer's levels were last reported (B6) — its own beat, much faster than the
    /// frame counters'.
    audio_last_levels_at: Instant,
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

impl App {
    /// The fallible half of initialization, isolated so `resumed()` (which winit's
    /// `ApplicationHandler` does not let return `Result`) can report a failure on the wire
    /// instead of panicking. A panic here would bypass `main()`'s `EngineMessage::Error`
    /// path entirely (regression found in review: `resumed()` used to `.expect()` these
    /// same calls, so any failure — e.g. "no monitor available", a real, documented,
    /// plausible prod error — became a silent process death, exactly the "mute failure"
    /// this file's own header warns against).
    fn try_init(&mut self, event_loop: &ActiveEventLoop) -> Result<()> {
        let attrs = Window::default_attributes()
            .with_title("Hikari engine — aperçu")
            .with_inner_size(LogicalSize::new(PREVIEW_START_WIDTH, PREVIEW_START_HEIGHT));
        let window = event_loop.create_window(attrs).context("création fenêtre d'aperçu")?;

        let mut context = ObsContext::new(StartupInfo::default()).context("init libobs")?;
        emit(&EngineMessage::Ready);

        let (sources, scene_item, startup_monitor) =
            build_scene_with_capture(&mut context).context("construction scène")?;
        emit(&EngineMessage::Sources { items: sources.clone() });

        // Without this, libobs has NO monitoring device and "écouter" would be accepted
        // while producing nothing — a setting that lies is worse than a missing one.
        if let Err(err) = audio::use_default_monitoring_device(context.runtime()) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }

        let display = create_preview(&mut context, &window).context("création aperçu")?;
        // Le liseré se dessine par-dessus l'image du moteur — seul endroit possible, la
        // fenêtre native couvrant tout contenu web. Un échec coûte le contour, jamais
        // l'aperçu : signalé, puis on continue.
        if let Err(err) = outline::attach(context.runtime(), &display) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
            anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
        };
        emit(&EngineMessage::PreviewReady { hwnd: handle.hwnd.get() as i64 });

        self.obs = Some(ObsInner {
            display,
            context,
            sources,
            camera_source: None,
            camera_device_id: None,
            camera_filters: None,
            camera_items: std::collections::HashMap::new(),
            locked: std::collections::HashSet::new(),
            scene_filter_state: std::collections::HashMap::new(),
            active_scene: "main".to_string(),
            item_rects: None,
            audio: Vec::new(),
            // La capture de démarrage est enregistrée comme une source ORDINAIRE : c'est ce
            // qui la rend retirable, saisissable et listée au même titre que les autres.
            scene_sources: std::collections::HashMap::from([(
                "main".to_string(),
                vec![SceneSource {
                    name: MONITOR_CAPTURE_NAME.to_string(),
                    kind: hikari_protocol::MONITOR_CAPTURE_KIND.to_string(),
                    source_kind: hikari_protocol::SourceKind::Monitor,
                    target_id: startup_monitor,
                    item: scene_item,
                }],
            )]),
        });
        self.window = Some(Sendable(window));
        emit(&EngineMessage::SceneList {
            scenes: vec![SceneInfo::empty("main")],
            active: "main".to_string(),
        });
        Ok(())
    }

    /// Starts a stream if none is running yet and the engine is initialized. A second
    /// `StartStream` while one is already live is a no-op (never double-attach an output).
    fn handle_start_stream(&mut self) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "StartStream avant l'initialisation".into() });
            return;
        };
        if self.stream.is_some() {
            return;
        }
        match start_stream(&mut obs.context) {
            Ok(output) => self.stream = Some(StreamState { output, last_stats_at: Instant::now() }),
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Stops the current stream, if any. A `StopStream` with nothing running is a no-op.
    fn handle_stop_stream(&mut self) {
        let Some(mut stream) = self.stream.take() else { return };
        if let Err(err) = stream.output.stop() {
            emit(&EngineMessage::Error { message: format!("arrêt de la diffusion: {err}") });
        }
        emit(&EngineMessage::StreamStopped);
    }

    /// Starts multistream to every target (B3): each target starts independently, a
    /// failure on one is reported (`PlatformError`) and skipped, never aborting the
    /// others. A second `StartMultistream` while one is already running is a no-op —
    /// same "never double-attach" rule as `handle_start_stream`.
    fn handle_start_multistream(&mut self, targets: Vec<hikari_protocol::StreamTarget>) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "StartMultistream avant l'initialisation".into() });
            return;
        };
        if !self.multistream.is_empty() {
            return;
        }
        self.multistream = start_multistream(&mut obs.context, &targets);
    }

    /// Stops every running multistream target. A target already stopped is a no-op for
    /// that target (see `multistream::stop_one`).
    fn handle_stop_multistream(&mut self) {
        for mut stream in self.multistream.drain(..) {
            stop_one(&mut stream);
        }
    }

    /// Creates a new, empty scene (multi-scene, tranche 1). Rejects a blank or already-used
    /// name (`hikari_protocol::validate_scene_name`) — checked against the engine's OWN live
    /// scene list, never a name the caller merely claims doesn't exist yet.
    fn handle_create_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "CreateScene avant l'initialisation".into() });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        if let Err(err) = hikari_protocol::validate_scene_name(&name, &existing) {
            emit(&EngineMessage::Error { message: format!("nom de scène invalide : {err:?}") });
            return;
        }
        if let Err(err) = scenes::create_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.emit_scene_list();
    }

    /// Switches the live scene (multi-scene, tranche 1) — an instant cut, never a
    /// transition (B7's remaining scope). Errors clearly on an unknown name rather than a
    /// silent no-op.
    fn handle_switch_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "SwitchScene avant l'initialisation".into() });
            return;
        };
        if let Err(err) = scenes::switch_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        obs.active_scene = name.clone();
        // The camera sits differently in each scene (its own position and scale), so the
        // cached rectangle belongs to the scene we just left.
        obs.item_rects = None;
        // Applies THIS scene's own filter state (Jay, 2026-07-24) — the "scene automation
        // toggles my filters" flow: switching scenes turns the right filters on/off.
        self.apply_scene_filter_state(&name);
        self.emit_scene_list();
    }

    /// Applies `scene`'s own desired filter state to the shared camera filters (a no-op if
    /// no camera exists yet, or `scene` has never had one added) — called on `SwitchScene`
    /// and right after `AddCamera` if the target scene is already the active one.
    fn apply_scene_filter_state(&mut self, scene: &str) {
        let Some(obs) = &mut self.obs else { return };
        let Some(filters) = &obs.camera_filters else { return };
        let Some(&(background_removal_on, circle_mask_on)) = obs.scene_filter_state.get(scene) else { return };
        if let Err(err) = camera::set_filter_enabled(&filters.background_removal, background_removal_on) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        if let Err(err) = camera::set_filter_enabled(&filters.circle_mask, circle_mask_on) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
    }

    /// Emits the real scene list + active scene straight from libobs (never a shadowed
    /// count) — shared tail of every command that can change what the scenes hold.
    ///
    /// Each entry carries what THAT scene holds (tranche 3), read from the engine's own
    /// per-scene maps: the panel can then show the whole list at once, instead of forcing a
    /// live scene switch just to discover what a scene contains.
    fn emit_scene_list(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        let names = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        let scenes = names
            .into_iter()
            .map(|name| {
                let (background_removal, circle_mask) =
                    obs.scene_filter_state.get(&name).copied().unwrap_or((false, false));
                let has_camera = obs.camera_items.contains_key(&name);
                let mut sources: Vec<hikari_protocol::SceneSourceInfo> = Vec::new();
                if let Some(added) = obs.scene_sources.get(&name) {
                    sources.extend(added.iter().map(|source| {
                        // Placement lu depuis libobs, jamais mémorisé de notre côté : une
                        // copie qui dérive ferait sauvegarder une position fausse.
                        let position = source.item.get_source_position().ok();
                        let scale = source.item.get_source_scale().ok();
                        hikari_protocol::SceneSourceInfo {
                            name: source.name.clone(),
                            kind: source.kind.clone(),
                            source_kind: source.source_kind,
                            target_id: source.target_id.clone(),
                            x: position.as_ref().map_or(0, |p| *p.x() as i32),
                            y: position.as_ref().map_or(0, |p| *p.y() as i32),
                            scale_percent: scale
                                .as_ref()
                                .map_or(100, |s| (s.x() * 100.0).round() as i32),
                            locked: obs
                                .locked
                                .contains(&(name.clone(), source.name.clone())),
                        }
                    }));
                }
                if let Some(item) = obs.camera_items.get(&name) {
                    // Même traitement que les autres sources : placement lu depuis libobs, et
                    // l'appareil retenu comme cible — c'est ce qui rend la caméra rejouable.
                    let position = item.get_source_position().ok();
                    let scale = item.get_source_scale().ok();
                    sources.push(hikari_protocol::SceneSourceInfo {
                        name: camera::CAMERA_SOURCE_NAME.to_string(),
                        kind: hikari_protocol::CAMERA_KIND.to_string(),
                        source_kind: hikari_protocol::SourceKind::Camera,
                        target_id: obs.camera_device_id.clone().unwrap_or_default(),
                        x: position.as_ref().map_or(0, |p| *p.x() as i32),
                        y: position.as_ref().map_or(0, |p| *p.y() as i32),
                        scale_percent: scale
                            .as_ref()
                            .map_or(100, |s| (s.x() * 100.0).round() as i32),
                        locked: obs.locked.contains(&(
                            name.clone(),
                            camera::CAMERA_SOURCE_NAME.to_string(),
                        )),
                    });
                }
                SceneInfo { has_camera, background_removal, circle_mask, sources, name }
            })
            .collect();
        emit(&EngineMessage::SceneList { scenes, active: obs.active_scene.clone() });
    }

    /// Deletes a scene and everything scene-local it carried (multi-scene, tranche 3).
    ///
    /// Order matters and is the whole point of this function: re-validate, then leave the
    /// scene if it is live (the output channel must never end up pointing at a scene that
    /// is about to be dropped), then release its camera item and filter preference, and
    /// only then delete. The shared physical webcam is untouched — other scenes keep
    /// showing it, exactly like `handle_remove_camera`.
    fn handle_delete_scene(&mut self, name: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "DeleteScene avant l'initialisation".into() });
            return;
        };
        let existing = match scenes::list_scene_names(&mut obs.context) {
            Ok(names) => names,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        if let Err(err) = hikari_protocol::validate_scene_deletion(&name, &existing) {
            let message = match err {
                hikari_protocol::SceneDeleteError::Unknown => {
                    format!("scène introuvable : {name}")
                }
                hikari_protocol::SceneDeleteError::LastScene => {
                    "impossible de supprimer la dernière scène".to_string()
                }
            };
            emit(&EngineMessage::Error { message });
            return;
        }

        // Leave the scene before dropping it: a fallback is guaranteed to exist here,
        // because `validate_scene_deletion` already refused the last-scene case.
        if obs.active_scene == name {
            let Some(fallback) = existing.iter().find(|other| **other != name).cloned() else {
                emit(&EngineMessage::Error { message: "aucune scène de repli".into() });
                return;
            };
            self.handle_switch_scene(fallback);
            let Some(obs_again) = &mut self.obs else { return };
            if obs_again.active_scene == name {
                // The switch failed and already reported why; deleting now would leave the
                // output channel on a dropped scene.
                return;
            }
        }

        let Some(obs) = &mut self.obs else { return };
        obs.camera_items.remove(&name);
        obs.scene_filter_state.remove(&name);
        obs.item_rects = None;
        // Les captures de cette scène partent avec elle : garder leurs poignées maintiendrait
        // la scène en vie et la suppression ne ferait rien (même piège que l'élément caméra).
        obs.scene_sources.remove(&name);
        if let Err(err) = scenes::delete_scene(&mut obs.context, &name) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.emit_scene_list();
    }

    /// Puts the ONE physical webcam into `scene` (B-cam, multi-scene tranche 2) — builds
    /// the source and its two filters (disabled) only the FIRST time any scene requests a
    /// camera (Jay, 2026-07-24: "la caméra est unique"); every later scene reuses that same
    /// source, added as its own scene item (`camera::add_existing_camera_to_scene`).
    fn handle_add_camera(&mut self, device_id: String, scene: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "AddCamera avant l'initialisation".into() });
            return;
        };
        if obs.camera_source.is_none() {
            let source = match camera::build_camera_source(&mut obs.context, &device_id) {
                Ok(source) => source,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            let background_removal = match camera::create_background_removal_filter(&source) {
                Ok(filter) => filter,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            let circle_mask = match camera::create_circle_mask_filter(&source) {
                Ok(filter) => filter,
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    return;
                }
            };
            obs.camera_source = Some(source);
            obs.camera_device_id = Some(device_id.clone());
            obs.camera_filters = Some(CameraFilters { background_removal, circle_mask });
        }
        let source = obs.camera_source.clone().expect("camera_source just ensured above");
        let item = match camera::add_existing_camera_to_scene(&mut obs.context, source, &scene) {
            Ok(item) => item,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        };
        obs.camera_items.insert(scene.clone(), item);
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false));
        // A camera appeared in this scene: any cached rectangle is stale (there was none).
        obs.item_rects = None;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
        let Some(obs) = &mut self.obs else { return };
        if !obs.sources.iter().any(|source| source.kind == hikari_protocol::CAMERA_KIND) {
            obs.sources.push(SourceInfo::camera(camera::CAMERA_SOURCE_NAME));
        }
        emit(&EngineMessage::Sources { items: obs.sources.clone() });
    }

    /// Sets whether the background-removal filter is enabled FOR `scene` (B-cam, F-036,
    /// multi-scene tranche 2) — updates that scene's own desired state; applied immediately
    /// only if `scene` is the one currently live (otherwise it takes effect next time this
    /// scene becomes active, via `handle_switch_scene`).
    fn handle_set_background_removal(&mut self, scene: String, enabled: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        if !obs.camera_items.contains_key(&scene) {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        }
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false)).0 = enabled;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
    }

    /// Sets whether the circular mask filter is enabled FOR `scene`. Same per-scene
    /// contract as `handle_set_background_removal`.
    fn handle_set_circle_mask(&mut self, scene: String, enabled: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        if !obs.camera_items.contains_key(&scene) {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        }
        obs.scene_filter_state.entry(scene.clone()).or_insert((false, false)).1 = enabled;
        if scene == obs.active_scene {
            self.apply_scene_filter_state(&scene);
        }
    }

    /// Removes the webcam from `scene` only — other scenes keep it, with their own filter
    /// state untouched. Once no scene shows it anymore, the shared source + filters are
    /// fully released (their `Drop` detaches the filters and destroys the source).
    fn handle_remove_camera(&mut self, scene: String) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.remove(&scene) else { return };
        if let Err(err) = camera::remove_camera_from_scene(&mut obs.context, &scene, item) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        obs.scene_filter_state.remove(&scene);
        obs.item_rects = None;
        if obs.camera_items.is_empty() {
            obs.camera_source = None;
            obs.camera_device_id = None;
            obs.camera_filters = None;
            // The next camera may be a different device with its own resolution.
            
            obs.sources.retain(|source| source.kind != hikari_protocol::CAMERA_KIND);
            emit(&EngineMessage::Sources { items: obs.sources.clone() });
        }
    }

    /// Moves the webcam's placement WITHIN `scene` by `(dx, dy)` pixels (B7). A no-op (with
    /// an explicit error, never a silent drop) if `scene` doesn't show the camera.
    fn handle_nudge_camera(&mut self, scene: String, dx: i32, dy: i32) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.get(&scene) else {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        };
        match camera::nudge_camera(item, dx, dy) {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Grows or shrinks the webcam's placement within `scene` by one fixed step (B7). Same
    /// guard as `handle_nudge_camera`.
    fn handle_scale_camera(&mut self, scene: String, grow: bool) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "réglage caméra avant l'initialisation".into() });
            return;
        };
        let Some(item) = obs.camera_items.get(&scene) else {
            emit(&EngineMessage::Error { message: "aucune caméra dans cette scène — ajoute-en une d'abord".into() });
            return;
        };
        match camera::scale_camera(item, grow) {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Moves a source one step in front of, or behind, the others in its scene.
    ///
    /// Notre propre liste bouge du même pas que libobs : elle sert de source de vérité au
    /// panneau, et deux ordres qui divergent donneraient un écran qui ment sur ce qui cache
    /// quoi. À l'écran, la liste va du plus en AVANT au plus en arrière, comme dans OBS.
    fn handle_reorder_source(
        &mut self,
        scene: String,
        name: String,
        direction: hikari_protocol::SourceOrder,
    ) {
        let Some(obs) = &mut self.obs else { return };
        let Some(list) = obs.scene_sources.get_mut(&scene) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source déplaçable de cette scène"),
            });
            return;
        };
        let Some(index) = list.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source déplaçable de cette scène"),
            });
            return;
        };
        // Le premier de la liste est le plus en avant : avancer, c'est reculer d'un index.
        let target = match direction {
            hikari_protocol::SourceOrder::Front => index.checked_sub(1),
            hikari_protocol::SourceOrder::Back => {
                if index + 1 < list.len() { Some(index + 1) } else { None }
            }
        };
        // Déjà au bout : rien à faire, et surtout pas d'enroulement — un clic de trop ne
        // doit jamais envoyer une source à l'autre extrémité de la pile.
        let Some(target) = target else { return };
        let runtime = obs.context.runtime().clone();
        let Some(list) = obs.scene_sources.get_mut(&scene) else { return };
        if let Err(err) = sources::set_order(&runtime, &list[index].item, direction) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        // Vérifié par sonde le 2026-08-05 : notre liste et l'ordre réel du moteur coïncident
        // exactement après cet échange (positions relevées des deux côtés).
        list.swap(index, target);
        // L'ordre décide quelle source un clic désigne : le cache doit repartir de zéro.
        obs.item_rects = None;
        self.emit_scene_list();
    }

    /// Places a source exactly — la commande qui rend une session rejouable.
    fn handle_set_source_transform(
        &mut self,
        scene: String,
        name: String,
        x: i32,
        y: i32,
        scale_percent: i32,
    ) {
        let Some(obs) = &self.obs else { return };
        // La caméra ne vit pas dans `scene_sources` (elle est UNE source physique partagée,
        // rangée à part) : la chercher là seulement rendait son cadrage IMPLACABLE au rejeu
        // de session — retenu sur le disque, refusé par le moteur (Jay, 2026-08-06).
        let Some(item) = obs
            .scene_sources
            .get(&scene)
            .and_then(|list| list.iter().find(|source| source.name == name))
            .map(|source| &source.item)
            .or_else(|| {
                (name == camera::CAMERA_SOURCE_NAME).then(|| obs.camera_items.get(&scene))?
            })
        else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas dans « {scene} »"),
            });
            return;
        };
        // L'échelle voyage en pourcentage — un entier survit à l'aller-retour d'un fichier
        // de session sans les surprises d'arrondi d'un nombre à virgule.
        let scale = hikari_protocol::clamp_camera_scale(scale_percent as f32 / 100.0);
        if let Err(err) = camera::set_camera_transform(item, x, y, scale) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return;
        }
        self.scene_layout_changed();
        self.emit_scene_list();
    }

    /// Locks or unlocks a source against the mouse, in ONE scene (brique Sources).
    ///
    /// Ne vérifie pas que la source existe : verrouiller ce qui n'est pas là n'abîme rien, et
    /// une erreur ici ferait échouer le rejeu d'une session dont une source a disparu entre
    /// deux lancements (une fenêtre fermée, un fichier déplacé). Le verrou attend alors la
    /// source, plutôt que d'interrompre tout le reste.
    fn handle_set_source_locked(&mut self, scene: String, name: String, locked: bool) {
        let Some(obs) = &mut self.obs else { return };
        if locked {
            obs.locked.insert((scene, name));
        } else {
            obs.locked.remove(&(scene, name));
        }
        // Le cache des rectangles décide de ce qu'un clic peut attraper : le laisser tel quel
        // rendrait le verrou effectif seulement au prochain changement de scène.
        obs.item_rects = None;
        self.emit_scene_list();
    }

    /// Emits everything the machine can capture right now (brique Sources).
    fn handle_list_capture_targets(&mut self) {
        let (games, windows, monitors) = sources::list_capture_targets();
        emit(&EngineMessage::CaptureTargets { games, windows, monitors });
    }

    /// The names already taken in `scene` — every capture plus the camera. Used to refuse a
    /// duplicate BEFORE libobs silently renames it ("Webcam 2").
    fn source_names_in_scene(&self, scene: &str) -> Vec<String> {
        let Some(obs) = &self.obs else { return Vec::new() };
        let mut names: Vec<String> = obs
            .scene_sources
            .get(scene)
            .map(|added| added.iter().map(|source| source.name.clone()).collect())
            .unwrap_or_default();
        if obs.camera_items.contains_key(scene) {
            names.push(camera::CAMERA_SOURCE_NAME.to_string());
        }
        names
    }

    /// Adds a game, window or screen capture into a scene (brique Sources).
    fn handle_add_capture_source(
        &mut self,
        scene: String,
        kind: hikari_protocol::SourceKind,
        target_id: String,
        name: String,
    ) {
        if self.obs.is_none() {
            emit(&EngineMessage::Error {
                message: "AddCaptureSource avant l'initialisation".into(),
            });
            return;
        }
        let taken = self.source_names_in_scene(&scene);
        if let Err(err) = hikari_protocol::validate_source_name(&name, &taken) {
            let message = match err {
                hikari_protocol::SceneNameError::Empty => "le nom de la source est vide".to_string(),
                hikari_protocol::SceneNameError::Duplicate => {
                    format!("« {name} » existe déjà dans cette scène")
                }
            };
            emit(&EngineMessage::Error { message });
            return;
        }
        let Some(obs) = &mut self.obs else { return };
        match sources::add_capture_to_scene(&mut obs.context, kind, &target_id, &name, &scene) {
            Ok(item) => {
                // En TÊTE, pas en queue : libobs pose une nouvelle source devant les autres,
                // et notre liste doit refléter cet ordre réel — sinon le panneau annoncerait
                // l'inverse de ce que l'écran montre.
                obs.scene_sources.entry(scene).or_default().insert(
                    0,
                    SceneSource {
                        name,
                        kind: kind.libobs_id().to_string(),
                        source_kind: kind,
                        target_id,
                        item,
                    },
                );
                // Oubli corrigé le 2026-08-05 : sans ça, le cache des rectangles gardait la
                // scène telle qu'elle était AVANT l'ajout, donc la nouvelle source n'était
                // saisissable par personne.
                obs.item_rects = None;
            }
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return;
            }
        }
        self.emit_scene_list();
    }

    /// Removes a capture from ONE scene. Other scenes keep theirs.
    fn handle_remove_source(&mut self, scene: String, name: String) {
        let Some(obs) = &mut self.obs else { return };
        let Some(list) = obs.scene_sources.get_mut(&scene) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source retirable de cette scène"),
            });
            return;
        };
        let Some(index) = list.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error {
                message: format!("« {name} » n'est pas une source retirable de cette scène"),
            });
            return;
        };
        let removed = list.remove(index);
        obs.item_rects = None;
        if let Err(err) = sources::remove_from_scene(&mut obs.context, &scene, removed.item) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
        self.emit_scene_list();
    }

    /// Emits the machine's real audio devices, both sides (B6). A failure on one side is
    /// reported and yields an empty list for that side rather than hiding the other.
    fn handle_list_audio_devices(&mut self) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "ListAudioDevices avant l'initialisation".into() });
            return;
        };
        let probe = |kind| match audio::probe_audio_devices(&obs.context, kind) {
            Ok(devices) => devices,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                Vec::new()
            }
        };
        let inputs = probe(hikari_protocol::AudioSourceKind::Input);
        let outputs = probe(hikari_protocol::AudioSourceKind::Output);
        emit(&EngineMessage::AudioDevices { inputs, outputs });
    }

    /// Adds a microphone or desktop-audio capture to the mixer (B6).
    fn handle_add_audio_source(
        &mut self,
        device_id: String,
        kind: hikari_protocol::AudioSourceKind,
        name: String,
    ) {
        let Some(obs) = &mut self.obs else {
            emit(&EngineMessage::Error { message: "AddAudioSource avant l'initialisation".into() });
            return;
        };
        if obs.audio.iter().any(|existing| existing.name == name) {
            emit(&EngineMessage::Error { message: format!("« {name} » est déjà dans le mixeur") });
            return;
        }
        let Some(channel) = Self::free_audio_channel(&obs.audio) else {
            emit(&EngineMessage::Error {
                message: format!("mixeur plein ({} sources maximum)", audio::MAX_AUDIO_SOURCES),
            });
            return;
        };
        let capture = match self.open_capture(&device_id, kind, &name, channel) {
            Some(capture) => capture,
            None => return,
        };
        let Some(obs) = &mut self.obs else { return };
        // A missing meter costs a bar, never the sound — reported, then carried on without.
        let meter = match audio::LevelMeter::attach(&capture.source) {
            Ok(meter) => Some(meter),
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                None
            }
        };
        obs.audio.push(MixerSource {
            name,
            kind,
            public: Some(capture),
            monitor: None,
            meter,
            // libobs starts a source at unity gain; the slider must say the same thing the
            // ear hears, so it starts at 100 rather than at some remembered default.
            volume_percent: 100,
            monitor_volume_percent: 100,
            muted: false,
            // libobs's own default, and the safe one: monitoring a microphone through
            // speakers is how a feedback howl starts.
            monitoring: hikari_protocol::AudioMonitoring::None,
            noise_suppression: false,
            noise_method: hikari_protocol::NoiseMethod::Rnnoise,
            noise_level_db: hikari_protocol::NOISE_LEVEL_DEFAULT_DB,
            device_id,
        });
        self.emit_audio_sources();
    }

    /// Opens ONE libobs capture of `device_id` on `channel`, with its noise filter attached
    /// disabled where that means something. `None` (after reporting) if libobs refused —
    /// which is the case a second capture of the same device can genuinely hit.
    fn open_capture(
        &mut self,
        device_id: &str,
        kind: hikari_protocol::AudioSourceKind,
        libobs_name: &str,
        channel: u32,
    ) -> Option<LiveCapture> {
        let obs = self.obs.as_mut()?;
        let source = match audio::build_audio_source(&mut obs.context, kind, device_id, libobs_name)
        {
            Ok(source) => source,
            Err(err) => {
                emit(&EngineMessage::Error { message: err.to_string() });
                return None;
            }
        };
        if let Err(err) = audio::attach_to_channel(&source, channel) {
            emit(&EngineMessage::Error { message: err.to_string() });
            return None;
        }
        // Attached disabled, only where it means something. A failure costs the feature on
        // this capture, never the capture itself — the microphone still works without it.
        let noise_filter = if kind.supports_noise_suppression() {
            match audio::create_noise_suppression_filter(&source) {
                Ok(filter) => Some(filter),
                Err(err) => {
                    emit(&EngineMessage::Error { message: err.to_string() });
                    None
                }
            }
        } else {
            None
        };
        Some(LiveCapture { source, channel, noise_filter })
    }

    /// The lowest channel no capture occupies. `None` when the mixer is full. Counts every
    /// capture, not every entry — an entry heard by both sides holds two.
    fn free_audio_channel(sources: &[MixerSource]) -> Option<u32> {
        (audio::FIRST_AUDIO_CHANNEL..audio::FIRST_AUDIO_CHANNEL + audio::MAX_AUDIO_SOURCES).find(
            |channel| {
                !sources
                    .iter()
                    .flat_map(MixerSource::captures)
                    .any(|capture| capture.channel == *channel)
            },
        )
    }

    /// Frees one capture's channel. The capture itself drops with its owner.
    fn close_capture(runtime: &libobs_wrapper::runtime::ObsRuntime, capture: &LiveCapture) {
        if let Err(err) = audio::clear_channel(runtime, capture.channel) {
            emit(&EngineMessage::Error { message: err.to_string() });
        }
    }

    /// Removes an entry from the mixer: destroys its meter, frees every capture it holds.
    fn handle_remove_audio_source(&mut self, name: String) {
        let Some(obs) = &mut self.obs else { return };
        let Some(index) = obs.audio.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error { message: format!("« {name} » n'est pas dans le mixeur") });
            return;
        };
        let mut removed = obs.audio.remove(index);
        let runtime = obs.context.runtime().clone();
        // The meter goes first: it must stop pointing at a source about to be freed. Taken
        // out of the entry so the captures below can still be read from it.
        if let Some(meter) = removed.meter.take() {
            if let Err(err) = meter.destroy(&runtime) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
        }
        for capture in removed.captures() {
            Self::close_capture(&runtime, capture);
        }
        self.emit_audio_sources();
    }

    /// Sets the volume the AUDIENCE hears. A muted entry keeps the new value: it takes
    /// effect the moment it is unmuted, never silently discarded.
    fn handle_set_audio_volume(&mut self, name: String, percent: i32) {
        self.update_entry(&name, |entry| {
            entry.volume_percent =
                hikari_protocol::volume_to_percent(hikari_protocol::percent_to_volume(percent));
        });
    }

    /// Sets the volume the STREAMER hears, independently of the audience's.
    fn handle_set_monitor_volume(&mut self, name: String, percent: i32) {
        self.update_entry(&name, |entry| {
            entry.monitor_volume_percent =
                hikari_protocol::volume_to_percent(hikari_protocol::percent_to_volume(percent));
        });
    }

    /// Mutes or unmutes an entry, leaving its sliders untouched.
    fn handle_set_audio_muted(&mut self, name: String, muted: bool) {
        self.update_entry(&name, |entry| entry.muted = muted);
    }

    /// Sets room-noise suppression: on/off, method, and Speex's strength.
    fn handle_set_noise_settings(
        &mut self,
        name: String,
        enabled: bool,
        method: hikari_protocol::NoiseMethod,
        level_db: f32,
    ) {
        self.update_entry(&name, |entry| {
            entry.noise_suppression = enabled;
            entry.noise_method = method;
            entry.noise_level_db = hikari_protocol::clamp_noise_level(level_db);
        });
    }

    /// Applies a change to one entry, then re-pushes ITS WHOLE desired state to libobs.
    ///
    /// Re-applying everything rather than only what changed is deliberate: routing decides
    /// which capture carries which volume, so a volume change and a routing change touch the
    /// same libobs calls. One place that reconciles the whole entry cannot drift; five places
    /// that each patch one field eventually do.
    fn update_entry(&mut self, name: &str, change: impl FnOnce(&mut MixerSource)) {
        let Some(obs) = &mut self.obs else { return };
        let Some(index) = obs.audio.iter().position(|source| source.name == name) else {
            emit(&EngineMessage::Error { message: format!("« {name} » n'est pas dans le mixeur") });
            return;
        };
        change(&mut obs.audio[index]);
        self.reconcile_entry(index);
        self.emit_audio_sources();
    }

    /// Sets whether the streamer hears this entry, and whether the audience does.
    ///
    /// This is the call that may open or close the SECOND capture: "both hear it" needs two
    /// (one per volume), the two one-sided modes need one.
    fn handle_set_audio_monitoring(
        &mut self,
        name: String,
        monitoring: hikari_protocol::AudioMonitoring,
    ) {
        self.update_entry(&name, |entry| entry.monitoring = monitoring);
    }

    /// Makes libobs match one entry's desired state — captures, volumes, mute, filters.
    fn reconcile_entry(&mut self, index: usize) {
        use hikari_protocol::AudioMonitoring;
        let Some(obs) = &mut self.obs else { return };
        let Some(entry) = obs.audio.get(index) else { return };
        let (wants_public, wants_monitor) = match entry.monitoring {
            AudioMonitoring::None => (true, false),
            AudioMonitoring::MonitorOnly => (false, true),
            AudioMonitoring::MonitorAndOutput => (true, true),
        };
        let runtime = obs.context.runtime().clone();
        let (name, device_id, kind) =
            (entry.name.clone(), entry.device_id.clone(), entry.kind);

        // Close what is no longer wanted BEFORE opening what is: a device that refuses two
        // simultaneous captures would otherwise fail on a mere routing change.
        for (wanted, take) in [
            (wants_public, true),
            (wants_monitor, false),
        ] {
            if wanted {
                continue;
            }
            let Some(obs) = &mut self.obs else { return };
            let Some(entry) = obs.audio.get_mut(index) else { return };
            let slot = if take { &mut entry.public } else { &mut entry.monitor };
            if let Some(capture) = slot.take() {
                Self::close_capture(&runtime, &capture);
            }
        }

        // Open what is missing. A refusal is reported and leaves the entry one-sided rather
        // than silently pretending both volumes are live.
        for (wanted, is_public) in [(wants_public, true), (wants_monitor, false)] {
            let already = self
                .obs
                .as_ref()
                .and_then(|obs| obs.audio.get(index))
                .is_some_and(|entry| if is_public { entry.public.is_some() } else { entry.monitor.is_some() });
            if !wanted || already {
                continue;
            }
            let Some(channel) =
                Self::free_audio_channel(self.obs.as_ref().map_or(&[], |obs| &obs.audio))
            else {
                emit(&EngineMessage::Error {
                    message: format!("mixeur plein ({} canaux)", audio::MAX_AUDIO_SOURCES),
                });
                continue;
            };
            // The second capture needs its own libobs name — two sources cannot share one.
            let libobs_name =
                if is_public { name.clone() } else { format!("{name} (retour)") };
            let Some(capture) = self.open_capture(&device_id, kind, &libobs_name, channel) else {
                continue;
            };
            let Some(obs) = &mut self.obs else { return };
            let Some(entry) = obs.audio.get_mut(index) else { return };
            if is_public {
                entry.public = Some(capture);
            } else {
                entry.monitor = Some(capture);
            }
        }

        self.apply_entry_settings(index);
    }

    /// Pushes an entry's volumes, mute and filter state onto whichever captures now exist.
    fn apply_entry_settings(&mut self, index: usize) {
        use hikari_protocol::AudioMonitoring;
        let Some(obs) = &mut self.obs else { return };
        let Some(entry) = obs.audio.get(index) else { return };
        let public_volume = hikari_protocol::percent_to_volume(entry.volume_percent);
        let monitor_volume = hikari_protocol::percent_to_volume(entry.monitor_volume_percent);
        let (muted, enabled, method, level_db) =
            (entry.muted, entry.noise_suppression, entry.noise_method, entry.noise_level_db);

        let apply = |capture: &LiveCapture, volume: f32, routing: AudioMonitoring| {
            if let Err(err) = audio::set_volume(&capture.source, volume) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Err(err) = audio::set_muted(&capture.source, muted) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Err(err) = audio::set_monitoring(&capture.source, routing) {
                emit(&EngineMessage::Error { message: err.to_string() });
            }
            if let Some(filter) = &capture.noise_filter {
                if let Err(err) = audio::apply_noise_settings(filter, method, level_db) {
                    emit(&EngineMessage::Error { message: err.to_string() });
                }
                if let Err(err) = filters::set_enabled(filter, enabled) {
                    emit(&EngineMessage::Error { message: err.to_string() });
                }
            }
        };

        if let Some(capture) = &entry.public {
            // The public capture is never played back: the monitor capture does that job.
            apply(capture, public_volume, AudioMonitoring::None);
        }
        if let Some(capture) = &entry.monitor {
            // Always the headphone slider — whether this capture is the entry's only one
            // (streamer listens alone) or its second (both listen).
            apply(capture, monitor_volume, AudioMonitoring::MonitorOnly);
        }
    }

    /// Emits the mixer's real state — shared tail of every command that changes it.
    fn emit_audio_sources(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        let items = obs
            .audio
            .iter()
            .map(|source| hikari_protocol::AudioSourceInfo {
                name: source.name.clone(),
                kind: source.kind,
                device_id: source.device_id.clone(),
                volume_percent: source.volume_percent,
                monitor_volume_percent: source.monitor_volume_percent,
                muted: source.muted,
                monitoring: source.monitoring,
                noise_suppression: source.noise_suppression,
                noise_method: source.noise_method,
                noise_level_db: source.noise_level_db,
            })
            .collect();
        emit(&EngineMessage::AudioSources { items });
    }

    /// Emits every source's current loudness. Called on the engine's periodic tick, never
    /// from the audio callback itself — that one only stores a number, so it never blocks.
    fn emit_audio_levels(&mut self) {
        let Some(obs) = &mut self.obs else { return };
        if obs.audio.is_empty() {
            return;
        }
        let levels = obs
            .audio
            .iter()
            .map(|source| {
                // A muted source is silent to the listener; showing its bar still moving
                // would say the opposite of what is being heard. `AudioLevel::new` turns
                // that silence into a value JSON can carry — sending `-inf` used to make
                // the whole message unreadable, freezing EVERY bar (regression 2026-08-04).
                let db = match (&source.meter, source.muted) {
                    (_, true) | (None, _) => f32::NEG_INFINITY,
                    (Some(meter), false) => meter.magnitude_db(),
                };
                hikari_protocol::AudioLevel::new(source.name.clone(), db)
            })
            .collect();
        emit(&EngineMessage::AudioLevels { levels });
    }

    /// Forgets the cached rectangles. Called by every path that moves, resizes, adds,
    /// removes or reorders a source, and by every scene switch — the cache is only exact as
    /// long as no writer forgets this.
    fn scene_layout_changed(&mut self) {
        if let Some(obs) = &mut self.obs {
            obs.item_rects = None;
        }
    }

    /// Every grabbable source of the ACTIVE scene with its rectangle, front-first.
    fn active_item_rects(&mut self) -> &[ItemRect] {
        if self.obs.as_ref().is_some_and(|obs| obs.item_rects.is_some()) {
            return self.obs.as_ref().map_or(&[], |obs| {
                obs.item_rects.as_deref().unwrap_or(&[])
            });
        }
        let Some(obs) = &mut self.obs else { return &[] };
        let runtime = obs.context.runtime().clone();
        let scene = obs.active_scene.clone();

        // Camera + captures gathered together: the user sees one stack, not two families.
        //
        // Une source VERROUILLÉE n'entre pas dans cette liste (brique Sources). C'est le seul
        // endroit où le verrou peut vraiment tenir : tout geste souris — saisir, déplacer,
        // redimensionner, et jusqu'au curseur qui change de forme — part de ce test de clic.
        // Le désactiver côté écran laisserait la source attrapable, donc pas verrouillée.
        let mut items: Vec<(String, &ObsSceneItemRef<ObsSourceRef>)> = obs
            .scene_sources
            .get(&scene)
            .map(|list| {
                list.iter()
                    .filter(|source| {
                        !obs.locked.contains(&(scene.clone(), source.name.clone()))
                    })
                    .map(|source| (source.name.clone(), &source.item))
                    .collect()
            })
            .unwrap_or_default();
        let camera_locked = obs
            .locked
            .contains(&(scene.clone(), camera::CAMERA_SOURCE_NAME.to_string()));
        if let Some(item) = obs.camera_items.get(&scene).filter(|_| !camera_locked) {
            items.push((camera::CAMERA_SOURCE_NAME.to_string(), item));
        }

        let mut measured: Vec<(i32, ItemRect)> = items
            .into_iter()
            .filter_map(|(name, item)| {
                let (base_w, base_h) = sources::item_base_size(&runtime, item).ok()?;
                if base_w == 0 || base_h == 0 {
                    // Source pas encore prête : rien à attraper, plutôt qu'un rectangle
                    // inventé sur une taille supposée.
                    return None;
                }
                let position = item.get_source_position().ok()?;
                let scale = item.get_source_scale().ok()?;
                let order = sources::order_position(&runtime, item).ok()?;
                Some((
                    order,
                    ItemRect {
                        name,
                        x: *position.x(),
                        y: *position.y(),
                        width: base_w as f32 * scale.x(),
                        height: base_h as f32 * scale.y(),
                    },
                ))
            })
            .collect();
        // Trié par la pile RÉELLE du moteur, jamais par notre ordre d'insertion : c'est ce
        // que l'utilisateur voit qui décide quelle source un clic désigne. Décroissant, donc
        // le plus en avant vient en premier.
        measured.sort_by_key(|(order, _)| std::cmp::Reverse(*order));

        obs.item_rects = Some(measured.into_iter().map(|(_, rect)| rect).collect());
        obs.item_rects.as_deref().unwrap_or(&[])
    }

    /// The scene item behind a name, in the active scene.
    fn active_item(&self, name: &str) -> Option<&ObsSceneItemRef<ObsSourceRef>> {
        let obs = self.obs.as_ref()?;
        if name == camera::CAMERA_SOURCE_NAME {
            return obs.camera_items.get(&obs.active_scene);
        }
        obs.scene_sources
            .get(&obs.active_scene)?
            .iter()
            .find(|source| source.name == name)
            .map(|source| &source.item)
    }

    /// Sets the mouse pointer to match what a click would do right here (B7) — the only
    /// visual clue that a corner is grabbable, since the handles themselves are not drawn.
    /// Left untouched during a gesture: the shape must not flicker while dragging.
    fn update_cursor_icon(&mut self) {
        if self.drag.is_some() {
            return;
        }
        let icon = self.hover_icon();
        if let Some(window) = &self.window {
            window.0.set_cursor(icon);
        }
    }

    /// The front-most source under the cursor, and the corner it is on if any.
    ///
    /// Walks the stack from the top down and stops at the first hit: the user aims at what
    /// they SEE, so a source hidden behind another must never be the one that answers.
    fn hit_test(&mut self) -> Option<(String, f32, f32, f32, f32, Option<hikari_protocol::Corner>)> {
        let cursor = self.cursor?;
        let (cx, cy) = self.cursor_in_canvas(cursor)?;
        for rect in self.active_item_rects() {
            let (x, y, w, h) = (rect.x, rect.y, rect.width, rect.height);
            let corner =
                hikari_protocol::corner_at(cx, cy, x, y, w, h, hikari_protocol::CORNER_GRAB_MARGIN);
            if corner.is_some() || hikari_protocol::is_inside(cx, cy, x, y, w, h) {
                return Some((rect.name.clone(), x, y, w, h, corner));
            }
        }
        None
    }

    /// Which pointer shape the current cursor position calls for, and — même geste — le
    /// liseré qui entoure la source visée. Les deux répondent à la même question : « laquelle
    /// vais-je saisir ». Les séparer les ferait fatalement diverger.
    fn hover_icon(&mut self) -> CursorIcon {
        let hit = self.hit_test();
        match &hit {
            Some((_, x, y, w, h, _)) => {
                let canvas = self
                    .obs
                    .as_ref()
                    .and_then(|obs| camera::canvas_size(obs.context.runtime()).ok());
                match canvas {
                    Some(canvas) => outline::show(*x, *y, *w, *h, canvas),
                    None => outline::hide(),
                }
            }
            None => outline::hide(),
        }
        let Some((_, _, _, _, _, corner)) = hit else { return CursorIcon::Default };
        match corner {
            // The double-headed diagonal arrows Windows itself uses for a corner resize:
            // "↘↖" on the two corners of one diagonal, "↙↗" on the other.
            Some(hikari_protocol::Corner::TopLeft | hikari_protocol::Corner::BottomRight) => {
                CursorIcon::NwseResize
            }
            Some(hikari_protocol::Corner::TopRight | hikari_protocol::Corner::BottomLeft) => {
                CursorIcon::NeswResize
            }
            None => CursorIcon::Move,
        }
    }

    /// Turns a cursor position in the preview into canvas coordinates. `None` while libobs
    /// video is not initialized — no guessed canvas size, ever.
    fn cursor_in_canvas(&mut self, cursor: (f32, f32)) -> Option<(f32, f32)> {
        let obs = self.obs.as_mut()?;
        let (canvas_w, canvas_h) = camera::canvas_size(obs.context.runtime()).ok()?;
        Some(hikari_protocol::window_to_canvas(
            cursor.0,
            cursor.1,
            self.fitted.0,
            self.fitted.1,
            canvas_w,
            canvas_h,
        ))
    }

    /// Left button pressed: start a resize if the cursor is on a corner of the camera, a
    /// move if it is anywhere else on it (B7, souris). A press off the camera starts
    /// nothing — the rest of the canvas is not interactive yet.
    fn begin_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return };
        let Some((name, x, y, w, h, corner)) = self.hit_test() else { return };
        self.drag = Some(match corner {
            Some(corner) => {
                let (anchor_is_left, anchor_is_top) = corner.anchor_side();
                DragState::Resize {
                    name,
                    anchor_x: if anchor_is_left { x } else { x + w },
                    anchor_y: if anchor_is_top { y } else { y + h },
                    anchor_is_left,
                    anchor_is_top,
                }
            }
            None => DragState::Move { name, grab_offset_x: cx - x, grab_offset_y: cy - y },
        });
    }

    /// Cursor moved during a gesture — applies whichever one is in progress.
    fn continue_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return };
        // Cloné plutôt qu'emprunté : le geste appelle ensuite des méthodes qui empruntent
        // `self` en entier.
        let drag = match &self.drag {
            Some(DragState::Move { name, grab_offset_x, grab_offset_y }) => {
                Some((name.clone(), None, (*grab_offset_x, *grab_offset_y)))
            }
            Some(DragState::Resize { name, anchor_x, anchor_y, anchor_is_left, anchor_is_top }) => {
                Some((
                    name.clone(),
                    Some((*anchor_x, *anchor_y, *anchor_is_left, *anchor_is_top)),
                    (0.0, 0.0),
                ))
            }
            None => None,
        };
        let Some((name, resize, (grab_x, grab_y))) = drag else { return };
        match resize {
            Some((anchor_x, anchor_y, anchor_is_left, anchor_is_top)) => {
                self.apply_resize(&name, cx, anchor_x, anchor_y, anchor_is_left, anchor_is_top)
            }
            None => self.apply_move(&name, cx - grab_x, cy - grab_y),
        }
    }

    /// Puts one source's top-left at `(x, y)` canvas pixels and reports the real result.
    ///
    /// La position passe par l'aimantation : approcher un bord ou un axe central y colle la
    /// source. C'est ce qui rend un cadrage propre atteignable à la souris, sans viser au
    /// pixel — et ça ne coûte rien quand on place volontairement de travers, l'aimantation
    /// ne corrigeant jamais au-delà de sa portée.
    fn apply_move(&mut self, name: &str, x: f32, y: f32) {
        let (x, y) = self.snapped(name, x, y);
        let Some(item) = self.active_item(name) else { return };
        let result = camera::set_camera_position(item, x as i32, y as i32);
        self.report_transform(result);
    }

    /// La position aimantée d'une source, ou la position brute si le cadre ou la taille de
    /// la source sont inconnus — jamais une aimantation devinée sur des dimensions supposées.
    fn snapped(&mut self, name: &str, x: f32, y: f32) -> (f32, f32) {
        let Some((width, height)) = self
            .active_item_rects()
            .iter()
            .find(|rect| rect.name == name)
            .map(|rect| (rect.width, rect.height))
        else {
            return (x, y);
        };
        let Some(obs) = &self.obs else { return (x, y) };
        let Ok((canvas_w, canvas_h)) = camera::canvas_size(obs.context.runtime()) else {
            return (x, y);
        };
        hikari_protocol::snap_position(x, y, width, height, canvas_w, canvas_h)
    }

    /// Resizes one source so the dragged corner follows the cursor while the anchor corner
    /// stays pinned. The scale comes from the horizontal distance alone, so the source's
    /// aspect ratio is kept — a squashed image is never what the user meant.
    fn apply_resize(
        &mut self,
        name: &str,
        cursor_x: f32,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    ) {
        let Some(obs) = &self.obs else { return };
        let runtime = obs.context.runtime().clone();
        let Some(item) = self.active_item(name) else { return };
        let Ok((base_w, base_h)) = sources::item_base_size(&runtime, item) else { return };
        if base_w == 0 || base_h == 0 {
            return;
        }
        let scale = hikari_protocol::clamp_camera_scale(hikari_protocol::resize_scale(
            anchor_x, cursor_x, base_w,
        ));
        let (new_x, new_y) = hikari_protocol::resize_box(
            anchor_x,
            anchor_y,
            anchor_is_left,
            anchor_is_top,
            base_w as f32 * scale,
            base_h as f32 * scale,
        );
        let Some(item) = self.active_item(name) else { return };
        let result = camera::set_camera_transform(item, new_x as i32, new_y as i32, scale);
        self.report_transform(result);
    }

    /// Shared tail of both gestures: forget the cached rectangles and report what really
    /// happened (the clamped values, never the requested ones).
    fn report_transform(&mut self, result: Result<(i32, i32, i32)>) {
        let scene = self.obs.as_ref().map(|obs| obs.active_scene.clone()).unwrap_or_default();
        match result {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }
}

impl ApplicationHandler<EngineEvent> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        // `try_init` never runs twice (winit calls `resumed` once per real app lifecycle
        // on Windows) but `try_init` returning early is still preferable to a second panic
        // if that assumption ever breaks — `env_logger::try_init` tolerates a repeat call.
        let _ = env_logger::try_init();
        if let Err(err) = self.try_init(event_loop) {
            emit(&EngineMessage::Error { message: err.to_string() });
            event_loop.exit();
        }
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, event: EngineEvent) {
        match event {
            EngineEvent::Exit => event_loop.exit(),
            EngineEvent::StartStream => self.handle_start_stream(),
            EngineEvent::StopStream => self.handle_stop_stream(),
            EngineEvent::StartMultistream { targets } => self.handle_start_multistream(targets),
            EngineEvent::StopMultistream => self.handle_stop_multistream(),
            EngineEvent::AddCamera { device_id, scene } => self.handle_add_camera(device_id, scene),
            EngineEvent::SetBackgroundRemoval { scene, enabled } => self.handle_set_background_removal(scene, enabled),
            EngineEvent::SetCircleMask { scene, enabled } => self.handle_set_circle_mask(scene, enabled),
            EngineEvent::RemoveCamera { scene } => self.handle_remove_camera(scene),
            EngineEvent::NudgeCamera { scene, dx, dy } => self.handle_nudge_camera(scene, dx, dy),
            EngineEvent::ScaleCamera { scene, grow } => self.handle_scale_camera(scene, grow),
            EngineEvent::CreateScene { name } => self.handle_create_scene(name),
            EngineEvent::SwitchScene { name } => self.handle_switch_scene(name),
            EngineEvent::DeleteScene { name } => self.handle_delete_scene(name),
            EngineEvent::ListAudioDevices => self.handle_list_audio_devices(),
            EngineEvent::AddAudioSource { device_id, kind, name } => {
                self.handle_add_audio_source(device_id, kind, name)
            }
            EngineEvent::RemoveAudioSource { name } => self.handle_remove_audio_source(name),
            EngineEvent::SetAudioVolume { name, percent } => {
                self.handle_set_audio_volume(name, percent)
            }
            EngineEvent::SetAudioMuted { name, muted } => self.handle_set_audio_muted(name, muted),
            EngineEvent::SetAudioMonitoring { name, monitoring } => {
                self.handle_set_audio_monitoring(name, monitoring)
            }
            EngineEvent::SetNoiseSettings { name, enabled, method, level_db } => {
                self.handle_set_noise_settings(name, enabled, method, level_db)
            }
            EngineEvent::SetMonitorVolume { name, percent } => {
                self.handle_set_monitor_volume(name, percent)
            }
            EngineEvent::ListCaptureTargets => self.handle_list_capture_targets(),
            EngineEvent::AddCaptureSource { scene, kind, target_id, name } => {
                self.handle_add_capture_source(scene, kind, target_id, name)
            }
            EngineEvent::RemoveSource { scene, name } => self.handle_remove_source(scene, name),
            EngineEvent::ReorderSource { scene, name, direction } => {
                self.handle_reorder_source(scene, name, direction)
            }
            EngineEvent::SetSourceTransform { scene, name, x, y, scale_percent } => {
                self.handle_set_source_transform(scene, name, x, y, scale_percent)
            }
            EngineEvent::SetSourceLocked { scene, name, locked } => {
                self.handle_set_source_locked(scene, name, locked)
            }
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        // Periodic reporting: frame drops while streaming (B2a: continuous health, not the
        // spike's single end-of-run sample) and audio levels while the mixer holds sources
        // (B6). Fully idle — no stream, no multistream, no audio — never wakes the loop.
        let has_audio = self.obs.as_ref().is_some_and(|obs| !obs.audio.is_empty());
        if self.stream.is_none() && self.multistream.is_empty() && !has_audio {
            event_loop.set_control_flow(ControlFlow::Wait);
            return;
        }
        if self.obs.is_none() {
            return;
        }
        if let Some(stream) = &mut self.stream {
            if stream.last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
                let obs = self.obs.as_ref().expect("obs checked just above");
                report_frame_stats(&obs.context, &stream.output);
                stream.last_stats_at = Instant::now();
            }
        }
        if !self.multistream.is_empty() && self.multistream_last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
            let obs = self.obs.as_ref().expect("obs checked just above");
            for platform_stream in &self.multistream {
                report_platform_frame_stats(&obs.context, platform_stream);
            }
            self.multistream_last_stats_at = Instant::now();
        }
        if has_audio && self.audio_last_levels_at.elapsed() >= AUDIO_LEVEL_INTERVAL {
            self.emit_audio_levels();
            self.audio_last_levels_at = Instant::now();
        }
        // Wake on the SHORTEST pending deadline: the audio meter is far more frequent than
        // the frame counters, and sleeping for the longer one would make the bars lurch.
        let next = if has_audio { AUDIO_LEVEL_INTERVAL } else { FRAME_STATS_INTERVAL };
        event_loop.set_control_flow(ControlFlow::WaitUntil(Instant::now() + next));
    }

    fn exiting(&mut self, _event_loop: &ActiveEventLoop) {
        self.handle_stop_stream();
        self.handle_stop_multistream();
        // Explicit removal BEFORE the struct drops (belt-and-braces: field order already
        // fixed above, this also detaches the display from libobs's registry cleanly).
        if let Some(inner) = &mut self.obs {
            let _ = inner.context.remove_display(&inner.display);
        }
        self.obs = None;
        emit(&EngineMessage::Stopped);
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::RedrawRequested => {
                if let Some(w) = &self.window {
                    w.0.request_redraw();
                }
            }
            WindowEvent::Resized(size) => {
                let (w, h) = fit_size(size.width, size.height);
                // Kept even when libobs isn't up yet: it is the divisor every later cursor
                // conversion uses, and a stale value would misplace the camera silently.
                self.fitted = (w, h);
                if let Some(obs) = &self.obs {
                    let _ = obs.display.set_size(w, h);
                }
            }
            WindowEvent::CursorMoved { position, .. } => {
                self.cursor = Some((position.x as f32, position.y as f32));
                if self.drag.is_some() {
                    self.continue_drag();
                } else {
                    self.update_cursor_icon();
                }
            }
            WindowEvent::MouseInput { state, button: MouseButton::Left, .. } => match state {
                ElementState::Pressed => self.begin_drag(),
                ElementState::Released => {
                    self.drag = None;
                    // The camera may have ended up under a different part of the cursor.
                    self.update_cursor_icon();
                }
            },
            // The cursor leaving the preview ends the gesture: without this, coming back in
            // would teleport the camera by the distance travelled outside.
            WindowEvent::CursorLeft { .. } => self.drag = None,
            _ => (),
        }
    }
}

/// Reads `ControllerCommand` lines from stdin on a background thread and forwards the
/// ones that need the winit/libobs thread as `EngineEvent`s (libobs calls only ever happen
/// there — see `EngineEvent`'s doc). `Stop` breaks this thread's own loop too (nothing left
/// to read once the engine is exiting).
fn spawn_stdin_command_reader(proxy: EventLoopProxy<EngineEvent>) {
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines().map_while(std::io::Result::ok) {
            match hikari_protocol::parse_controller_command(&line) {
                Ok(ControllerCommand::Stop) => {
                    let _ = proxy.send_event(EngineEvent::Exit);
                    break;
                }
                Ok(ControllerCommand::StartStream) => {
                    let _ = proxy.send_event(EngineEvent::StartStream);
                }
                Ok(ControllerCommand::StopStream) => {
                    let _ = proxy.send_event(EngineEvent::StopStream);
                }
                Ok(ControllerCommand::StartMultistream { targets }) => {
                    let _ = proxy.send_event(EngineEvent::StartMultistream { targets });
                }
                Ok(ControllerCommand::StopMultistream) => {
                    let _ = proxy.send_event(EngineEvent::StopMultistream);
                }
                Ok(ControllerCommand::AddCamera { device_id, scene }) => {
                    let _ = proxy.send_event(EngineEvent::AddCamera { device_id, scene });
                }
                Ok(ControllerCommand::SetBackgroundRemoval { scene, enabled }) => {
                    let _ = proxy.send_event(EngineEvent::SetBackgroundRemoval { scene, enabled });
                }
                Ok(ControllerCommand::SetCircleMask { scene, enabled }) => {
                    let _ = proxy.send_event(EngineEvent::SetCircleMask { scene, enabled });
                }
                Ok(ControllerCommand::RemoveCamera { scene }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveCamera { scene });
                }
                Ok(ControllerCommand::NudgeCamera { scene, dx, dy }) => {
                    let _ = proxy.send_event(EngineEvent::NudgeCamera { scene, dx, dy });
                }
                Ok(ControllerCommand::ScaleCamera { scene, grow }) => {
                    let _ = proxy.send_event(EngineEvent::ScaleCamera { scene, grow });
                }
                Ok(ControllerCommand::CreateScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::CreateScene { name });
                }
                Ok(ControllerCommand::SwitchScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::SwitchScene { name });
                }
                Ok(ControllerCommand::DeleteScene { name }) => {
                    let _ = proxy.send_event(EngineEvent::DeleteScene { name });
                }
                Ok(ControllerCommand::ListAudioDevices) => {
                    let _ = proxy.send_event(EngineEvent::ListAudioDevices);
                }
                Ok(ControllerCommand::AddAudioSource { device_id, kind, name }) => {
                    let _ = proxy.send_event(EngineEvent::AddAudioSource { device_id, kind, name });
                }
                Ok(ControllerCommand::RemoveAudioSource { name }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveAudioSource { name });
                }
                Ok(ControllerCommand::SetAudioVolume { name, percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioVolume { name, percent });
                }
                Ok(ControllerCommand::SetAudioMuted { name, muted }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioMuted { name, muted });
                }
                Ok(ControllerCommand::SetAudioMonitoring { name, monitoring }) => {
                    let _ = proxy.send_event(EngineEvent::SetAudioMonitoring { name, monitoring });
                }
                Ok(ControllerCommand::SetNoiseSettings { name, enabled, method, level_db }) => {
                    let _ = proxy
                        .send_event(EngineEvent::SetNoiseSettings { name, enabled, method, level_db });
                }
                Ok(ControllerCommand::SetMonitorVolume { name, percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetMonitorVolume { name, percent });
                }
                Ok(ControllerCommand::ListCaptureTargets) => {
                    let _ = proxy.send_event(EngineEvent::ListCaptureTargets);
                }
                Ok(ControllerCommand::AddCaptureSource { scene, kind, target_id, name }) => {
                    let _ = proxy
                        .send_event(EngineEvent::AddCaptureSource { scene, kind, target_id, name });
                }
                Ok(ControllerCommand::RemoveSource { scene, name }) => {
                    let _ = proxy.send_event(EngineEvent::RemoveSource { scene, name });
                }
                Ok(ControllerCommand::ReorderSource { scene, name, direction }) => {
                    let _ = proxy.send_event(EngineEvent::ReorderSource { scene, name, direction });
                }
                Ok(ControllerCommand::SetSourceTransform { scene, name, x, y, scale_percent }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceTransform { scene, name, x, y, scale_percent });
                }
                Ok(ControllerCommand::SetSourceLocked { scene, name, locked }) => {
                    let _ = proxy.send_event(EngineEvent::SetSourceLocked { scene, name, locked });
                }
                Ok(_) => (), // ListSources : hors périmètre de ce lecteur pour l'instant
                Err(err) => eprintln!("[engine] commande stdin illisible {line:?}: {err}"),
            }
        }
    });
}

fn run() -> Result<()> {
    let event_loop = EventLoop::<EngineEvent>::with_user_event().build()?;
    spawn_stdin_command_reader(event_loop.create_proxy());
    let mut app = App {
        window: None,
        obs: None,
        stream: None,
        multistream: Vec::new(),
        multistream_last_stats_at: Instant::now(),
        audio_last_levels_at: Instant::now(),
        cursor: None,
        fitted: (PREVIEW_START_WIDTH, PREVIEW_START_HEIGHT),
        drag: None,
    };
    event_loop.run_app(&mut app)?;
    Ok(())
}

/// One-shot mode (B9 pré-vol, option A): init libobs just enough to list the video
/// encoders it reports, emit `Encoders`, then exit — no window, no scene, no preview.
/// Never the continuous supervised process (that wiring is separate debt, see PET B1
/// "Dette restante") — this exists so the pré-vol screen can show a REAL detection
/// (F-003: never presumed) without paying for the full engine lifecycle.
fn detect_encoders_and_exit() -> Result<()> {
    let context = ObsContext::new(StartupInfo::default()).context("init libobs")?;
    let available = context
        .available_video_encoders()
        .context("liste des encodeurs vidéo")?
        .into_iter()
        .map(|b| format!("{:?}", b.get_encoder_id()))
        .collect::<Vec<_>>();
    emit(&EngineMessage::Encoders { available });
    Ok(())
}

/// One-shot mode (B-cam tranche 1): init libobs just enough to probe the real camera
/// devices it sees, emit `Cameras`, then exit — same shape as `detect_encoders_and_exit`,
/// never the continuous supervised process.
fn detect_cameras_and_exit() -> Result<()> {
    let context = ObsContext::new(StartupInfo::default()).context("init libobs")?;
    let devices = camera::probe_camera_devices(&context)?;
    emit(&EngineMessage::Cameras { devices });
    Ok(())
}

fn main() -> Result<()> {
    let outcome = if std::env::args().any(|arg| arg == "--detect-encoders") {
        detect_encoders_and_exit()
    } else if std::env::args().any(|arg| arg == "--detect-cameras") {
        detect_cameras_and_exit()
    } else {
        run()
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
