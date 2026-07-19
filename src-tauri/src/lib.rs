//! Hikari — point d'entrée du cadre Tauri. Socle B0.3 : zéro logique métier.
//! Le moteur vidéo vit dans un PROCESSUS SÉPARÉ (ADR-013), supervisé via `engine_bridge`.

pub mod accounts;
pub mod commands;
pub mod deck_bridge;
pub mod engine_bridge;
pub mod preview_bridge;
pub mod protocol;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Single `invoke_handler` call: Tauri's builder REPLACES the handler on each call
    // rather than composing them, so every command (Twitch B2b, deck B4) is listed here,
    // in one place, instead of split across each module's own `register()`.
    tauri::Builder::default()
        .manage(deck_bridge::DeckState::default())
        .invoke_handler(tauri::generate_handler![
            commands::connect_twitch,
            commands::connect_youtube,
            deck_bridge::deck_list_keys,
            deck_bridge::deck_trigger_key,
        ])
        .plugin(tauri_plugin_store::Builder::default().build())
        .run(tauri::generate_context!())
        .expect("erreur au lancement de l'application Tauri");
}
