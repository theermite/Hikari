//! Multistream RTMP (B3, horizontal only — vertical is deferred to its own spike, see PET
//! B3/B0.2 and the 2026-07-19 technical challenge: this libobs version has ONE global video
//! canvas per `ObsContext`, a true simultaneous vertical output needs a second canvas via
//! the raw `obs_view`/`obs_canvas` FFI, unwrapped by `libobs-wrapper` — out of this brick's
//! scope). Replicates `stream.rs`'s proven single-target pattern (`rtmp_output` + NVENC/x264
//! fallback + AAC + `run_with_obs!` FFI service attach) once per target, so a failure on one
//! platform never takes the others down (B3 acceptance: "aucun échec silencieux").

use anyhow::{Context, Result};
use hikari_protocol::{EngineMessage, StreamTarget};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::ObsDataSetters;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::output::{ObsOutputRef, ObsOutputTrait};
use libobs_wrapper::encoders::{ObsAudioEncoderType, ObsContextEncoders, ObsVideoEncoderType};
use libobs_wrapper::run_with_obs;
use libobs_wrapper::sys as obs;
use libobs_wrapper::utils::{AudioEncoderInfo, OutputInfo, VideoEncoderInfo};

use crate::emit;

/// One target's running output, kept alongside the `id` so per-platform frame stats and
/// stop/error reporting stay correctly attributed (mirrors `stream::StreamState`, one per
/// target instead of one for the whole engine).
pub struct PlatformStream {
    pub id: String,
    pub output: ObsOutputRef,
}

/// Reads the RTMP key for one target from the engine's OWN environment
/// (`HIKARI_RTMP_KEY_<ID>`, `id` uppercased) — never over the wire, same rule as
/// `stream::rtmp_target`'s single `HIKARI_RTMP_KEY`. Falls back to `"hikari"` (the same
/// zero-secret local-MediaMTX default `stream.rs` uses) so multistream is exercisable
/// against a local test server without any platform credential.
fn rtmp_key_for(id: &str) -> String {
    let var = format!("HIKARI_RTMP_KEY_{}", id.to_uppercase());
    std::env::var(&var).unwrap_or_else(|_| "hikari".into())
}

/// Starts one target's RTMP output. Transcribed from `stream::start_stream`, unchanged
/// encoder settings — only the output name and service attach are made unique per `id` so
/// N outputs coexist in the same libobs context without colliding.
fn start_one(context: &mut ObsContext, target: &StreamTarget) -> Result<ObsOutputRef> {
    let key = rtmp_key_for(&target.id);
    let output_name = format!("hikari-stream-{}", target.id);

    let output_info = OutputInfo::new("rtmp_output", output_name, None, None);
    let mut output = context.output(output_info).context("création sortie RTMP")?;

    let available = context
        .available_video_encoders()
        .context("liste des encodeurs vidéo")?
        .into_iter()
        .map(|b| b.get_encoder_id().clone())
        .collect::<Vec<_>>();

    let (video_type, hardware) = if available.contains(&ObsVideoEncoderType::OBS_NVENC_H264_TEX) {
        (ObsVideoEncoderType::OBS_NVENC_H264_TEX, true)
    } else {
        (ObsVideoEncoderType::OBS_X264, false)
    };

    let mut video_settings = context.data().context("réglages encodeur vidéo")?;
    video_settings.set_string("rate_control", "CBR")?;
    video_settings.set_int("bitrate", 6000)?;
    video_settings.set_int("keyint_sec", 2)?;
    let video_info = VideoEncoderInfo::new(
        video_type,
        format!("hikari_video_encoder_{}", target.id),
        Some(video_settings),
        None,
    );
    output.create_and_set_video_encoder(video_info).context("encodeur vidéo")?;

    let mut audio_settings = context.data().context("réglages encodeur audio")?;
    audio_settings.set_string("rate_control", "CBR")?;
    audio_settings.set_int("bitrate", 160)?;
    let audio_info = AudioEncoderInfo::new(
        ObsAudioEncoderType::FFMPEG_AAC,
        format!("hikari_audio_encoder_{}", target.id),
        Some(audio_settings),
        None,
    );
    output.create_and_set_audio_encoder(audio_info, 0).context("encodeur audio")?;

    let output_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let server_c = std::ffi::CString::new(target.server.as_str()).context("serveur RTMP invalide (NUL)")?;
    let key_c = std::ffi::CString::new(key.as_str()).context("clé RTMP invalide (NUL)")?;
    let service_name = format!("hikari-service-{}", target.id);
    let service_name_c = std::ffi::CString::new(service_name).context("nom de service invalide (NUL)")?;
    run_with_obs!(runtime, (output_ptr), move || {
        // SAFETY: exécuté sur le fil libobs (garanti par `run_with_obs!`) ; `output_ptr`
        // reste valide tant que `output` (possédé par l'appelant) n'est pas droppé — même
        // invariant que `stream::start_stream`.
        unsafe {
            let settings = obs::obs_data_create();
            obs::obs_data_set_string(settings, c"server".as_ptr(), server_c.as_ptr());
            obs::obs_data_set_string(settings, c"key".as_ptr(), key_c.as_ptr());
            let service = obs::obs_service_create(
                c"rtmp_custom".as_ptr(),
                service_name_c.as_ptr(),
                settings,
                std::ptr::null_mut(),
            );
            obs::obs_output_set_service(output_ptr.get_ptr(), service);
            obs::obs_data_release(settings);
            // service volontairement non libéré : la sortie le détient (même choix que stream.rs).
        }
    })
    .context("attache du service RTMP")?;

    output.start().context("démarrage de la diffusion")?;
    emit(&EngineMessage::PlatformStarted { id: target.id.clone(), hardware });
    Ok(output)
}

