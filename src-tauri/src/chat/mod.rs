//! Chat fusionné — connexion en lecture à Twitch (IRC) et YouTube (sondage), réponse
//! (Twitch seulement) et modération inline (Twitch seulement : mise en sourdine,
//! bannissement). Ni l'outil de référence déjà en usage chez Jay (`chat-overlay`,
//! Python/Qt) ni cette étape n'implémentent l'envoi ou la modération YouTube : le scope
//! demandé reste `youtube.readonly`, à élargir seulement quand une brique l'utilisera
//! réellement (même principe que `accounts::twitch::required_scopes` — élargir un scope
//! est une décision, jamais une dérive silencieuse).
//!
//! Chaque message reçu est émis comme événement `chat-message` ; la fusion visuelle des
//! deux plateformes, le filtre et la limite d'historique vivent côté interface
//! (`src/features/chat/history.ts`) — ce module ne retient aucun historique, seulement
//! les poignées nécessaires pour répondre, modérer et couper la connexion.
//!
//! Auto-modération (spam, liens, mots interdits), alertes, bandeaux et objectifs restent
//! hors de cette partie (voir le découpage convenu avec Jay, 2026-09-14).

pub mod moderation;
pub mod twitch;
pub mod youtube;

use std::sync::Mutex;

use tauri::{AppHandle, Emitter, State};

use crate::accounts::twitch::TWITCH_CLIENT_ID;
use crate::accounts::vault::{self, Platform};

/// Un message de chat tel qu'il traverse vers l'interface. Aucun autre champ que ceux
/// affichés/utilisés dans cette partie : pas de balise brute, pas de jeton.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChatMessage {
    pub platform: Platform,
    pub username: String,
    pub text: String,
    /// L'identifiant Twitch de l'auteur — nécessaire aux actions de modération, qui
    /// ciblent un compte, jamais un pseudonyme affiché. `None` pour YouTube : la
    /// modération n'y est pas implémentée dans cette partie (voir le module doc).
    pub user_id: Option<String>,
}

/// Ce que le pont conserve entre deux commandes — les poignées des connexions en cours,
/// pour pouvoir répondre, modérer (Twitch) et couper (les deux) sans les rouvrir à
/// l'aveugle.
#[derive(Default)]
struct ChatRuntime {
    twitch: Option<twitch::TwitchChatHandle>,
    youtube: Option<youtube::YouTubeChatHandle>,
}

#[derive(Default)]
pub struct ChatState(Mutex<ChatRuntime>);

fn lock<'a>(state: &'a State<'a, ChatState>) -> std::sync::MutexGuard<'a, ChatRuntime> {
    state
        .0
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

/// Sort le client Twitch du verrou — un `MutexGuard` std n'est pas `Send` et ne traverse
/// pas un `.await` ; le clone est ce que le crate prévoit pour cet usage (« the client
/// handle is cloneable for multi-threaded use »). Partagé par `chat_send`,
/// `chat_timeout_user` et `chat_ban_user`.
fn twitch_handle(state: &State<'_, ChatState>) -> Result<twitch::TwitchChatHandle, String> {
    lock(state)
        .twitch
        .clone()
        .ok_or_else(|| "chat Twitch non connecté".to_string())
}

/// Connecte le chat des comptes REELLEMENT utilisables — jamais un jeton expiré à
/// l'aveugle : cette partie ne renouvelle rien elle-même, l'écran Comptes reste la seule
/// voie de reconnexion (portée volontairement resserrée, voir le module doc).
#[tauri::command]
pub(crate) async fn chat_connect(
    app: AppHandle,
    state: State<'_, ChatState>,
) -> Result<(), String> {
    let now = vault::now_unix();

    if let Ok(Some(token)) = vault::load(Platform::Twitch) {
        if !vault::is_expired(&token, now) {
            let http = reqwest::Client::new();
            match crate::accounts::twitch_stream::fetch_account(
                &http,
                TWITCH_CLIENT_ID,
                &token.access_token,
            )
            .await
            {
                Ok(account) => match twitch::connect(
                    app.clone(),
                    account.login,
                    account.id,
                    &token.access_token,
                ) {
                    Ok(handle) => lock(&state).twitch = Some(handle),
                    Err(err) => {
                        let _ = app.emit("chat-error", format!("Twitch : {err}"));
                    }
                },
                Err(err) => {
                    let _ = app.emit(
                        "chat-error",
                        format!("Twitch : identifiant illisible ({err})"),
                    );
                }
            }
        }
    }

    if let Ok(Some(token)) = vault::load(Platform::YouTube) {
        if !vault::is_expired(&token, now) {
            let handle = youtube::connect(app.clone(), token.access_token.expose().to_string());
            lock(&state).youtube = Some(handle);
        }
    }

    Ok(())
}

/// Répond sur Twitch — la seule plateforme qui répond dans cette partie (voir le module
/// doc : YouTube reste en lecture seule ici).
#[tauri::command]
pub(crate) async fn chat_send(state: State<'_, ChatState>, text: String) -> Result<(), String> {
    twitch::send(&twitch_handle(&state)?, text).await
}

/// Met `user_id` en sourdine sur Twitch pour `duration_secs` secondes.
#[tauri::command]
pub(crate) async fn chat_timeout_user(
    state: State<'_, ChatState>,
    user_id: String,
    duration_secs: u32,
) -> Result<(), String> {
    twitch::timeout(&twitch_handle(&state)?, &user_id, duration_secs).await
}

/// Bannit `user_id` définitivement sur Twitch.
#[tauri::command]
pub(crate) async fn chat_ban_user(
    state: State<'_, ChatState>,
    user_id: String,
) -> Result<(), String> {
    twitch::ban(&twitch_handle(&state)?, &user_id).await
}

/// Coupe les connexions en cours — appelé à la fermeture du panneau Chat.
#[tauri::command]
pub(crate) fn chat_disconnect(state: State<'_, ChatState>) {
    let mut guard = lock(&state);
    if let Some(handle) = guard.youtube.take() {
        youtube::disconnect(&handle);
    }
    // Le client Twitch n'a pas de méthode `close()` explicite dans le crate : l'abandonner
    // ferme sa connexion (le crate le documente comme le chemin normal d'arrêt).
    guard.twitch = None;
}
