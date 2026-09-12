//! Hikari — point d'entrée du cadre Tauri. Socle B0.3 : zéro logique métier.
//! Le moteur vidéo vit dans un PROCESSUS SÉPARÉ (ADR-013), supervisé via `engine_bridge`.

pub mod accounts;
pub mod bandwidth;
pub mod broadcast_target;
pub mod camera_bridge;
pub mod commands;
pub mod deck_bridge;
pub mod encoding_settings;
pub mod engine_audio;
pub mod engine_bridge;
pub mod engine_lifecycle;
pub mod engine_scenes;
pub mod fonts;
pub mod preflight;
pub mod preflight_bridge;
pub mod preview_bridge;
pub mod protocol;
pub mod settings_window;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Single `invoke_handler` call: Tauri's builder REPLACES the handler on each call
    // rather than composing them, so every command (Twitch B2b, deck B4) is listed here,
    // in one place, instead of split across each module's own `register()`.
    tauri::Builder::default()
        .manage(deck_bridge::DeckState::default())
        .manage(engine_lifecycle::EngineState::default())
        .invoke_handler(tauri::generate_handler![
            commands::connect_twitch,
            commands::connect_youtube,
            commands::account_status,
            deck_bridge::deck_list_keys,
            deck_bridge::deck_trigger_key,
            preflight_bridge::run_preflight,
            camera_bridge::list_cameras,
            engine_lifecycle::start_engine,
            engine_lifecycle::stop_engine,
            engine_lifecycle::position_preview,
            engine_lifecycle::hide_preview,
            engine_scenes::add_camera_source,
            engine_scenes::set_background_removal,
            engine_scenes::set_mask_shape,
            engine_scenes::remove_camera_source,
            engine_scenes::nudge_camera,
            engine_scenes::scale_camera,
            engine_scenes::create_scene,
            engine_scenes::switch_scene,
            engine_scenes::delete_scene,
            engine_audio::list_audio_devices,
            engine_audio::add_audio_source,
            engine_audio::remove_audio_source,
            engine_audio::set_audio_volume,
            engine_audio::set_audio_muted,
            engine_audio::set_audio_monitoring,
            engine_audio::set_noise_settings,
            engine_audio::set_monitor_volume,
            engine_scenes::list_capture_targets,
            engine_scenes::add_capture_source,
            engine_scenes::remove_source,
            engine_scenes::reorder_source,
            engine_scenes::set_source_transform,
            engine_scenes::set_source_locked,
            engine_scenes::set_source_visible,
            settings_window::open_settings_window,
            engine_scenes::set_text_settings,
            engine_scenes::set_text_content,
            fonts::list_fonts,
            engine_scenes::request_scene_list,
            engine_scenes::restart_camera,
            engine_lifecycle::start_stream,
            engine_lifecycle::stop_stream,
        ])
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_dialog::init())
        // Mises à jour : le module VÉRIFIE et TÉLÉCHARGE, il ne décide jamais. C'est
        // l'interface (`UpdateBanner`) qui déclenche, sur un clic — une installation
        // spontanée pourrait couper un live. `process` fournit le redémarrage qui suit.
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .run(tauri::generate_context!())
        .expect("erreur au lancement de l'application Tauri");
}
