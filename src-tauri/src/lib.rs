//! Hikari — point d'entrée du cadre Tauri. Socle B0.3 : zéro logique métier.
//! Le moteur vidéo vit dans un PROCESSUS SÉPARÉ (ADR-013), supervisé via `engine_bridge`.

pub mod accounts;
pub mod camera_bridge;
pub mod commands;
pub mod deck_bridge;
pub mod engine_bridge;
pub mod engine_lifecycle;
pub mod preflight;
pub mod preflight_bridge;
pub mod preview_bridge;
pub mod protocol;

use tauri::Manager;

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
            deck_bridge::deck_list_keys,
            deck_bridge::deck_trigger_key,
            preflight_bridge::run_preflight,
            camera_bridge::list_cameras,
            engine_lifecycle::start_engine,
            engine_lifecycle::stop_engine,
        ])
        .plugin(tauri_plugin_store::Builder::default().build())
        .setup(|app| {
            // Keeps the grafted preview (option A: whole window) fitted as the app
            // window resizes — a no-op before the engine has announced its preview
            // (`on_host_resized` checks state itself).
            if let Some(window) = app.get_webview_window("main") {
                let handle = app.handle().clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::Resized(size) = event {
                        let state = handle.state::<engine_lifecycle::EngineState>();
                        engine_lifecycle::on_host_resized(&state, size.width, size.height);
                    }
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("erreur au lancement de l'application Tauri");
}
