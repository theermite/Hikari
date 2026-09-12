//! Preflight bridge — the Tauri command wiring for `preflight.rs`'s pure decision logic
//! against a REAL, one-shot encoder detection (`engine_bridge::run_detect_encoders`,
//! B9 pré-vol option A) AND a real upload-bandwidth measurement (`bandwidth.rs`,
//! 2026-09-12). Never a continuous engine process — that wiring stays separate debt (see
//! PET B1 "Dette restante").

use tauri::{AppHandle, Manager};

use crate::bandwidth::measure_upload_kbps;
use crate::encoding_settings::{saved_bitrate_kbps, saved_composition, saved_encoder};
use crate::engine_bridge::run_detect_encoders;
use crate::preflight::{
    bandwidth_allows, effective_encoder, go_live_allowed, propose_composition, PreflightError,
};

/// What the frontend shows after a pré-vol check: either the safe encoder actually
/// detected, or why Go Live is blocked (F-010/F-012) — never both, never neither.
#[derive(Clone, serde::Serialize)]
pub(crate) struct PreflightOutcome {
    ok: bool,
    encoder_name: Option<String>,
    hardware: Option<bool>,
    reason: Option<String>,
    /// Le débit montant mesuré, en kbit/s — `None` seulement si la mesure elle-même n'a
    /// pas pu s'exécuter (Go Live bloqué dans ce cas aussi, jamais présumé sûr).
    measured_upload_kbps: Option<u32>,
    /// Le meilleur palier que CETTE mesure et CET encodeur tiennent réellement — la part
    /// du pré-vol restée non livrée le 2026-09-06 (« proposer », pas seulement accepter ou
    /// refuser). `None` seulement quand la mesure elle-même a échoué : proposer un réglage
    /// à partir d'une mesure absente vaudrait deviner, exactement ce que ce module refuse.
    proposed_composition: Option<hikari_protocol::Composition>,
    /// Le débit que CE réglage proposé enverrait réellement sur CETTE machine — affiché à
    /// côté, pour que Jay voie le chiffre avant de l'appliquer, jamais une boîte noire.
    proposed_bitrate_kbps: Option<u32>,
}

/// Runs a real pré-vol check: spawns the engine in one-shot detection mode (blocking I/O,
/// hence `spawn_blocking` — never on the async runtime's worker thread), applies the
/// already-tested `go_live_allowed` decision, then measures the real upload bandwidth and
/// checks it against what this stream would actually send (`bandwidth_allows`).
#[tauri::command]
pub(crate) async fn run_preflight(app: AppHandle) -> Result<PreflightOutcome, String> {
    let available = tauri::async_runtime::spawn_blocking(run_detect_encoders)
        .await
        .map_err(|err| err.to_string())?
        .map_err(|err| err.to_string())?;

    let encoder = match go_live_allowed(&available) {
        // Le gate ne dit que « quelque chose d'utilisable existe » — c'est
        // `effective_encoder` qui décide LEQUEL, en respectant un choix manuel (B-settings)
        // réellement détecté. `go_live_allowed` vient de confirmer qu'au moins un encodeur
        // sûr existe, donc `effective_encoder` (qui retombe sur le même calcul) ne peut pas
        // rendre `None` ici.
        Ok(_) => effective_encoder(&available, saved_encoder(&app))
            .expect("go_live_allowed vient de confirmer qu'un encodeur sûr existe"),
        Err(_) => {
            return Ok(PreflightOutcome {
                ok: false,
                encoder_name: None,
                hardware: None,
                reason: Some("aucun encodeur reconnu détecté".to_string()),
                measured_upload_kbps: None,
                proposed_composition: None,
                proposed_bitrate_kbps: None,
            });
        }
    };

    let measured = match measure_upload_kbps().await {
        Ok(kbps) => kbps,
        Err(err) => {
            // Une mesure qui échoue (pas de réseau, point de mesure injoignable) n'est
            // PAS un feu vert par défaut — c'est exactement l'écart que ce pré-vol existe
            // pour fermer (F-003 étendu au réseau).
            return Ok(PreflightOutcome {
                ok: false,
                encoder_name: Some(encoder.name),
                hardware: Some(encoder.hardware),
                reason: Some(format!("mesure de débit impossible : {err}")),
                measured_upload_kbps: None,
                proposed_composition: None,
                proposed_bitrate_kbps: None,
            });
        }
    };

    let required = required_bitrate_kbps(&app, encoder.hardware);
    let proposed = propose_composition(measured);
    let proposed_bitrate = hikari_protocol::bitrate_kbps(proposed, encoder.hardware);

    Ok(match bandwidth_allows(measured, required) {
        Ok(()) => PreflightOutcome {
            ok: true,
            encoder_name: Some(encoder.name),
            hardware: Some(encoder.hardware),
            reason: None,
            measured_upload_kbps: Some(measured),
            proposed_composition: Some(proposed),
            proposed_bitrate_kbps: Some(proposed_bitrate),
        },
        Err(PreflightError::BandwidthInsufficient {
            measured_kbps,
            required_kbps,
        }) => PreflightOutcome {
            ok: false,
            encoder_name: Some(encoder.name),
            hardware: Some(encoder.hardware),
            reason: Some(format!(
                "connexion insuffisante : {measured_kbps} kbit/s mesurés, \
                 {required_kbps} kbit/s nécessaires"
            )),
            measured_upload_kbps: Some(measured),
            proposed_composition: Some(proposed),
            proposed_bitrate_kbps: Some(proposed_bitrate),
        },
        Err(PreflightError::NoEncoderDetected) => {
            unreachable!("bandwidth_allows ne rend jamais cette variante")
        }
    })
}

/// Le débit que ce direct enverrait réellement : le réglage manuel de l'utilisateur
/// (B-settings) s'il en a posé un, sinon calculé sur la résolution de SORTIE réellement
/// utilisée (`saved_composition` si elle existe, sinon la taille d'écran détectée) —
/// jamais sur le canevas seul. Même règle que côté moteur (`crate::output_composition`,
/// engine `main.rs`) : bitrate et résolution de sortie doivent toujours s'accorder.
fn required_bitrate_kbps(app: &AppHandle, hardware: bool) -> u32 {
    if let Some(choisi) = saved_bitrate_kbps(app) {
        return choisi;
    }
    let (largeur, hauteur) = app
        .get_webview_window("main")
        .and_then(|fenetre| fenetre.primary_monitor().ok().flatten())
        .map(|ecran| (ecran.size().width, ecran.size().height))
        // Même repli prudent que le moteur (`lifecycle_ops.rs`) : un écran non détecté
        // compose petit plutôt que de refuser le pré-vol.
        .unwrap_or((1280, 720));
    let canevas = hikari_protocol::composition(largeur, hauteur);
    let sortie = hikari_protocol::resolve_output(canevas, saved_composition(app));
    hikari_protocol::bitrate_kbps(sortie, hardware)
}
