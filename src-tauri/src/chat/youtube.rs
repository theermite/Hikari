//! Lecture du chat YouTube — sondage périodique (YouTube n'offre pas de WebSocket de
//! chat), même principe que l'outil de référence `chat-overlay` (QTimer + REST), porté
//! ici en tâche tokio. Lecture SEULE dans cette partie : YouTube ne reçoit aucune réponse
//! (voir le module doc de `chat/mod.rs` — le scope `youtube.readonly` reste inchangé tant
//! qu'aucune brique n'envoie de message).

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use tauri::{AppHandle, Emitter};

use crate::accounts::vault::Platform;
use crate::chat::ChatMessage;

const BROADCASTS_URL: &str = "https://www.googleapis.com/youtube/v3/liveBroadcasts\
?part=snippet&broadcastStatus=active&broadcastType=all";
const CHAT_URL: &str = "https://www.googleapis.com/youtube/v3/liveChat/messages";
/// Attente entre deux tentatives quand aucun direct actif n'est trouvé, ou qu'un appel
/// échoue — mêmes ordres de grandeur que l'outil de référence (`chat-overlay`).
const RETRY_DELAY_MS: u64 = 10_000;
const NO_BROADCAST_DELAY_MS: u64 = 30_000;
const DEFAULT_POLL_DELAY_MS: u64 = 5_000;

/// Ce qu'une commande garde pour couper la connexion — un simple drapeau, lu par la
/// tâche de sondage à chaque tour de boucle.
pub struct YouTubeChatHandle {
    stop: Arc<AtomicBool>,
}

/// Démarre la tâche de sondage : trouve le direct actif du compte, puis lit son chat en
/// boucle jusqu'à `disconnect`. Ne bloque jamais l'appelant — tout se passe dans la tâche.
pub fn connect(app: AppHandle, access_token: String) -> YouTubeChatHandle {
    let stop = Arc::new(AtomicBool::new(false));
    let task_stop = stop.clone();

    tokio::spawn(async move {
        let http = reqwest::Client::new();
        while !task_stop.load(Ordering::SeqCst) {
            match find_active_chat_id(&http, &access_token).await {
                Some(chat_id) => poll_loop(&http, &access_token, &chat_id, &app, &task_stop).await,
                None => {
                    tokio::time::sleep(std::time::Duration::from_millis(NO_BROADCAST_DELAY_MS))
                        .await
                }
            }
        }
    });

    YouTubeChatHandle { stop }
}

/// Arrête la tâche de sondage à la prochaine vérification du drapeau — jamais immédiat,
/// borné par l'attente en cours (au plus `DEFAULT_POLL_DELAY_MS`/`RETRY_DELAY_MS`).
pub fn disconnect(handle: &YouTubeChatHandle) {
    handle.stop.store(true, Ordering::SeqCst);
}

async fn find_active_chat_id(http: &reqwest::Client, access_token: &str) -> Option<String> {
    let body = get(http, access_token, BROADCASTS_URL).await.ok()?;
    parse_chat_id(&body)
}

/// Le `liveChatId` du premier direct actif, s'il y en a un — forme exacte documentée par
/// `liveBroadcasts.list` (Google, vérifiée 2026-09-14).
fn parse_chat_id(body: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(body).ok()?;
    value
        .get("items")?
        .get(0)?
        .get("snippet")?
        .get("liveChatId")?
        .as_str()
        .map(str::to_string)
}

async fn poll_loop(
    http: &reqwest::Client,
    access_token: &str,
    chat_id: &str,
    app: &AppHandle,
    stop: &AtomicBool,
) {
    let mut page_token: Option<String> = None;
    while !stop.load(Ordering::SeqCst) {
        let mut url =
            format!("{CHAT_URL}?liveChatId={chat_id}&part=snippet,authorDetails&maxResults=50");
        if let Some(token) = &page_token {
            url.push_str(&format!("&pageToken={token}"));
        }
        match get(http, access_token, &url).await {
            Ok(body) => {
                let (messages, next_token, interval_ms) = parse_chat_page(&body);
                for mut message in messages {
                    // Horodaté ICI, pas dans `parse_chat_page` (pure, testée sur des
                    // pages figées) : c'est le moment réel où Hikari voit le message.
                    message.timestamp_ms = crate::chat::now_millis();
                    let _ = app.emit("chat-message", message);
                }
                page_token = next_token;
                tokio::time::sleep(std::time::Duration::from_millis(interval_ms.max(1000))).await;
            }
            Err(_) => {
                tokio::time::sleep(std::time::Duration::from_millis(RETRY_DELAY_MS)).await;
                return; // le direct a peut-être fini — on redemande un chat actif au tour suivant
            }
        }
    }
}

