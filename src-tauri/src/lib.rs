//! Hikari — point d'entrée du cadre Tauri. Socle B0.3 : zéro logique métier.
//! Le moteur vidéo vit dans un PROCESSUS SÉPARÉ (ADR-013), supervisé via `engine_bridge`.

pub mod accounts;
pub mod engine_bridge;
pub mod preview_bridge;
pub mod protocol;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("erreur au lancement de l'application Tauri");
}