/// Starts every target independently: one target's failure is reported as a
/// `PlatformError` and skipped, it never aborts the others (B3 acceptance: "aucun échec
/// silencieux" — a silent partial start would be the opposite failure). Returns the
/// successfully started subset; an empty return means every target failed (each already
/// reported its own `PlatformError`).
pub fn start_multistream(context: &mut ObsContext, targets: &[StreamTarget]) -> Vec<PlatformStream> {
    targets
        .iter()
        .filter_map(|target| match start_one(context, target) {
            Ok(output) => Some(PlatformStream { id: target.id.clone(), output }),
            Err(err) => {
                emit(&EngineMessage::PlatformError { id: target.id.clone(), message: err.to_string() });
                None
            }
        })
        .collect()
}

/// Stops one target's output and reports it, tolerating an already-stopped output the same
/// way `stream::start_stream`'s caller tolerates a missing stream (no panic, no silent gap).
pub fn stop_one(stream: &mut PlatformStream) {
    if let Err(err) = stream.output.stop() {
        emit(&EngineMessage::PlatformError { id: stream.id.clone(), message: err.to_string() });
        return;
    }
    emit(&EngineMessage::PlatformStopped { id: stream.id.clone() });
}

/// Reads the network frame-drop counters for one target's output — transcribed from
/// `stream::report_frame_stats`, tagged by `id` since B3 runs several outputs at once.
pub fn report_platform_frame_stats(context: &ObsContext, stream: &PlatformStream) {
    let stats_ptr = stream.output.as_ptr();
    let runtime = context.runtime().clone();
    let result = run_with_obs!(runtime, (stats_ptr), move || unsafe {
        // SAFETY: exécuté sur le fil libobs ; `stats_ptr` reste valide tant que `stream`
        // (possédé par l'appelant, vivant tout le temps du multistream) n'est pas droppé.
        (
            obs::obs_output_get_frames_dropped(stats_ptr.get_ptr()),
            obs::obs_output_get_total_frames(stats_ptr.get_ptr()),
        )
    });
    match result {
        Ok((dropped, total)) => {
            emit(&EngineMessage::PlatformFrames { id: stream.id.clone(), dropped, total })
        }
        Err(err) => eprintln!("[engine] lecture stats images échouée ({}): {err}", stream.id),
    }
}

// No `cargo test` here: this module links libobs (same `test = false` constraint as
// `stream.rs` and `main.rs`, see their doc). The headless-testable half — target
// validation, wire round-trip — lives in `hikari-protocol` (`tests/multistream.rs`).
// `should_not_drop_frames_when_dual_encode`/`should_confirm_hardware_codec_on_each_output`
// (PET B3) are proven by RUNNING this engine with real targets (integration regime, same
// as B0.0/B2a) — a bench with a game running, not automatable in this test harness.
