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
