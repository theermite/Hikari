//! Tauri commands — the bridge between the frontend and the backend modules already
//! proven (B2b). Reuses the exact flow validated manually (`examples/*_manual_auth.rs`,
//! B2b) — no new backend logic, only the Tauri glue. Registered from `lib.rs` alongside
//! the deck commands (`deck_bridge`) — Tauri allows only one `invoke_handler`.

use tauri::{AppHandle, Emitter};

use crate::accounts::vault::Platform;
use crate::accounts::{twitch, vault};

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
#[tauri::command]
pub(crate) async fn connect_twitch(app: AppHandle) -> Result<(), String> {
    let http = reqwest::Client::new();
    let (mut builder, prompt) = twitch::start_device_flow(twitch::TWITCH_CLIENT_ID, &http)
        .await
        .map_err(|err| err.to_string())?;

    let _ = app.emit(
        "twitch-code",
        TwitchCodePayload { verification_uri: prompt.verification_uri.clone(), user_code: prompt.user_code },
    );
    let _ = open_in_browser(&prompt.verification_uri);

    match twitch::wait_for_authorization(&mut builder, &http).await {
        Ok(token) => {
            vault::store(Platform::Twitch, &token).map_err(|err| err.to_string())?;
            let _ = app.emit("twitch-connected", ());
            Ok(())
        }
        Err(err) => {
            let message = err.to_string();
            let _ = app.emit("twitch-error", message.clone());
            Err(message)
        }
    }
}
