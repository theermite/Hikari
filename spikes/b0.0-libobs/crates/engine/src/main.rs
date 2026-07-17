//! Hikari — spike B0.0, processus MOTEUR.
//!
//! Charge `libobs` DANS ce processus. Le contrôleur le lance comme processus enfant
//! (ADR-013 : moteur en processus séparé = isolation des pannes). Le moteur peut mourir
//! sans emporter le contrôleur.
//!
//! Étape 1 (ici) : prouver la chaîne de build via l'ENREGISTREMENT — le « hello world »
//! de libobs-rs. Si `cargo-obs-build` ou l'édition de liens casse, on le voit ici, vite.
//! Étape 2 (à venir) : remplacer la sortie fichier par une sortie RTMP = l'épreuve (a).
//!
//! Code JETABLE (régime spike §9bis). API calquée sur l'exemple `monitor-capture` du
//! dépôt libobs-rs (main), pont vérifié 9.0.4+32.0.2 le 2026-07-17.

use std::env;
use std::thread;
use std::time::Duration;

use libobs_simple::output::simple::ObsContextSimpleExt;
use libobs_simple::sources::windows::{MonitorCaptureSourceBuilder, ObsDisplayCaptureMethod};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::output::ObsOutputTrait;
use libobs_wrapper::scenes::SceneItemTrait;
use libobs_wrapper::sources::ObsSourceBuilder;
use libobs_wrapper::utils::{ObsPath, StartupInfo};

fn main() -> anyhow::Result<()> {
    env_logger::init();

    // Durée d'enregistrement en secondes (défaut 5). Le contrôleur la passe en argument.
    let secs: u64 = env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(5);

    // Démarrer le contexte OBS dans CE processus.
    let mut context = ObsContext::new(StartupInfo::default())?;
    // Ligne d'état lue par le contrôleur (IPC minimal par stdout).
    println!("ENGINE:READY");

    let mut scene = context.scene("main", Some(0))?;

    // Capture d'écran (le spike mesure le surcoût, pas la beauté de la scène).
    let monitors = MonitorCaptureSourceBuilder::get_monitors()?;
    let monitor_item = context
        .source_builder::<MonitorCaptureSourceBuilder, _>("Monitor Capture")?
        .set_monitor(&monitors[0])
        .set_capture_method(ObsDisplayCaptureMethod::MethodDXGI)
        .add_to_scene(&mut scene)?;
    monitor_item.fit_source_to_screen()?;

    // Étape 1 : sortie fichier. Sera remplacée par une sortie RTMP à l'épreuve (a).
    let mut output = context
        .simple_output_builder("hikari-spike-output", ObsPath::new("record.mp4"))
        .build()?;

    output.start()?;
    println!("ENGINE:STARTED secs={secs}");

    thread::sleep(Duration::from_secs(secs));

    output.stop()?;
    println!("ENGINE:STOPPED");
    Ok(())
}
