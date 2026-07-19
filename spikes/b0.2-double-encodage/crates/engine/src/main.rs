//! Spike B0.2 — double encodage RTX 3060 (régime SPIKE §9bis, code jetable, jamais
//! fusionné dans `main`). Question unique : la RTX 3060 encaisse-t-elle l'horizontal
//! 1080p ET un 2e flux vertical simultané, PENDANT qu'un jeu tourne ? Voir docs/PET.md
//! "B0.2" pour les 3 épreuves et leurs seuils.
//!
//! [VEILLE] libobs-wrapper@9.0.4+32.0.2 verifie 2026-07-19 via crates.io (memes
//! versions que la production, aucune derive) ; obs_encoder_set_scaled_size verifie
//! 2026-07-19 via le code source local de libobs 5.0.1+32.0.4 (bindings_win.rs) —
//! l'API brute existe, non enveloppee par libobs-wrapper, meme famille de FFI que le
//! service RTMP deja prouve au spike B0.0.
//!
//! Approche : une seule scène (capture d'écran), DEUX sorties RTMP depuis le MÊME
//! canevas — A (horizontale, native, motif prouvé B2a) et B (vertical-ish, résolution
//! forcée via `obs_encoder_set_scaled_size`, l'unique appel FFI brut que ce spike
//! ajoute). Ne prouve PAS un recadrage portrait propre (question UX séparée, hors
//! scope) — mesure seulement la capacité GPU/CPU de 2 sessions NVENC simultanées.
//!
//! Ce que ce spike ne fait PAS : pas de preview, pas de deck, pas de compte OAuth.
//! Diffuser 2 flux, mesurer, rien d'autre — même discipline que B0.0.

use std::ffi::CString;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use libobs_simple::sources::windows::monitor_capture::MonitorCaptureSourceBuilder;
use libobs_simple::sources::windows::ObsDisplayCaptureMethod;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::ObsDataSetters;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::output::{ObsOutputRef, ObsOutputTrait};
use libobs_wrapper::encoders::{ObsAudioEncoderType, ObsContextEncoders, ObsVideoEncoderType};
use libobs_wrapper::run_with_obs;
use libobs_wrapper::scenes::SceneItemTrait;
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::sys as obs;
use libobs_wrapper::utils::{AudioEncoderInfo, OutputInfo, StartupInfo, VideoEncoderInfo};

/// Résolution "verticale" forcée sur le 2e encodeur — pas un vrai recadrage 9:16
/// (question UX différée), juste une résolution portrait réaliste pour charger le GPU
/// comme le ferait un vrai flux vertical (épreuve (a)/(b)/(c) du PET, jamais la qualité
/// visuelle du cadrage).
const VERTICAL_WIDTH: u32 = 1080;
const VERTICAL_HEIGHT: u32 = 1920;
const MONITOR_CAPTURE_NAME: &str = "Monitor Capture (spike b0.2)";
const STATS_INTERVAL: Duration = Duration::from_secs(2);

/// Démarre une sortie RTMP standard (motif prouvé B2a, transcrit tel quel) vers
/// `server`/`key`, avec un nom d'encodeur/sortie unique (`label`) pour coexister avec
/// la 2e sortie sur le même contexte.
fn start_output(context: &mut ObsContext, label: &str, server: &str, key: &str) -> Result<ObsOutputRef> {
    let output_info = OutputInfo::new("rtmp_output", format!("spike-output-{label}"), None, None);
    let mut output = context.output(output_info).context("création sortie RTMP")?;

    let available = context
        .available_video_encoders()
        .context("liste des encodeurs vidéo")?
        .into_iter()
        .map(|b| b.get_encoder_id().clone())
        .collect::<Vec<_>>();
    let hardware = available.contains(&ObsVideoEncoderType::OBS_NVENC_H264_TEX);
    let video_type = if hardware { ObsVideoEncoderType::OBS_NVENC_H264_TEX } else { ObsVideoEncoderType::OBS_X264 };
    println!(
        "[spike-b0.2] sortie {label}: encodeur={video_type:?} materiel={hardware} (jamais un repli logiciel muet)"
    );

    let mut video_settings = context.data().context("réglages encodeur vidéo")?;
    video_settings.set_string("rate_control", "CBR")?;
    video_settings.set_int("bitrate", 6000)?;
    video_settings.set_int("keyint_sec", 2)?;
    let video_info = VideoEncoderInfo::new(video_type, format!("spike_video_{label}"), Some(video_settings), None);
    output.create_and_set_video_encoder(video_info).context("encodeur vidéo")?;

    let mut audio_settings = context.data().context("réglages encodeur audio")?;
    audio_settings.set_string("rate_control", "CBR")?;
    audio_settings.set_int("bitrate", 160)?;
    let audio_info =
        AudioEncoderInfo::new(ObsAudioEncoderType::FFMPEG_AAC, format!("spike_audio_{label}"), Some(audio_settings), None);
    output.create_and_set_audio_encoder(audio_info, 0).context("encodeur audio")?;

    // ÉPREUVE B0.2 : force la résolution de sortie du 2e encodeur (raw FFI, non
    // enveloppé par libobs-wrapper — voir le marqueur [VEILLE] en tête de fichier). Un
    // appel unique, même famille que le service RTMP ci-dessous.
    if label == "vertical" {
        let encoder = output
            .get_current_video_encoder()
            .context("lecture de l'encodeur vidéo")?
            .context("aucun encodeur vidéo attaché à cette sortie")?;
        let encoder_ptr = encoder.as_ptr();
        let runtime = context.runtime().clone();
        run_with_obs!(runtime, (encoder_ptr), move || {
            // SAFETY: exécuté sur le fil libobs (garanti par `run_with_obs!`) ; `encoder_ptr`
            // reste valide tant que `output` (possédé par l'appelant) n'est pas droppé.
            unsafe { obs::obs_encoder_set_scaled_size(encoder_ptr.get_ptr(), VERTICAL_WIDTH, VERTICAL_HEIGHT) };
        })
        .context("obs_encoder_set_scaled_size")?;
        println!("[spike-b0.2] sortie vertical: scaled_size force a {VERTICAL_WIDTH}x{VERTICAL_HEIGHT}");
    }

    let output_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let server_c = CString::new(server).context("serveur RTMP invalide (NUL)")?;
    let key_c = CString::new(key).context("clé RTMP invalide (NUL)")?;
    let service_name_c = CString::new(format!("spike-service-{label}")).context("nom de service invalide (NUL)")?;
    run_with_obs!(runtime, (output_ptr), move || {
        // SAFETY: même invariant que `stream::start_stream` en production.
        unsafe {
            let settings = obs::obs_data_create();
            obs::obs_data_set_string(settings, c"server".as_ptr(), server_c.as_ptr());
            obs::obs_data_set_string(settings, c"key".as_ptr(), key_c.as_ptr());
            let service =
                obs::obs_service_create(c"rtmp_custom".as_ptr(), service_name_c.as_ptr(), settings, std::ptr::null_mut());
            obs::obs_output_set_service(output_ptr.get_ptr(), service);
            obs::obs_data_release(settings);
        }
    })
    .context("attache du service RTMP")?;

    output.start().context("démarrage de la diffusion")?;
    println!("[spike-b0.2] sortie {label} démarrée -> {server}/{key}");
    Ok(output)
}

