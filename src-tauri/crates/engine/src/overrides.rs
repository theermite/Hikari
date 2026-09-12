//! Lit les réglages d'encodage choisis à la main (B-settings) dans l'environnement du
//! moteur — le même transport que `HIKARI_RTMP_SERVER`/`HIKARI_RTMP_KEY`
//! (`stream::rtmp_target`), la seule voie déjà éprouvée pour poser une valeur qui tient
//! toute la vie de ce processus séparé (ADR-013). Rien n'invente un second canal : le
//! contrôleur (`engine_lifecycle.rs`, côté Tauri) pose ces variables au lancement,
//! seulement pour les champs que l'utilisateur n'a pas laissés sur "auto".
//!
//! Chaque fonction ici est un mince coquille impure (lecture de `std::env`) autour d'un
//! analyseur pur et testé dans `hikari_protocol::encoding` — la logique de validation ne
//! vit qu'à un seul endroit.

/// La composition choisie à la main, si l'utilisateur en a posé une. `None` retombe sur
/// `crate::composition()` (taille d'écran détectée).
pub(crate) fn composition_override_from_env() -> Option<hikari_protocol::Composition> {
    let value = std::env::var("HIKARI_COMPOSITION_OVERRIDE").ok();
    hikari_protocol::composition_override(value.as_deref())
}

/// L'encodeur choisi à la main, si l'utilisateur en a posé un. `None` retombe sur la
/// détection réelle (F-003) — jamais une famille d'encodeur non confirmée par la machine.
pub(crate) fn encoder_override_from_env() -> Option<hikari_protocol::EncoderChoice> {
    let value = std::env::var("HIKARI_ENCODER_OVERRIDE").ok();
    hikari_protocol::encoder_override(value.as_deref())
}

/// Le débit choisi à la main, si l'utilisateur en a posé un. `None` retombe sur
/// `hikari_protocol::bitrate_kbps(...)` (calculé depuis la composition et le matériel).
pub(crate) fn bitrate_override_from_env() -> Option<u32> {
    let value = std::env::var("HIKARI_BITRATE_KBPS_OVERRIDE").ok();
    hikari_protocol::bitrate_override(value.as_deref())
}
