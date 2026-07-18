//! Hikari — engine process (ADR-013). Loads `libobs` in ITS OWN process (the controller
//! launches it by path, never links it) and reports over the JSON-line wire protocol
//! (`hikari-protocol`, ADR-011).
//!
//! B1a scope: initialize libobs, build a scene with a screen (monitor) capture, and emit
//! the scene's sources. Encoding + RTMP broadcast (the spike's `sys` FFI path) belong to
//! B2, where they are tested against a real ingest — they are intentionally NOT here.
//!
//! API transcribed from the proven B0.0 spike (verified on the libobs-rs repo 2026-07-17,
//! re-pinned via crates.io 2026-07-18). This is the integrated port, not throwaway code.

use anyhow::{Context, Result};
use hikari_protocol::{EngineMessage, SourceInfo};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::scenes::SceneItemTrait;
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::utils::StartupInfo;

use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};

/// The libobs source-kind identifier reported to decks for a screen capture.
const MONITOR_CAPTURE_KIND: &str = "monitor_capture";
/// The display name given to the scene's screen-capture source.
const MONITOR_CAPTURE_NAME: &str = "Monitor Capture";

/// Emit one protocol message as a single JSON line on stdout. A serialization failure is
/// reported on stderr rather than swallowed (it must never crash the engine).
fn emit(msg: &EngineMessage) {
    match hikari_protocol::to_line(msg) {
        Ok(line) => println!("{line}"),
        Err(err) => eprintln!("[engine] failed to serialize {msg:?}: {err}"),
    }
}

/// Describe a monitor (screen) capture source for the wire protocol. Pure: no libobs.
fn monitor_capture_source(name: &str) -> SourceInfo {
    SourceInfo { name: name.to_string(), kind: MONITOR_CAPTURE_KIND.to_string() }
}

/// Build the "main" scene with a screen capture and return its sources. Requires the real
/// libobs runtime (a GPU and at least one monitor).
fn build_scene_with_capture(context: &mut ObsContext) -> Result<Vec<SourceInfo>> {
    let mut scene = context.scene("main", Some(0))?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let first = monitors.first().context("no monitor available to capture")?;
    let item = context
        .source_builder::<MonitorCaptureSourceBuilder, _>(MONITOR_CAPTURE_NAME)?
        .set_monitor(first)
        .set_capture_method(ObsDisplayCaptureMethod::MethodDXGI)
        .add_to_scene(&mut scene)?;
    item.fit_source_to_screen()?;
    Ok(vec![monitor_capture_source(MONITOR_CAPTURE_NAME)])
}

/// The engine's one-shot run: init libobs, build the scene, report its sources, exit.
fn run() -> Result<()> {
    env_logger::init();
    let mut context = ObsContext::new(StartupInfo::default())?;
    emit(&EngineMessage::Ready);
    let sources = build_scene_with_capture(&mut context)?;
    emit(&EngineMessage::Sources { items: sources });
    emit(&EngineMessage::Stopped);
    Ok(())
}

fn main() -> Result<()> {
    if let Err(err) = run() {
        // Report the failure on the wire before dying, so the controller never sees a
        // silent death (B0.0 lesson: a mute failure costs a day).
        emit(&EngineMessage::Error { message: err.to_string() });
        return Err(err);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_list_sources_when_scene_created() {
        // The runnable half: a scene with one screen capture yields exactly that source,
        // and it serializes to a single protocol line. The real libobs scene build needs
        // a GPU + monitor runtime -> proven by the #[ignore]d integration test below.
        let sources = vec![monitor_capture_source(MONITOR_CAPTURE_NAME)];
        let msg = EngineMessage::Sources { items: sources.clone() };
        assert_eq!(sources.len(), 1, "exactly one source added");
        assert_eq!(sources[0].kind, MONITOR_CAPTURE_KIND);
        let line = hikari_protocol::to_line(&msg).expect("sources message serializes");
        assert!(line.contains(MONITOR_CAPTURE_KIND), "kind is on the wire");
        assert!(!line.contains('\n'), "one JSON object per line");
    }

    #[test]
    #[ignore = "needs the real libobs runtime (GPU + a monitor): integration regime like the B0.0 spike, not headless CI. Run with `cargo test -p engine -- --ignored`."]
    fn should_build_real_scene_when_libobs_available() {
        let mut context = ObsContext::new(StartupInfo::default())
            .expect("libobs initializes when the runtime is present");
        let sources = build_scene_with_capture(&mut context)
            .expect("a scene with a screen capture builds on real hardware");
        assert_eq!(sources.len(), 1, "the built scene exposes exactly one source");
        assert_eq!(sources[0].kind, MONITOR_CAPTURE_KIND);
    }
}
