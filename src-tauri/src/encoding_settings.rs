//! Lit les réglages d'encodage sauvegardés (B-settings, `encoding-settings.json`, écrit
//! par `src/features/settings/encodingSettings.ts` via `tauri-plugin-store`) et les
//! traduit en variables d'environnement pour le processus moteur — même transport que
//! `HIKARI_RTMP_SERVER`/`HIKARI_RTMP_KEY` (`engine_lifecycle.rs`), la seule voie déjà
//! éprouvée pour poser une valeur qui tient toute la vie du processus séparé (ADR-013).
//!
//! Rien n'est posé pour un champ resté sur `"auto"` : le comportement calculé
//! (`hikari_protocol::composition`/`bitrate_kbps`) reste inchangé pour quiconque n'a
//! jamais ouvert l'écran Paramètres.

use std::process::Command;

use tauri::AppHandle;
use tauri_plugin_store::StoreExt;

const STORE_FILE: &str = "encoding-settings.json";
const SETTINGS_KEY: &str = "settings";

/// Pose les réglages d'encodage choisis à la main sur la commande de lancement du
/// moteur — un seul appel pour le site de spawn (`engine_lifecycle.rs`), même pattern
/// que ses deux `.env(...)` RTMP juste au-dessus.
pub(crate) fn apply_encoding_env(app: &AppHandle, command: &mut Command) {
    for (name, value) in encoding_env_vars(app) {
        command.env(name, value);
    }
}

/// Le débit choisi à la main, s'il y en a un — utilisé par le pré-vol (`bandwidth.rs`)
/// pour savoir CE QUE ce direct enverrait réellement, sans lancer le moteur continu.
///
/// Passe par `hikari_protocol::bitrate_override` — jamais un `.parse()` séparé : corrigé
/// après relecture indépendante (2026-09-12), le parsing à la main acceptait `"0"` comme un
/// débit valide (`required = 0` faisait toujours dire « Go Live sûr ») alors que le moteur,
/// lui, rejette `"0"` (`bitrate_override` filtre `> 0`) et retombe sur le calcul automatique
/// — deux lectures divergentes de la même valeur enregistrée.
pub(crate) fn saved_bitrate_kbps(app: &AppHandle) -> Option<u32> {
    let store = app.store(STORE_FILE).ok()?;
    let settings = store.get(SETTINGS_KEY)?;
    let value = settings.get("bitrateKbps")?.as_str()?.to_string();
    hikari_protocol::bitrate_override(Some(&value))
}

/// La résolution/cadence de SORTIE choisie à la main, si l'utilisateur en a posé une —
/// même lecture que celle envoyée au moteur (`encoding_env_vars` ci-dessous), pour que le
/// pré-vol calcule le débit requis sur ce que ce direct enverrait VRAIMENT, jamais sur la
/// taille de l'écran quand une résolution manuelle existe déjà (`preflight_bridge.rs`).
pub(crate) fn saved_composition(app: &AppHandle) -> Option<hikari_protocol::Composition> {
    let store = app.store(STORE_FILE).ok()?;
    let settings = store.get(SETTINGS_KEY)?;
    let value = settings.get("composition")?.as_str()?.to_string();
    hikari_protocol::composition_override(Some(&value))
}

/// L'encodeur choisi à la main, si l'utilisateur en a posé un — pour que le pré-vol calcule
/// le débit requis et sa proposition sur ce que ce direct utiliserait VRAIMENT, jamais sur
/// le seul encodeur auto-détecté (`preflight::effective_encoder`, relecture indépendante
/// 2026-09-12 : un `x264` choisi à la main sur une machine à NVENC faisait refuser Go Live
/// sur une connexion qui tenait pourtant le débit réellement envoyé).
pub(crate) fn saved_encoder(app: &AppHandle) -> Option<hikari_protocol::EncoderChoice> {
    let store = app.store(STORE_FILE).ok()?;
    let settings = store.get(SETTINGS_KEY)?;
    let value = settings.get("encoder")?.as_str()?.to_string();
    hikari_protocol::encoder_override(Some(&value))
}

/// Les variables à poser sur le processus moteur avant son lancement. Vide si le fichier
/// de réglages n'existe pas encore (premier lancement), ou si tout est resté sur "auto".
///
/// Intégration pure lecture (fichier + plugin), non testée en unitaire — même statut que
/// `engine_bridge::run_detect_encoders` : E/S réelle, sans logique de décision à isoler.
fn encoding_env_vars(app: &AppHandle) -> Vec<(&'static str, String)> {
    let Ok(store) = app.store(STORE_FILE) else {
        return Vec::new();
    };
    let Some(settings) = store.get(SETTINGS_KEY) else {
        return Vec::new();
    };
    let field = |name: &str| -> Option<String> { settings.get(name)?.as_str().map(str::to_string) };

    let mut vars = Vec::new();
    if let Some(composition) = field("composition").filter(|v| v != "auto") {
        vars.push(("HIKARI_COMPOSITION_OVERRIDE", composition));
    }
    if let Some(encoder) = field("encoder").filter(|v| v != "auto") {
        vars.push(("HIKARI_ENCODER_OVERRIDE", encoder));
    }
    if let Some(bitrate) = field("bitrateKbps").filter(|v| v != "auto") {
        vars.push(("HIKARI_BITRATE_KBPS_OVERRIDE", bitrate));
    }
    vars
}
