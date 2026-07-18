//! Manual, one-off test of the REAL YouTube connection flow (B2b). NOT part of the app —
//! `cargo run --example` only, never shipped. Reads credentials from environment variables,
//! never hardcoded, never printed: `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` (Jay's own
//! Google Cloud "Desktop app" registration, set locally, never committed — same pattern as
//! B2a's `HIKARI_RTMP_KEY`).
//!
//! Run:
//!   $env:YOUTUBE_CLIENT_ID = "..."
//!   $env:YOUTUBE_CLIENT_SECRET = "..."
//!   cargo run --example youtube_manual_auth --manifest-path src-tauri/Cargo.toml

use anyhow::Context;
use hikari_lib::accounts::vault::{self, Platform, Secret};
use hikari_lib::accounts::youtube;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let client_id = std::env::var("YOUTUBE_CLIENT_ID")
        .map_err(|_| anyhow::anyhow!("variable d'environnement YOUTUBE_CLIENT_ID absente"))?;
    let client_secret = std::env::var("YOUTUBE_CLIENT_SECRET")
        .map_err(|_| anyhow::anyhow!("variable d'environnement YOUTUBE_CLIENT_SECRET absente"))?;
    let client_secret = Secret::new(client_secret);

    let pending = youtube::start_authorization(&client_id);
    println!("Ouverture du navigateur — autorise Hikari, puis reviens ici :\n");
    println!("{}\n", pending.authorization_url);
    // Auto-open so there's no manual copy/paste race against the 5-minute window (found in
    // practice: pasting the URL late enough left nothing to redeem, since Google's own
    // consent hadn't been given yet — opening it immediately removes that step entirely).
    if let Err(err) = open_in_browser(&pending.authorization_url) {
        println!("(ouverture automatique impossible: {err} — copie l'URL ci-dessus manuellement)");
    }
    println!("En attente de la redirection (5 min max)...");

    let http = reqwest::Client::new();
    match youtube::finish_authorization(pending, &client_id, &client_secret, &http).await {
        Ok(token) => {
            // Never print token.access_token/refresh_token — Secret has no way to leak them
            // via {}/{:?} even by accident; expires_at is not sensitive.
            println!("\n✅ Connexion réussie. Jeton valide jusqu'à (unix): {}", token.expires_at);

            // Close the loop B2b actually promises: the token in the OS credential store,
            // not just a successful exchange. Round-trips through the REAL Windows
            // Credential Manager (vault::store/load), not the in-memory value.
            vault::store(Platform::YouTube, &token).context("écriture dans le coffre système")?;
            println!("✅ Jeton écrit dans le coffre système (Windows Credential Manager).");

            let reloaded = vault::load(Platform::YouTube)
                .context("lecture depuis le coffre système")?
                .context("le coffre est vide juste après l'écriture — incohérence")?;
            let now = vault::now_unix();
            println!(
                "✅ Relu depuis le coffre : expire dans {}s, jugé {} par is_expired().",
                reloaded.expires_at.saturating_sub(now),
                if vault::is_expired(&reloaded, now) { "EXPIRÉ" } else { "valide" }
            );
            println!("(les jetons eux-mêmes ne sont jamais affichés — type Secret)");
        }
        Err(err) => {
            println!("\n❌ Connexion échouée: {err}");
        }
    }
    Ok(())
}

/// Opens `url` in the default browser. Windows-only, `explorer.exe` (not `cmd /C start`):
/// `cmd.exe` re-parses its whole command line and treats an unescaped `&` as a command
/// separator, silently truncating any URL with more than one query parameter — exactly
/// what broke the first version of this example (Google saw only the params before the
/// first `&`, hence "response_type missing"). `explorer.exe` receives the URL as a single
/// argument via `CreateProcess` directly (Rust's `Command` never spawns a shell here), so
/// `&` is never reinterpreted.
fn open_in_browser(url: &str) -> std::io::Result<()> {
    std::process::Command::new("explorer").arg(url).spawn()?;
    Ok(())
}
