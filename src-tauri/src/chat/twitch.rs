//! Connexion en lecture + réponse + modération au chat Twitch (IRC pour le chat, Helix
//! pour la modération), via le crate `twitch-irc` — préféré à une implémentation manuelle
//! du protocole (ce que l'outil de référence `chat-overlay` fait à la main, faute de
//! mieux en Python/Qt) : le crate porte déjà la reconnexion, le PING/PONG et le parsing
//! des tags, jamais réécrits ici.

use tauri::{AppHandle, Emitter};
use twitch_irc::login::StaticLoginCredentials;
use twitch_irc::message::ServerMessage;
use twitch_irc::{ClientConfig, SecureTCPTransport, TwitchIRCClient};

use crate::accounts::twitch::TWITCH_CLIENT_ID;
use crate::accounts::vault::{Platform, Secret};
use crate::chat::moderation;
use crate::chat::ChatMessage;

type Client = TwitchIRCClient<SecureTCPTransport, StaticLoginCredentials>;

/// Ce qu'une commande garde pour répondre, modérer et couper la connexion. `Clone` : le
/// crate documente le client IRC comme une poignée clonable pour un usage multi-thread —
/// c'est ce qui permet à `chat_send`/`chat_timeout_user`/`chat_ban_user` de le sortir du
/// verrou avant un `.await` (voir `chat/mod.rs`).
#[derive(Clone)]
pub struct TwitchChatHandle {
    client: Client,
    channel: String,
    /// Le SIEN — Hikari se modère toujours lui-même (voir `moderation.rs`).
    broadcaster_id: String,
    access_token: Secret,
}

/// Ouvre la connexion IRC pour `login` (le SIEN — Hikari rejoint toujours son propre
/// salon, jamais un autre) et relaie chaque message reçu comme événement `chat-message`.
/// `access_token` est le jeton déjà rangé dans le coffre — le crate ajoute lui-même le
/// préfixe `oauth:` qu'IRC exige (sa propre doc : "the token should be without the
/// `oauth:` prefix"), jamais ajouté ici. `broadcaster_id` est gardé pour les actions de
/// modération, qui passent par Helix, jamais par IRC.
pub fn connect(
    app: AppHandle,
    login: String,
    broadcaster_id: String,
    access_token: &Secret,
) -> Result<TwitchChatHandle, String> {
    let config = ClientConfig::new_simple(StaticLoginCredentials::new(
        login.clone(),
        Some(access_token.expose().to_string()),
    ));
    let (mut incoming, client) = Client::new(config);

    let reader_app = app.clone();
    tokio::spawn(async move {
        while let Some(message) = incoming.recv().await {
            if let ServerMessage::Privmsg(privmsg) = message {
                let _ = reader_app.emit(
                    "chat-message",
                    ChatMessage {
                        platform: Platform::Twitch,
                        username: privmsg.sender.name,
                        user_id: Some(privmsg.sender.id),
                        text: privmsg.message_text,
                    },
                );
            }
        }
    });

    client
        .join(login.clone())
        .map_err(|err| format!("connexion au chat Twitch refusée : {err}"))?;

    Ok(TwitchChatHandle {
        client,
        channel: login,
        broadcaster_id,
        access_token: access_token.clone(),
    })
}

/// Envoie `text` sur le salon déjà rejoint — la réponse (F-030 « réponse », première partie).
pub async fn send(handle: &TwitchChatHandle, text: String) -> Result<(), String> {
    handle
        .client
        .say(handle.channel.clone(), text)
        .await
        .map_err(|err| format!("envoi au chat Twitch échoué : {err}"))
}

/// Met `user_id` en sourdine — la modération inline (cette partie).
pub async fn timeout(
    handle: &TwitchChatHandle,
    user_id: &str,
    duration_secs: u32,
) -> Result<(), String> {
    moderation::timeout_user(
        &reqwest::Client::new(),
        TWITCH_CLIENT_ID,
        &handle.access_token,
        &handle.broadcaster_id,
        user_id,
        duration_secs,
    )
    .await
}

/// Bannit `user_id` définitivement — la modération inline (cette partie).
pub async fn ban(handle: &TwitchChatHandle, user_id: &str) -> Result<(), String> {
    moderation::ban_user(
        &reqwest::Client::new(),
        TWITCH_CLIENT_ID,
        &handle.access_token,
        &handle.broadcaster_id,
        user_id,
    )
    .await
}
