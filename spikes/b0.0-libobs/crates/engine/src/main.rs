//! Hikari — spike B0.0, processus MOTEUR : DIFFUSION RTMP (épreuve a).
//!
//! Charge `libobs` dans CE processus (le contrôleur le lance à part, ADR-013) et diffuse
//! un flux RTMP en direct. C'est le seul inconnu du projet : Rust + moteur d'OBS +
//! diffusion en direct. Ce code y répond, et sert de base à la mesure du surcoût.
//!
//! Ce que `libobs-simple` ne fournit pas (il n'enregistre que) : la sortie RTMP et son
//! SERVICE. On les pose via l'API bas niveau du pont (`sys`), exécutée sur le fil libobs
//! par la macro `run_with_obs!` (mêmes règles que le pont lui-même).
//!
//! Cible par défaut : serveur RTMP LOCAL (MediaMTX) — zéro secret. Pour un test Twitch,
//! surcharger par variables d'environnement (jamais de clé écrite dans le code) :
//!   HIKARI_RTMP_SERVER, HIKARI_RTMP_KEY
//!
//! Code JETABLE (régime spike §9bis). API vérifiée le 2026-07-17 sur le dépôt libobs-rs.

use std::env;
use std::thread;
use std::time::Duration;

use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::ObsDataSetters;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::encoders::{ObsAudioEncoderType, ObsContextEncoders, ObsVideoEncoderType};
use libobs_wrapper::run_with_obs;
use libobs_wrapper::scenes::SceneItemTrait;
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::sys as obs;
use libobs_wrapper::utils::{AudioEncoderInfo, OutputInfo, StartupInfo, VideoEncoderInfo};

use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};

fn main() -> anyhow::Result<()> {
    env_logger::init();

    // Durée de diffusion en secondes (défaut 30 pour ce premier test ; 300 pour l'épreuve).
    let secs: u64 = env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(30);

    // Cible RTMP. Défaut = MediaMTX local. Surcharge Twitch par variables d'environnement.
    let server =
        env::var("HIKARI_RTMP_SERVER").unwrap_or_else(|_| "rtmp://localhost:1935/live".into());
    let key = env::var("HIKARI_RTMP_KEY").unwrap_or_else(|_| "hikari".into());

    let mut context = ObsContext::new(StartupInfo::default())?;
    println!("ENGINE:READY");

    // Une scène + une capture d'écran : il faut de la vidéo à encoder.
    let mut scene = context.scene("main", Some(0))?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let monitor_item = context
        .source_builder::<MonitorCaptureSourceBuilder, _>("Monitor Capture")?
        .set_monitor(&monitors[0])
        .set_capture_method(ObsDisplayCaptureMethod::MethodDXGI)
        .add_to_scene(&mut scene)?;
    monitor_item.fit_source_to_screen()?;

    // Sortie RTMP (jamais un fichier). Le service porte l'URL, la sortie n'a pas de réglage.
    let output_info = OutputInfo::new("rtmp_output", "hikari-stream", None, None);
    let mut output = context.output(output_info)?;

    // Encodeur vidéo : NVENC H264 si présent (épreuve a : « codec matériel confirmé »),
    // sinon repli x264 logiciel — et on le DIT (un repli muet serait un faux positif).
    let available = context
        .available_video_encoders()?
        .into_iter()
        .map(|b| b.get_encoder_id().clone())
        .collect::<Vec<_>>();
    println!("ENGINE:ENCODERS {available:?}");

    let (video_type, hardware) = if available.contains(&ObsVideoEncoderType::OBS_NVENC_H264_TEX) {
        (ObsVideoEncoderType::OBS_NVENC_H264_TEX, true)
    } else {
        (ObsVideoEncoderType::OBS_X264, false)
    };
    println!("ENGINE:VIDEO_ENCODER type={video_type:?} hardware={hardware}");

    let mut video_settings = context.data()?;
    video_settings.set_string("rate_control", "CBR")?;
    video_settings.set_int("bitrate", 6000)?;
    video_settings.set_int("keyint_sec", 2)?; // clé toutes les 2 s : exigence des ingests RTMP
    let video_info = VideoEncoderInfo::new(video_type, "hikari_video_encoder", Some(video_settings), None);
    output.create_and_set_video_encoder(video_info)?;

    // Encodeur audio : AAC CBR.
    let mut audio_settings = context.data()?;
    audio_settings.set_string("rate_control", "CBR")?;
    audio_settings.set_int("bitrate", 160)?;
    let audio_info = AudioEncoderInfo::new(
        ObsAudioEncoderType::FFMPEG_AAC,
        "hikari_audio_encoder",
        Some(audio_settings),
        None,
    );
    output.create_and_set_audio_encoder(audio_info, 0)?;

    // Attacher le SERVICE RTMP (rtmp_custom) en FFI, sur le fil libobs.
    // Le pont n'expose pas les services ; on passe par `sys` comme le pont lui-même.
    let output_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let server_c = std::ffi::CString::new(server.as_str())?;
    let key_c = std::ffi::CString::new(key.as_str())?;
    run_with_obs!(runtime, (output_ptr), move || {
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
            // service volontairement non libéré : la sortie le détient ; process jetable.
        }
    })?;

    println!("ENGINE:SERVICE server={server}");

    output.start()?;
    println!("ENGINE:STARTED secs={secs}");

    thread::sleep(Duration::from_secs(secs));

    // Images perdues réseau (le vrai indicateur de l'épreuve a), lues sur le fil libobs.
    let stats_ptr = output.as_ptr();
    let stats_runtime = context.runtime().clone();
    let (dropped, total) = run_with_obs!(stats_runtime, (stats_ptr), move || unsafe {
        (
            obs::obs_output_get_frames_dropped(stats_ptr.get_ptr()),
            obs::obs_output_get_total_frames(stats_ptr.get_ptr()),
        )
    })?;
    println!("ENGINE:FRAMES dropped={dropped} total={total}");

    output.stop()?;
    println!("ENGINE:STOPPED");
    Ok(())
}
