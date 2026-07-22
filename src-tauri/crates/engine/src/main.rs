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
mod stream;

use std::io::{BufRead, Write};
use std::time::Instant;

use anyhow::{Context, Result};
use hikari_protocol::{ControllerCommand, EngineMessage, SourceInfo};
use libobs_simple::sources::windows::monitor_capture::MonitorCaptureSource;
use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::encoders::ObsContextEncoders;
use libobs_wrapper::display::{ObsDisplayCreationData, ObsDisplayRef, ObsWindowHandle, WindowPositionTrait};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::unsafe_send::Sendable;
use libobs_wrapper::utils::StartupInfo;
use multistream::{PlatformStream, report_platform_frame_stats, start_multistream, stop_one};
use stream::{FRAME_STATS_INTERVAL, StreamState, report_frame_stats, start_stream};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::{Window, WindowId};

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
        emit(&EngineMessage::Sources { items: sources });

        let display = create_preview(&mut context, &window).context("création aperçu")?;
        let RawWindowHandle::Win32(handle) = window.window_handle()?.as_raw() else {
            anyhow::bail!("moteur Windows uniquement : handle de fenêtre Win32 attendu");
        };
        emit(&EngineMessage::PreviewReady { hwnd: handle.hwnd.get() as i64 });

        self.obs = Some(ObsInner { display, context, _scene_item: scene_item });
        self.window = Some(Sendable(window));
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
                if let Some(obs) = &self.obs {
                    let (w, h) = fit_size(size.width, size.height);
                    let _ = obs.display.set_size(w, h);
                }
            }
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
                Ok(_) => (), // CreateScene/ListSources : hors périmètre de ce lecteur pour l'instant
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
