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

mod camera;
mod multistream;
mod scenes;
mod stream;

use std::io::{BufRead, Write};
use std::time::Instant;

use anyhow::{Context, Result};
use hikari_protocol::{ControllerCommand, EngineMessage, SceneInfo, SourceInfo};
use libobs_simple::sources::windows::monitor_capture::MonitorCaptureSource;
use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::encoders::ObsContextEncoders;
use libobs_wrapper::display::{ObsDisplayCreationData, ObsDisplayRef, ObsWindowHandle, WindowPositionTrait};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::{ObsSourceBuilder, ObsSourceRef};
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

/// Emit one protocol message as a single JSON line on stdout. A serialization failure is
/// reported on stderr rather than swallowed (it must never crash the engine). `pub(crate)`
/// so `stream.rs` can report streaming events the same way.
pub(crate) fn emit(msg: &EngineMessage) {
    match hikari_protocol::to_line(msg) {
        Ok(line) => println!("{line}"),
        Err(err) => eprintln!("[engine] failed to serialize {msg:?}: {err}"),
    }
}

/// Build the "main" scene with a screen capture and return its sources. Requires the real
/// libobs runtime (a GPU and at least one monitor).
fn build_scene_with_capture(context: &mut ObsContext) -> Result<(Vec<SourceInfo>, ObsSceneItemRef<MonitorCaptureSource>)> {
    let mut scene = context.scene("main", Some(0))?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let first = monitors.first().context("no monitor available to capture")?;
    let item = context
        .source_builder::<MonitorCaptureSourceBuilder, _>(MONITOR_CAPTURE_NAME)?
        .set_monitor(first)
        .set_capture_method(ObsDisplayCaptureMethod::MethodDXGI)
        .add_to_scene(&mut scene)?;
    item.fit_source_to_screen()?;
    Ok((vec![SourceInfo::monitor_capture(MONITOR_CAPTURE_NAME)], item))
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
    _scene_item: ObsSceneItemRef<MonitorCaptureSource>,
    /// The real, currently-composed scene sources — grown by `handle_add_camera`. Kept
    /// here (never re-derived from libobs) so every `Sources` emission reflects the whole
    /// scene, never just the last-added delta.
    sources: Vec<SourceInfo>,
    /// The ONE physical webcam source (Jay, 2026-07-24: "la caméra est unique"), created the
    /// first time any scene adds a camera. Reused (never rebuilt) for every later scene.
    camera_source: Option<ObsSourceRef>,
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
    /// The active scene's camera rectangle in canvas pixels, cached (B7, curseur au survol).
    ///
    /// WHY a cache: the cursor shape is decided on EVERY mouse move, and measuring the
    /// camera costs three round-trips to the OBS thread (position, scale, source size).
    /// Doing that per move made the preview stutter. The cache is exact rather than
    /// approximate because nothing but this engine ever moves the camera — every writer
    /// clears it through `invalidate_camera_rect`.
    camera_rect: Option<(f32, f32, f32, f32)>,
    /// The camera's native pixel size, measured once. A webcam does not change resolution
    /// mid-session; re-asking libobs on every mouse move would be pure cost.
    camera_base_size: Option<(u32, u32)>,
}

/// An in-progress camera gesture (B7, souris) — a move or a resize, decided at press time
/// by where the cursor was.
enum DragState {
    /// Moving. `grab_offset` is where inside the camera the user grabbed it, in canvas
    /// pixels. Keeping that offset is what makes the camera follow the cursor instead of
    /// jumping so its corner snaps under the pointer on the first move.
    Move { grab_offset_x: f32, grab_offset_y: f32 },
    /// Resizing from a corner. `anchor` is the OPPOSITE corner, in canvas pixels — it stays
    /// pinned for the whole gesture, so the camera grows away from a fixed point instead of
    /// sliding while it resizes. Read once at press time: re-deriving it from the live
    /// rectangle each move would chase its own changes.
    Resize { anchor_x: f32, anchor_y: f32, anchor_is_left: bool, anchor_is_top: bool },
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

