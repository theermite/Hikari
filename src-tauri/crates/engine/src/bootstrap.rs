//! Starting the engine: the real event loop (`run`), and the two one-shot detection modes
//! used by the pré-vol screen (`--detect-encoders`, `--detect-cameras`).

use anyhow::{Context, Result};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::encoders::ObsContextEncoders;
use libobs_wrapper::utils::StartupInfo;
use std::time::Instant;
use winit::event_loop::EventLoop;

use crate::stdin_reader::spawn_stdin_command_reader;
use crate::{App, EngineEvent, PREVIEW_START_HEIGHT, PREVIEW_START_WIDTH, camera, emit};
use hikari_protocol::EngineMessage;

pub(crate) fn run() -> Result<()> {
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
pub(crate) fn detect_encoders_and_exit() -> Result<()> {
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
pub(crate) fn detect_cameras_and_exit() -> Result<()> {
    let context = ObsContext::new(StartupInfo::default()).context("init libobs")?;
    let devices = camera::probe_camera_devices(&context)?;
    emit(&EngineMessage::Cameras { devices });
    Ok(())
}
