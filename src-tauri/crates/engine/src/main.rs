//! Hikari — engine process (ADR-013). Loads `libobs` in ITS OWN process (the controller
//! launches it by path, never links it) and reports over the JSON-line wire protocol
//! (`hikari-protocol`, ADR-011).
//!
//! B1a scope: initialize libobs, build a scene with a screen (monitor) capture, emit the
//! scene's sources. B1b scope (this file, extended): create a native preview window
//! (`obs_display`), announce its HWND (`PreviewReady`), and stay alive so the controller
//! can graft that window into the Tauri app (cross-process `SetParent`, proven at the
//! `spikes/b1b-preview` spike — 2 jalons GO 2026-07-18). Encoding + RTMP broadcast (the
//! spike B0.0's `sys` FFI path) belong to B2, tested there against a real ingest.
//!
//! API transcribed from the proven spikes (B0.0 for the scene/sources, B1b for the
//! preview window + wire announcement — verified on the libobs-rs repo `obs-preview`
//! example 2026-07-18). This is the integrated port, not throwaway code.

use std::io::{BufRead, Write};

use anyhow::{Context, Result};
use hikari_protocol::{ControllerCommand, EngineMessage, SourceInfo};
use libobs_simple::sources::windows::monitor_capture::MonitorCaptureSource;
use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::display::{ObsDisplayCreationData, ObsDisplayRef, ObsWindowHandle, WindowPositionTrait};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::unsafe_send::Sendable;
use libobs_wrapper::utils::StartupInfo;
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, EventLoop, EventLoopProxy};
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
/// reported on stderr rather than swallowed (it must never crash the engine).
fn emit(msg: &EngineMessage) {
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

/// A custom winit event used only to ask the event loop to exit from the stdin-reader
/// thread (winit's `EventLoopProxy` is the documented cross-thread wake-up mechanism).
struct StopRequested;

struct App {
    window: Option<Sendable<Window>>,
    obs: Option<ObsInner>,
}

impl ApplicationHandler<StopRequested> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        env_logger::init();
        let attrs = Window::default_attributes()
            .with_title("Hikari engine — aperçu")
            .with_inner_size(LogicalSize::new(PREVIEW_START_WIDTH, PREVIEW_START_HEIGHT));
        let window = event_loop.create_window(attrs).expect("création fenêtre d'aperçu");

        let mut context = ObsContext::new(StartupInfo::default()).expect("init libobs");
        emit(&EngineMessage::Ready);

        let (sources, scene_item) = build_scene_with_capture(&mut context).expect("construction scène");
        emit(&EngineMessage::Sources { items: sources });

        let display = create_preview(&mut context, &window).expect("création aperçu");
        let RawWindowHandle::Win32(handle) = window.window_handle().unwrap().as_raw() else {
            unreachable!("vérifié dans create_preview");
        };
        emit(&EngineMessage::PreviewReady { hwnd: handle.hwnd.get() as i64 });

        self.obs = Some(ObsInner { display, context, _scene_item: scene_item });
        self.window = Some(Sendable(window));
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, _event: StopRequested) {
        event_loop.exit();
    }

    fn exiting(&mut self, _event_loop: &ActiveEventLoop) {
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

/// Reads `ControllerCommand` lines from stdin on a background thread; on `Stop`, wakes the
/// event loop via its proxy so `App::user_event` can exit cleanly (display removed before
/// context, per `ObsInner`'s field order).
fn spawn_stdin_command_reader(proxy: EventLoopProxy<StopRequested>) {
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines().map_while(std::io::Result::ok) {
            match hikari_protocol::parse_controller_command(&line) {
                Ok(ControllerCommand::Stop) => {
                    let _ = proxy.send_event(StopRequested);
                    break;
                }
                Ok(_) => (), // d'autres commandes arriveront avec B2/B-auto — ignorées ici
                Err(err) => eprintln!("[engine] commande stdin illisible {line:?}: {err}"),
            }
        }
    });
}

fn run() -> Result<()> {
    let event_loop = EventLoop::<StopRequested>::with_user_event().build()?;
    spawn_stdin_command_reader(event_loop.create_proxy());
    let mut app = App { window: None, obs: None };
    event_loop.run_app(&mut app)?;
    Ok(())
}

fn main() -> Result<()> {
    if let Err(err) = run() {
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