/// Lit et affiche les compteurs d'images pour une sortie — l'épreuve (b) du PET (0
/// image perdue attendu sur chaque sortie).
fn report_stats(context: &ObsContext, label: &str, output: &ObsOutputRef) {
    let stats_ptr = output.as_ptr();
    let runtime = context.runtime().clone();
    let result = run_with_obs!(runtime, (stats_ptr), move || unsafe {
        (
            obs::obs_output_get_frames_dropped(stats_ptr.get_ptr()),
            obs::obs_output_get_total_frames(stats_ptr.get_ptr()),
        )
    });
    match result {
        Ok((dropped, total)) => println!("[spike-b0.2] {label}: images_perdues={dropped} images_totales={total}"),
        Err(err) => eprintln!("[spike-b0.2] {label}: lecture stats échouée: {err}"),
    }
}

fn main() -> Result<()> {
    env_logger::init();
    println!("=== Spike B0.2 — double encodage RTX 3060 ===");
    println!("Prérequis : un jeu réel qui tourne (LoL/Dofus), MediaMTX local actif sur rtmp://localhost:1935/live/.");
    println!("Ctrl+C pour arrêter — les stats s'affichent toutes les {STATS_INTERVAL:?}.\n");

    let mut context = ObsContext::new(StartupInfo::default()).context("init libobs")?;

    let mut scene = context.scene("spike-scene", Some(0)).context("création scène")?;
    let monitors = MonitorCaptureSourceBuilder::get_monitors().context("liste des moniteurs")?;
    let first = monitors.first().context("aucun moniteur disponible")?;
    context
        .source_builder::<MonitorCaptureSourceBuilder, _>(MONITOR_CAPTURE_NAME)?
        .set_monitor(first)
        .set_capture_method(ObsDisplayCaptureMethod::MethodDXGI)
        .add_to_scene(&mut scene)?
        .fit_source_to_screen()?;

    // Épreuve (a) : les 2 sessions s'ouvrent, codec matériel confirmé sur chaque —
    // jamais un repli logiciel silencieux (voir `start_output`'s println).
    let horizontal = start_output(&mut context, "horizontal", "rtmp://localhost:1935/live", "spike-h")?;
    let vertical = start_output(&mut context, "vertical", "rtmp://localhost:1935/live", "spike-v")?;

    println!("\n[spike-b0.2] 2 sessions ouvertes. Lance ton jeu et observe ses images/seconde MAINTENANT.");
    println!("[spike-b0.2] Épreuve (b) : note images_perdues après 10 min, sur chaque sortie.");
    println!("[spike-b0.2] Épreuve (c) : compare les images/seconde du jeu avec et sans ce spike actif.\n");

    let started = Instant::now();
    loop {
        std::thread::sleep(STATS_INTERVAL);
        let elapsed = started.elapsed();
        println!("--- t={elapsed:?} ---");
        report_stats(&context, "horizontal", &horizontal);
        report_stats(&context, "vertical", &vertical);
    }
}
