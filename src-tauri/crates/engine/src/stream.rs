//! Real RTMP streaming (B2a). Transcribed from the B0.0 spike (`rtmp_output` + NVENC/x264
//! fallback + AAC + `run_with_obs!` FFI service attach), proven GO.

use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use hikari_protocol::EngineMessage;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::ObsDataSetters;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::output::{ObsOutputRef, ObsOutputTrait};
use libobs_wrapper::encoders::{ObsAudioEncoderType, ObsContextEncoders, ObsVideoEncoderType};
use libobs_wrapper::run_with_obs;
use libobs_wrapper::sys as obs;
use libobs_wrapper::utils::{AudioEncoderInfo, OutputInfo, VideoEncoderInfo};

use crate::emit;

/// How often frame-drop stats are reported while streaming — continuous health monitoring
/// (B2a), unlike the spike's single end-of-run sample.
pub const FRAME_STATS_INTERVAL: Duration = Duration::from_secs(2);

/// A live stream's state: the output + when its stats were last reported (drives the
/// periodic `FRAME_STATS_INTERVAL` tick in `App::about_to_wait`).
pub struct StreamState {
    pub output: ObsOutputRef,
    pub last_stats_at: Instant,
}

/// The RTMP target, read from the engine's OWN environment (never over the wire — see
/// `ControllerCommand::StartStream` docs). Defaults to a local MediaMTX server, zero
/// secret, same as the B0.0 spike; `HIKARI_RTMP_KEY` lets Jay point at a real platform
/// with a test key that is NEVER committed.
fn rtmp_target() -> (String, String) {
    let server =
        std::env::var("HIKARI_RTMP_SERVER").unwrap_or_else(|_| "rtmp://localhost:1935/live".into());
    let key = std::env::var("HIKARI_RTMP_KEY").unwrap_or_else(|_| "hikari".into());
    (server, key)
}

/// Starts a real RTMP stream of the current scene: NVENC if available (reported, never a
/// silent software fallback), AAC audio, RTMP service attached via the low-level FFI path
/// (`libobs-simple` only records — the pont doesn't expose services, same as `sys`
/// itself). Transcribed from the B0.0 spike (`rtmp_output` + `run_with_obs!`), proven GO.
pub fn start_stream(context: &mut ObsContext) -> Result<ObsOutputRef> {
    let (server, key) = rtmp_target();

    let output_info = OutputInfo::new("rtmp_output", "hikari-stream", None, None);
    let mut output = context.output(output_info).context("création sortie RTMP")?;

    let available = context
        .available_video_encoders()
        .context("liste des encodeurs vidéo")?
        .into_iter()
        .map(|b| b.get_encoder_id().clone())
        .collect::<Vec<_>>();
    emit(&EngineMessage::Encoders {
        available: available.iter().map(|e| format!("{e:?}")).collect(),
    });

    let (video_type, hardware) = if available.contains(&ObsVideoEncoderType::OBS_NVENC_H264_TEX) {
        (ObsVideoEncoderType::OBS_NVENC_H264_TEX, true)
    } else {
        (ObsVideoEncoderType::OBS_X264, false)
    };
    emit(&EngineMessage::VideoEncoder { kind: format!("{video_type:?}"), hardware });

    let mut video_settings = context.data().context("réglages encodeur vidéo")?;
    video_settings.set_string("rate_control", "CBR")?;
    video_settings.set_int("bitrate", 6000)?;
    video_settings.set_int("keyint_sec", 2)?; // clé toutes les 2 s : exigence des ingests RTMP
    let video_info = VideoEncoderInfo::new(video_type, "hikari_video_encoder", Some(video_settings), None);
    output.create_and_set_video_encoder(video_info).context("encodeur vidéo")?;

    let mut audio_settings = context.data().context("réglages encodeur audio")?;
    audio_settings.set_string("rate_control", "CBR")?;
    audio_settings.set_int("bitrate", 160)?;
    let audio_info = AudioEncoderInfo::new(
        ObsAudioEncoderType::FFMPEG_AAC,
        "hikari_audio_encoder",
        Some(audio_settings),
        None,
    );
    output.create_and_set_audio_encoder(audio_info, 0).context("encodeur audio")?;

    // Service RTMP (rtmp_custom) attaché en FFI, sur le fil libobs — jamais la clé sur le
    // fil protocolaire (EngineMessage::Service ne porte QUE le serveur, voir sa doc).
    let output_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let server_c = std::ffi::CString::new(server.as_str()).context("serveur RTMP invalide (NUL)")?;
    let key_c = std::ffi::CString::new(key.as_str()).context("clé RTMP invalide (NUL)")?;
    let server_for_message = server.clone();
    run_with_obs!(runtime, (output_ptr), move || {
        // SAFETY: exécuté sur le fil libobs (garanti par `run_with_obs!`) ; `output_ptr`
        // reste valide tant que `output` (possédé par l'appelant) n'est pas droppé.
        unsafe {
            let settings = obs::obs_data_create();
            obs::obs_data_set_string(settings, c"server".as_ptr(), server_c.as_ptr());
            obs::obs_data_set_string(settings, c"key".as_ptr(), key_c.as_ptr());
            let service = obs::obs_service_create(
                c"rtmp_custom".as_ptr(),
                c"hikari-service".as_ptr(),
                settings,
                std::ptr::null_mut(),
            );
            obs::obs_output_set_service(output_ptr.get_ptr(), service);
            obs::obs_data_release(settings);
            // service volontairement non libéré : la sortie le détient (même choix que le spike).
        }
    })
    .context("attache du service RTMP")?;
    emit(&EngineMessage::Service { server: server_for_message });

    output.start().context("démarrage de la diffusion")?;
    emit(&EngineMessage::Started);
    Ok(output)
}

/// Reads the network frame-drop counters off the libobs thread and reports them. `dropped`
/// is the real health indicator (transcribed from the spike's end-of-run measurement, now
/// called periodically — see `FRAME_STATS_INTERVAL`).
pub fn report_frame_stats(context: &ObsContext, output: &ObsOutputRef) {
    let stats_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let result = run_with_obs!(runtime, (stats_ptr), move || unsafe {
        // SAFETY: exécuté sur le fil libobs ; `stats_ptr` reste valide tant que `output`
        // (possédé par l'appelant, vivant tout le temps du stream) n'est pas droppé.
        (
            obs::obs_output_get_frames_dropped(stats_ptr.get_ptr()),
            obs::obs_output_get_total_frames(stats_ptr.get_ptr()),
        )
    });
    match result {
        Ok((dropped, total)) => emit(&EngineMessage::Frames { dropped, total }),
        Err(err) => eprintln!("[engine] lecture stats images échouée: {err}"),
    }
}