        let (sources, scene_item) =
            build_scene_with_capture(&mut context).context("construction scène")?;
        emit(&EngineMessage::Sources { items: sources.clone() });

        let display = create_preview(&mut context, &window).context("création aperçu")?;
        let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
            anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
        };
        emit(&EngineMessage::PreviewReady { hwnd: handle.hwnd.get() as i64 });

        self.obs = Some(ObsInner {
            display,
            context,
            _scene_item: scene_item,
            sources,
            camera_source: None,
            camera_filters: None,
            camera_items: std::collections::HashMap::new(),
            scene_filter_state: std::collections::HashMap::new(),
            active_scene: "main".to_string(),
            camera_rect: None,
            camera_base_size: None,
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
        obs.camera_rect = None;
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
                SceneInfo {
                    has_camera: obs.camera_items.contains_key(&name),
                    background_removal,
                    circle_mask,
                    name,
                }
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
        obs.camera_rect = None;
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
        obs.camera_rect = None;
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
        obs.camera_rect = None;
        if obs.camera_items.is_empty() {
            obs.camera_source = None;
            obs.camera_filters = None;
            // The next camera may be a different device with its own resolution.
            obs.camera_base_size = None;
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
                self.camera_rect_changed();
                self.camera_rect_changed();
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
                self.camera_rect_changed();
                self.camera_rect_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Forgets the cached camera rectangle. Called by every path that moves, resizes, adds
    /// or removes the camera, and by every scene switch — the cache is only exact as long
    /// as no writer forgets this.
    fn camera_rect_changed(&mut self) {
        if let Some(obs) = &mut self.obs {
            obs.camera_rect = None;
        }
    }

    /// The camera's native size, measured once then remembered. `None` while the device is
    /// still opening (libobs reports 0×0 until the first frame).
    fn camera_base_size(&mut self) -> Option<(u32, u32)> {
        let obs = self.obs.as_mut()?;
        if let Some(size) = obs.camera_base_size {
            return Some(size);
        }
        let source = obs.camera_source.as_ref()?;
        let size = camera::source_base_size(source).ok()?;
        if size.0 == 0 || size.1 == 0 {
            return None;
        }
        obs.camera_base_size = Some(size);
        Some(size)
    }

    /// Where the camera sits in the ACTIVE scene, in canvas pixels: `(x, y, width, height)`.
    /// `None` when no camera is in this scene, or while the device is still opening (a
    /// zero-sized source has nothing to grab). Served from the cache when it is warm.
    fn active_camera_rect(&mut self) -> Option<(f32, f32, f32, f32)> {
        if let Some(rect) = self.obs.as_ref()?.camera_rect {
            return Some(rect);
        }
        let (base_w, base_h) = self.camera_base_size()?;
        let obs = self.obs.as_mut()?;
        let item = obs.camera_items.get(&obs.active_scene)?;
        let position = item.get_source_position().ok()?;
        let scale = item.get_source_scale().ok()?;
        let rect = (
            *position.x(),
            *position.y(),
            base_w as f32 * scale.x(),
            base_h as f32 * scale.y(),
        );
        obs.camera_rect = Some(rect);
        Some(rect)
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

    /// Which pointer shape the current cursor position calls for.
    fn hover_icon(&mut self) -> CursorIcon {
        let Some(cursor) = self.cursor else { return CursorIcon::Default };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return CursorIcon::Default };
        let Some((x, y, w, h)) = self.active_camera_rect() else { return CursorIcon::Default };
        match hikari_protocol::corner_at(cx, cy, x, y, w, h, hikari_protocol::CORNER_GRAB_MARGIN) {
            // The double-headed diagonal arrows Windows itself uses for a corner resize:
            // "↘↖" on the two corners of one diagonal, "↙↗" on the other.
            Some(hikari_protocol::Corner::TopLeft | hikari_protocol::Corner::BottomRight) => {
                CursorIcon::NwseResize
            }
            Some(hikari_protocol::Corner::TopRight | hikari_protocol::Corner::BottomLeft) => {
                CursorIcon::NeswResize
            }
            None if hikari_protocol::is_inside(cx, cy, x, y, w, h) => CursorIcon::Move,
            None => CursorIcon::Default,
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
        let Some((x, y, w, h)) = self.active_camera_rect() else { return };
        if let Some(corner) =
            hikari_protocol::corner_at(cx, cy, x, y, w, h, hikari_protocol::CORNER_GRAB_MARGIN)
        {
            let (anchor_is_left, anchor_is_top) = corner.anchor_side();
            self.drag = Some(DragState::Resize {
                anchor_x: if anchor_is_left { x } else { x + w },
                anchor_y: if anchor_is_top { y } else { y + h },
                anchor_is_left,
                anchor_is_top,
            });
        } else if hikari_protocol::is_inside(cx, cy, x, y, w, h) {
            self.drag =
                Some(DragState::Move { grab_offset_x: cx - x, grab_offset_y: cy - y });
        }
    }

    /// Cursor moved during a gesture — applies whichever one is in progress.
    fn continue_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return };
        match self.drag {
            Some(DragState::Move { grab_offset_x, grab_offset_y }) => {
                self.apply_move(cx - grab_offset_x, cy - grab_offset_y)
            }
            Some(DragState::Resize { anchor_x, anchor_y, anchor_is_left, anchor_is_top }) => {
                self.apply_resize(cx, anchor_x, anchor_y, anchor_is_left, anchor_is_top)
            }
            None => (),
        }
    }

    /// Puts the camera's top-left at `(x, y)` canvas pixels and reports the real result.
    fn apply_move(&mut self, x: f32, y: f32) {
        let Some(obs) = &mut self.obs else { return };
        let scene = obs.active_scene.clone();
        let Some(item) = obs.camera_items.get(&scene) else { return };
        match camera::set_camera_position(item, x as i32, y as i32) {
            Ok((x, y, scale_percent)) => {
                self.camera_rect_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }

    /// Resizes the camera so the dragged corner follows the cursor while the anchor corner
    /// stays pinned. The scale comes from the horizontal distance alone, so the webcam's
    /// aspect ratio is kept — a squashed face is never what the user meant.
    fn apply_resize(
        &mut self,
        cursor_x: f32,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    ) {
        let Some(obs) = &mut self.obs else { return };
        let Some(source) = obs.camera_source.as_ref() else { return };
        let Ok((base_w, base_h)) = camera::source_base_size(source) else { return };
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
        let scene = obs.active_scene.clone();
        let Some(item) = obs.camera_items.get(&scene) else { return };
        match camera::set_camera_transform(item, new_x as i32, new_y as i32, scale) {
            Ok((x, y, scale_percent)) => {
                self.camera_rect_changed();
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
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        // Periodic frame-drop reporting while streaming (B2a: continuous health, not the
        // spike's single end-of-run sample). Idle (no stream, no multistream) never wakes
        // the loop early.
        if self.stream.is_none() && self.multistream.is_empty() {
            event_loop.set_control_flow(ControlFlow::Wait);
            return;
        }
        let Some(obs) = &self.obs else { return };
        if let Some(stream) = &mut self.stream {
            if stream.last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
                report_frame_stats(&obs.context, &stream.output);
                stream.last_stats_at = Instant::now();
            }
        }
        if !self.multistream.is_empty() && self.multistream_last_stats_at.elapsed() >= FRAME_STATS_INTERVAL {
            for platform_stream in &self.multistream {
                report_platform_frame_stats(&obs.context, platform_stream);
            }
            self.multistream_last_stats_at = Instant::now();
        }
        event_loop.set_control_flow(ControlFlow::WaitUntil(Instant::now() + FRAME_STATS_INTERVAL));
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
