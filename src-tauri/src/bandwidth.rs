//! Mesure le débit montant RÉEL de la connexion (B9 pré-vol, 2026-09-12) — décidé avec
//! Jay : un test d'upload synthétique vers un point Cloudflare public, AVANT tout
//! démarrage de direct (contrairement au mode test Twitch, qui ne mesure qu'un flux déjà
//! parti, et exclut YouTube). Payload aléatoire, aucune donnée personnelle : hors du
//! périmètre Confidentiality Gate A.
//!
//! Née du retour de Jay : ~65 % d'images perdues sur son dernier direct — rien ne
//! mesurait sa connexion avant de choisir un débit à envoyer.

use anyhow::{Context, Result};
use std::time::Instant;

/// Point d'upload public Cloudflare — aucun compte, aucune authentification (vérifié en
/// direct, 2026-09-12 : POST 100 Ko → 200 OK).
const UPLOAD_URL: &str = "https://speed.cloudflare.com/__up";

/// Taille du payload : assez grand pour lisser le démarrage d'une connexion TCP (le débit
/// des premiers octets ne reflète pas le régime établi), assez petit pour rester une
/// vérification pré-vol de quelques secondes, jamais un vrai test de charge.
const PAYLOAD_BYTES: usize = 4 * 1024 * 1024; // 4 Mio

/// Mesure le débit montant réel, en kbit/s. Impure et non testée en unitaire (E/S réseau
/// réelle) — même statut que `engine_bridge::run_detect_encoders`. La décision qui EN
/// dépend (`preflight::bandwidth_allows`) est, elle, pure et testée.
pub(crate) async fn measure_upload_kbps() -> Result<u32> {
    // Payload aléatoire : un contenu compressible (zéros, texte répété) mentirait sur le
    // débit réel si la moindre couche entre ici et Cloudflare compresse le corps.
    let payload = random_payload(PAYLOAD_BYTES);

    let client = reqwest::Client::new();
    let debut = Instant::now();
    let reponse = client
        .post(UPLOAD_URL)
        .body(payload)
        .send()
        .await
        .context("envoi du test d'upload")?;
    let ecoule = debut.elapsed();

    if !reponse.status().is_success() {
        anyhow::bail!("le point de mesure a répondu {}", reponse.status());
    }

    Ok(kbps_from(PAYLOAD_BYTES, ecoule))
}

/// `PAYLOAD_BYTES` octets aléatoires — impur (RNG), séparé pour rester mesurable en
/// isolation si besoin, jamais réellement testé (dépend d'une source d'aléa réelle).
fn random_payload(len: usize) -> Vec<u8> {
    use std::collections::hash_map::RandomState;
    use std::hash::{BuildHasher, Hasher};

    // Pas de dépendance à un crate d'aléa pour un simple bruit non-compressible : l'état
    // aléatoire du hasher standard (déjà dans la stdlib) suffit ici, la qualité
    // cryptographique n'a aucune importance pour un test de débit.
    let mut octets = Vec::with_capacity(len);
    while octets.len() < len {
        let mut hasher = RandomState::new().build_hasher();
        hasher.write_usize(octets.len());
        octets.extend_from_slice(&hasher.finish().to_le_bytes());
    }
    octets.truncate(len);
    octets
}

fn kbps_from(bytes: usize, ecoule: std::time::Duration) -> u32 {
    let secondes = ecoule.as_secs_f64().max(0.001); // jamais une division par zéro
    let bits = (bytes as f64) * 8.0;
    ((bits / secondes) / 1000.0) as u32
}
