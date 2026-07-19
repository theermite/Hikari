//! Tauri commands — the bridge between the frontend and the backend modules already
//! proven (B2b). Reuses the exact flow validated manually (`examples/*_manual_auth.rs`,
//! B2b) — no new backend logic, only the Tauri glue. Registered from `lib.rs` alongside
//! the deck commands (`deck_bridge`) — Tauri allows only one `invoke_handler`.

use tauri::{AppHandle, Emitter};

use crate::accounts::vault::{Platform, Secret};
use crate::accounts::{twitch, vault, youtube};

/// What the frontend shows while waiting for the user to authorize in their browser.
#[derive(Clone, serde::Serialize)]
struct TwitchCodePayload {
    verification_uri: String,
    user_code: String,
}

/// Opens `url` in the default browser. `explorer.exe`, not `cmd /C start`: `cmd.exe`
/// re-parses its command line and treats an unescaped `&` as a command separator, silently
/// truncating any URL with more than one query parameter (found the hard way in
/// `examples/youtube_manual_auth.rs` — Google saw only the params before the first `&`).
fn open_in_browser(url: &str) -> std::io::Result<()> {
    std::process::Command::new("explorer").arg(url).spawn()?;
    Ok(())
}

/// Runs the real Twitch Device Code flow (B2b, already proven manually) and stores the
/// resulting token in the OS credential store. Emits `twitch-code` as soon as the
/// verification URL/code are known (so the UI can show them immediately, not just at the
/// end), then `twitch-connected` or `twitch-error` when the flow concludes.
///
/// The single `Err` exit at the bottom (rather than each fallible step emitting its own
/// `twitch-error`) is deliberate: found in the field (2026-07-19, YouTube's twin bug, same
/// shape) that an early failure — e.g. `start_device_flow` erroring before ANY event is
/// emitted — leaves the UI stuck on "waiting" forever with zero feedback, because the
/// frontend's `invoke().catch()` swallows the rejection silently. Routing every fallible
/// step through `try_connect_twitch` and emitting exactly once here, on the one path all
/// errors funnel through, makes "no visible error" structurally impossible instead of
/// relying on each call site to remember to emit.
#[tauri::command]
pub(crate) async fn connect_twitch(app: AppHandle) -> Result<(), String> {
    let result = try_connect_twitch(&app).await;
    if let Err(message) = &result {
        let _ = app.emit("twitch-error", message.clone());
    }
    result
}

async fn try_connect_twitch(app: &AppHandle) -> Result<(), String> {
    let http = reqwest::Client::new();
    let (mut builder, prompt) = twitch::start_device_flow(twitch::TWITCH_CLIENT_ID, &http)
        .await
        .map_err(|err| err.to_string())?;

    let _ = app.emit(
        "twitch-code",
        TwitchCodePayload { verification_uri: prompt.verification_uri.clone(), user_code: prompt.user_code },
    );
    let _ = open_in_browser(&prompt.verification_uri);

    let token = twitch::wait_for_authorization(&mut builder, &http).await.map_err(|err| err.to_string())?;
    vault::store(Platform::Twitch, &token).map_err(|err| err.to_string())?;
    let _ = app.emit("twitch-connected", ());
    Ok(())
}

/// Runs the real YouTube Authorization Code + PKCE flow (B2b, already proven manually via
/// `examples/youtube_manual_auth.rs`) and stores the resulting token in the OS credential
/// store. Credentials come from the environment ONLY (`YOUTUBE_CLIENT_ID`/
/// `YOUTUBE_CLIENT_SECRET`, Jay's own Google Cloud Console registration) — never hardcoded
/// (decision 2026-07-19: the repo is public with no other user yet, so there is no reason
/// to commit Jay's specific client credential; revisit if/when other users need to run the
/// app without setting env vars). Unlike Twitch's Device Code Flow, there is no code to
/// show the user — only "browser opened, waiting for the redirect" — so this only emits
/// `youtube-connected`/`youtube-error`, no `youtube-code` counterpart to `twitch-code`.
/// Same single-exit shape as `connect_twitch` (see its doc comment) — here it is the fix
/// site: the env vars missing (the first thing to fail in practice, before any browser
/// opens) used to return early with zero event emitted, leaving the UI on "waiting"
/// forever (found live 2026-07-19, Jay's first real run).
#[tauri::command]
pub(crate) async fn connect_youtube(app: AppHandle) -> Result<(), String> {
    let result = try_connect_youtube(&app).await;
    if let Err(message) = &result {
        let _ = app.emit("youtube-error", message.clone());
    }
    result
}

async fn try_connect_youtube(app: &AppHandle) -> Result<(), String> {
    let client_id = std::env::var("YOUTUBE_CLIENT_ID")
        .map_err(|_| "variable d'environnement YOUTUBE_CLIENT_ID absente".to_string())?;
    let client_secret = std::env::var("YOUTUBE_CLIENT_SECRET")
        .map_err(|_| "variable d'environnement YOUTUBE_CLIENT_SECRET absente".to_string())?;
    let client_secret = Secret::new(client_secret);

    let pending = youtube::start_authorization(&client_id);
    let _ = open_in_browser(&pending.authorization_url);

    let http = reqwest::Client::new();
    let token = youtube::finish_authorization(pending, &client_id, &client_secret, &http)
        .await
        .map_err(|err| err.to_string())?;
    vault::store(Platform::YouTube, &token).map_err(|err| err.to_string())?;
    let _ = app.emit("youtube-connected", ());
    Ok(())
}