/// Les messages d'une page de `liveChat/messages`, le jeton de page suivante, et
/// l'intervalle que YouTube demande d'attendre avant le prochain appel — forme exacte
/// documentée par Google (`liveChatMessages.list`, vérifiée 2026-09-14). Un corps
/// illisible rend une page vide plutôt qu'un panic : une réponse hostile ne doit jamais
/// arrêter le sondage.
fn parse_chat_page(body: &str) -> (Vec<ChatMessage>, Option<String>, u64) {
    let value: serde_json::Value = match serde_json::from_str(body) {
        Ok(value) => value,
        Err(_) => return (Vec::new(), None, DEFAULT_POLL_DELAY_MS),
    };
    let messages = value
        .get("items")
        .and_then(|items| items.as_array())
        .map(|items| items.iter().filter_map(parse_one_message).collect())
        .unwrap_or_default();
    let next_token = value
        .get("nextPageToken")
        .and_then(|token| token.as_str())
        .map(str::to_string);
    let interval_ms = value
        .get("pollingIntervalMillis")
        .and_then(|ms| ms.as_u64())
        .unwrap_or(DEFAULT_POLL_DELAY_MS);
    (messages, next_token, interval_ms)
}

fn parse_one_message(item: &serde_json::Value) -> Option<ChatMessage> {
    let username = item
        .get("authorDetails")?
        .get("displayName")?
        .as_str()?
        .to_string();
    let text = item
        .get("snippet")?
        .get("displayMessage")?
        .as_str()?
        .to_string();
    Some(ChatMessage {
        platform: Platform::YouTube,
        username,
        text,
        user_id: None,
        // Rempli au moment de l'émission réelle (`poll_loop`), jamais ici : cette
        // fonction reste pure et testable sur des pages figées.
        timestamp_ms: 0,
    })
}

async fn get(http: &reqwest::Client, access_token: &str, url: &str) -> Result<String, String> {
    let response = http
        .get(url)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|err| err.to_string())?;
    if !response.status().is_success() {
        return Err(response.status().to_string());
    }
    response.text().await.map_err(|err| err.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Forme exacte de `liveBroadcasts.list` (Google, vérifiée 2026-09-14).
    const BROADCASTS: &str = r#"{"items":[{"snippet":{"liveChatId":"Cg0KC2FiY2RlZmdoaWpr"}}]}"#;

    #[test]
    fn should_read_the_chat_id_of_the_active_broadcast() {
        assert_eq!(
            parse_chat_id(BROADCASTS).as_deref(),
            Some("Cg0KC2FiY2RlZmdoaWpr")
        );
    }

    #[test]
    fn should_return_none_when_no_broadcast_is_active() {
        assert_eq!(parse_chat_id(r#"{"items":[]}"#), None);
    }

    #[test]
    fn should_return_none_when_broadcasts_body_is_malformed() {
        assert_eq!(parse_chat_id("pas du json"), None);
        assert_eq!(parse_chat_id("{}"), None);
    }

    /// Forme exacte de `liveChatMessages.list` (Google, vérifiée 2026-09-14).
    const CHAT_PAGE: &str = r#"{
        "items": [
            {"authorDetails": {"displayName": "Ange"}, "snippet": {"displayMessage": "coucou"}},
            {"authorDetails": {"displayName": "Jay"}, "snippet": {"displayMessage": "hello"}}
        ],
        "nextPageToken": "next-token-abc",
        "pollingIntervalMillis": 8000
    }"#;

    #[test]
    fn should_read_every_message_of_a_chat_page() {
        let (messages, next_token, interval_ms) = parse_chat_page(CHAT_PAGE);
        assert_eq!(
            messages,
            vec![
                ChatMessage {
                    platform: Platform::YouTube,
                    username: "Ange".to_string(),
                    text: "coucou".to_string(),
                    user_id: None,
                    timestamp_ms: 0,
                },
                ChatMessage {
                    platform: Platform::YouTube,
                    username: "Jay".to_string(),
                    text: "hello".to_string(),
                    user_id: None,
                    timestamp_ms: 0,
                },
            ]
        );
        assert_eq!(next_token.as_deref(), Some("next-token-abc"));
        assert_eq!(interval_ms, 8000);
    }

    #[test]
    fn should_default_the_poll_interval_when_youtube_omits_it() {
        let (_, _, interval_ms) = parse_chat_page(r#"{"items":[]}"#);
        assert_eq!(interval_ms, DEFAULT_POLL_DELAY_MS);
    }

    #[test]
    fn should_return_empty_page_when_body_is_malformed() {
        let (messages, next_token, interval_ms) = parse_chat_page("pas du json");
        assert_eq!(messages, Vec::new());
        assert_eq!(next_token, None);
        assert_eq!(interval_ms, DEFAULT_POLL_DELAY_MS);
    }

    #[test]
    fn should_skip_an_item_missing_the_fields_this_needs() {
        // Un item hostile/partiel ne doit jamais faire tomber toute la page — les autres
        // messages, valides, doivent quand même arriver.
        let body = r#"{"items": [
            {"authorDetails": {}},
            {"authorDetails": {"displayName": "Jay"}, "snippet": {"displayMessage": "ok"}}
        ]}"#;
        let (messages, _, _) = parse_chat_page(body);
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0].username, "Jay");
    }
}
