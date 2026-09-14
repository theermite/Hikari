//! Alertes Twitch (EventSub, WebSocket) — follow, abonnement (direct/offert/resign),
//! bits (l'équivalent de don le plus proche que Twitch expose nativement) et raid. Décidé
//! avec Jay 2026-09-14 : « tant que chaque plateforme a toutes les alertes activées »,
//! donc les six familles que Twitch pousse réellement, aucune de côté.
//!
//! YouTube n'a pas d'équivalent ici : ses dons (Super Chat/Super Sticker) et ses membres
//! n'arrivent pas par une connexion à part comme sur Twitch — ils sont mélangés aux
//! messages ordinaires du chat, à trier dans `chat/youtube.rs`. Rester sur une brique
//! séparée aurait mélangé deux mécanismes très différents.
//!
//! Un simple protocole JSON sur WebSocket, contrairement au chat IRC — pas besoin d'un
//! crate Twitch dédié : `tokio-tungstenite` (générique) suffit, et chaque payload
//! d'événement est un objet JSON plat, du même genre que ceux déjà lus à la main partout
//! ailleurs dans ce module (`twitch_stream.rs`, `chat/youtube.rs`).
//!
//! Formes vérifiées 2026-09-14 (dev.twitch.tv/docs/eventsub) : le corps de création d'un
//! abonnement (`type`/`version`/`condition`/`transport`), l'identifiant de session dans
//! `payload.session.id` d'un message `session_welcome`, et le type + l'événement d'une
//! `notification` dans `metadata.subscription_type` / `payload.event`.
//!
//! Reconnexion (`session_reconnect`) simplifiée, dette acceptée : au lieu de basculer en
//! douceur vers la nouvelle connexion que Twitch propose (recommandation officielle),
//! cette version referme et se reconnecte depuis zéro comme pour toute autre coupure —
//! quelques secondes d'alertes possiblement manquées le temps rare où Twitch migre une
//! session, jamais un défaut sur le chemin courant.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use futures_util::StreamExt;
use tauri::{AppHandle, Emitter};
use tokio_tungstenite::tungstenite::Message;

use crate::accounts::twitch::TWITCH_CLIENT_ID;
use crate::accounts::vault::Secret;

const EVENTSUB_WS_URL: &str = "wss://eventsub.wss.twitch.tv/ws";
const SUBSCRIPTIONS_URL: &str = "https://api.twitch.tv/helix/eventsub/subscriptions";
/// Attente avant de retenter une connexion perdue — même ordre de grandeur que le sondage
/// YouTube (`chat/youtube.rs`), pour la même raison : ne jamais boucler à vide sur une
/// panne réseau.
const RETRY_DELAY: Duration = Duration::from_secs(10);

/// Une alerte telle qu'elle traverse vers l'interface. `username`/`from_username` sont
/// absents pour un don anonyme (Twitch envoie `null` — Hikari ne devine jamais un nom).
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ChatAlert {
    Follow {
        username: String,
    },
    Subscribe {
        username: String,
        tier: String,
    },
    SubscriptionGift {
        username: Option<String>,
        total: u32,
        tier: String,
    },
    Resub {
        username: String,
        tier: String,
        cumulative_months: u32,
        message: String,
    },
    Cheer {
        username: Option<String>,
        bits: u32,
        message: String,
    },
    Raid {
        from_username: String,
        viewers: u32,
    },
}

/// Ce qu'une commande garde pour couper la connexion.
pub struct AlertsHandle {
    stop: Arc<AtomicBool>,
}

pub fn connect(app: AppHandle, broadcaster_id: String, access_token: Secret) -> AlertsHandle {
    let stop = Arc::new(AtomicBool::new(false));
    let task_stop = stop.clone();

    tokio::spawn(async move {
        let http = reqwest::Client::new();
        while !task_stop.load(Ordering::SeqCst) {
            match run_session(&app, &http, &broadcaster_id, &access_token, &task_stop).await {
                SessionOutcome::Stopped => break,
                SessionOutcome::Retry => tokio::time::sleep(RETRY_DELAY).await,
            }
        }
    });

    AlertsHandle { stop }
}

pub fn disconnect(handle: &AlertsHandle) {
    handle.stop.store(true, Ordering::SeqCst);
}

enum SessionOutcome {
    Stopped,
    Retry,
}

async fn run_session(
    app: &AppHandle,
    http: &reqwest::Client,
    broadcaster_id: &str,
    access_token: &Secret,
    stop: &AtomicBool,
) -> SessionOutcome {
    let Ok((ws_stream, _)) = tokio_tungstenite::connect_async(EVENTSUB_WS_URL).await else {
        return SessionOutcome::Retry;
    };
    let (_write, mut read) = ws_stream.split();

    let session_id = loop {
        match read.next().await {
            Some(Ok(Message::Text(text))) => {
                if let WsFrame::Welcome(id) = classify(&text) {
                    break id;
                }
                // Tout ce qui précède le message de bienvenue est ignoré — le protocole
                // ne documente rien d'autre à ce stade, mais rien n'oblige à casser la
                // connexion sur un message inattendu plutôt que de continuer à attendre.
            }
            _ => return SessionOutcome::Retry,
        }
    };

    if let Err(err) = create_all_subscriptions(
        http,
        TWITCH_CLIENT_ID,
        access_token,
        broadcaster_id,
        &session_id,
    )
    .await
    {
        let _ = app.emit("chat-error", format!("Alertes Twitch : {err}"));
        return SessionOutcome::Retry;
    }

    loop {
        if stop.load(Ordering::SeqCst) {
            return SessionOutcome::Stopped;
        }
        match read.next().await {
            Some(Ok(Message::Text(text))) => {
                if let WsFrame::Notification {
                    subscription_type,
                    event,
                } = classify(&text)
                {
                    if let Some(alert) = alert_from_event(&subscription_type, &event) {
                        let _ = app.emit("chat-alert", alert);
                    }
                }
                // keepalive / reconnect / revocation / inconnu : voir le module doc pour
                // reconnect (traité comme une coupure ordinaire) ; les autres n'appellent
                // aucune action de cette partie.
            }
            _ => return SessionOutcome::Retry,
        }
    }
}

/// Ce qu'un message WebSocket EventSub peut être — classification pure, vérifiable sans
/// réseau sur les formes exactes que Twitch documente.
#[derive(Debug, PartialEq)]
enum WsFrame {
    Welcome(String),
    Notification {
        subscription_type: String,
        event: serde_json::Value,
    },
    Other,
}

fn classify(raw: &str) -> WsFrame {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(raw) else {
        return WsFrame::Other;
    };
    match value
        .pointer("/metadata/message_type")
        .and_then(|v| v.as_str())
    {
        Some("session_welcome") => value
            .pointer("/payload/session/id")
            .and_then(|v| v.as_str())
            .map(|id| WsFrame::Welcome(id.to_string()))
            .unwrap_or(WsFrame::Other),
        Some("notification") => {
            let subscription_type = value
                .pointer("/metadata/subscription_type")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string();
            let event = value
                .pointer("/payload/event")
                .cloned()
                .unwrap_or(serde_json::Value::Null);
            WsFrame::Notification {
                subscription_type,
                event,
            }
        }
        _ => WsFrame::Other,
    }
}

/// Traduit l'événement brut d'une notification en alerte affichable — `None` pour un
/// abonnement de type inconnu, ou pour un `channel.subscribe` marqué `is_gift` (déjà
/// couvert par son propre événement `channel.subscription.gift`, jamais compté deux fois).
fn alert_from_event(subscription_type: &str, event: &serde_json::Value) -> Option<ChatAlert> {
    let text = |key: &str| event.get(key).and_then(|v| v.as_str()).map(str::to_string);
    let number = |key: &str| event.get(key).and_then(|v| v.as_u64()).map(|n| n as u32);
    let flag = |key: &str| event.get(key).and_then(|v| v.as_bool()).unwrap_or(false);

    match subscription_type {
        "channel.follow" => Some(ChatAlert::Follow {
            username: text("user_name")?,
        }),
        "channel.subscribe" if !flag("is_gift") => Some(ChatAlert::Subscribe {
            username: text("user_name")?,
            tier: text("tier")?,
        }),
        "channel.subscription.gift" => Some(ChatAlert::SubscriptionGift {
            username: text("user_name"),
            total: number("total")?,
            tier: text("tier")?,
        }),
        "channel.subscription.message" => Some(ChatAlert::Resub {
            username: text("user_name")?,
            tier: text("tier")?,
            cumulative_months: number("cumulative_months")?,
            message: event
                .pointer("/message/text")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string(),
        }),
        "channel.cheer" => Some(ChatAlert::Cheer {
            username: text("user_name"),
            bits: number("bits")?,
            message: text("message").unwrap_or_default(),
        }),
        "channel.raid" => Some(ChatAlert::Raid {
            from_username: text("from_broadcaster_user_name")?,
            viewers: number("viewers")?,
        }),
        _ => None,
    }
}

fn follow_condition(broadcaster_id: &str) -> serde_json::Value {
    serde_json::json!({ "broadcaster_user_id": broadcaster_id, "moderator_user_id": broadcaster_id })
}

fn broadcaster_condition(broadcaster_id: &str) -> serde_json::Value {
    serde_json::json!({ "broadcaster_user_id": broadcaster_id })
}

fn raid_condition(broadcaster_id: &str) -> serde_json::Value {
    serde_json::json!({ "to_broadcaster_user_id": broadcaster_id })
}

/// Le corps de création d'un abonnement EventSub — pure, vérifiable sans réseau.
fn subscription_body(
    subscription_type: &str,
    version: &str,
    condition: serde_json::Value,
    session_id: &str,
) -> serde_json::Value {
    serde_json::json!({
        "type": subscription_type,
        "version": version,
        "condition": condition,
        "transport": { "method": "websocket", "session_id": session_id },
    })
}

async fn create_all_subscriptions(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
    session_id: &str,
) -> Result<(), String> {
    let subscriptions = [
        subscription_body(
            "channel.follow",
            "2",
            follow_condition(broadcaster_id),
            session_id,
        ),
        subscription_body(
            "channel.subscribe",
            "1",
            broadcaster_condition(broadcaster_id),
            session_id,
        ),
        subscription_body(
            "channel.subscription.gift",
            "1",
            broadcaster_condition(broadcaster_id),
            session_id,
        ),
        subscription_body(
            "channel.subscription.message",
            "1",
            broadcaster_condition(broadcaster_id),
            session_id,
        ),
        subscription_body(
            "channel.cheer",
            "1",
            broadcaster_condition(broadcaster_id),
            session_id,
        ),
        subscription_body(
            "channel.raid",
            "1",
            raid_condition(broadcaster_id),
            session_id,
        ),
    ];
    for body in subscriptions {
        create_subscription(http, client_id, access_token, body).await?;
    }
    Ok(())
}

async fn create_subscription(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    body: serde_json::Value,
) -> Result<(), String> {
    let response = http
        .post(SUBSCRIPTIONS_URL)
        .header("Client-Id", client_id)
        .bearer_auth(access_token.expose())
        .json(&body)
        .send()
        .await
        .map_err(|err| err.to_string())?;
    if !response.status().is_success() {
        let status = response.status();
        let text = response.text().await.unwrap_or_default();
        return Err(format!(
            "abonnement refusé ({status}) pour {} : {text}",
            body["type"]
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const WELCOME: &str = r#"{
        "metadata": {"message_type": "session_welcome"},
        "payload": {"session": {"id": "AQoQexAWVYKSTIu4ec_2VAxyuhAB"}}
    }"#;

    #[test]
    fn should_read_the_session_id_from_a_welcome_message() {
        assert_eq!(
            classify(WELCOME),
            WsFrame::Welcome("AQoQexAWVYKSTIu4ec_2VAxyuhAB".to_string())
        );
    }

    #[test]
    fn should_classify_unknown_or_malformed_frames_as_other() {
        assert_eq!(classify("pas du json"), WsFrame::Other);
        assert_eq!(
            classify(r#"{"metadata": {"message_type": "session_keepalive"}}"#),
            WsFrame::Other
        );
    }

    #[test]
    fn should_read_subscription_type_and_event_from_a_notification() {
        let raw = r#"{
            "metadata": {"message_type": "notification", "subscription_type": "channel.follow"},
            "payload": {"event": {"user_name": "KromKam"}}
        }"#;
        assert_eq!(
            classify(raw),
            WsFrame::Notification {
                subscription_type: "channel.follow".to_string(),
                event: serde_json::json!({"user_name": "KromKam"}),
            }
        );
    }

    #[test]
    fn should_build_a_follow_alert() {
        let event = serde_json::json!({"user_name": "KromKam"});
        assert_eq!(
            alert_from_event("channel.follow", &event),
            Some(ChatAlert::Follow {
                username: "KromKam".to_string()
            })
        );
    }

    #[test]
    fn should_build_a_subscribe_alert_when_not_a_gift() {
        let event = serde_json::json!({"user_name": "Ange", "tier": "1000", "is_gift": false});
        assert_eq!(
            alert_from_event("channel.subscribe", &event),
            Some(ChatAlert::Subscribe {
                username: "Ange".to_string(),
                tier: "1000".to_string()
            })
        );
    }

    #[test]
    fn should_skip_a_subscribe_event_that_is_actually_a_gift() {
        // Déjà compté par `channel.subscription.gift` — un double affichage pour le même
        // geste serait exactement le bruit que Jay a demandé d'éviter.
        let event = serde_json::json!({"user_name": "Ange", "tier": "1000", "is_gift": true});
        assert_eq!(alert_from_event("channel.subscribe", &event), None);
    }

    #[test]
    fn should_build_a_gift_alert_with_a_name() {
        let event = serde_json::json!({"user_name": "Jay", "total": 5, "tier": "1000"});
        assert_eq!(
            alert_from_event("channel.subscription.gift", &event),
            Some(ChatAlert::SubscriptionGift {
                username: Some("Jay".to_string()),
                total: 5,
                tier: "1000".to_string(),
            })
        );
    }

    #[test]
    fn should_build_an_anonymous_gift_alert_when_twitch_omits_the_name() {
        // Twitch rend `user_name: null` pour un don anonyme — jamais un nom deviné.
        let event = serde_json::json!({"total": 5, "tier": "1000"});
        assert_eq!(
            alert_from_event("channel.subscription.gift", &event),
            Some(ChatAlert::SubscriptionGift {
                username: None,
                total: 5,
                tier: "1000".to_string()
            })
        );
    }

    #[test]
    fn should_build_a_resub_alert_with_its_message() {
        let event = serde_json::json!({
            "user_name": "Ange", "tier": "2000", "cumulative_months": 8,
            "message": {"text": "toujours là !"}
        });
        assert_eq!(
            alert_from_event("channel.subscription.message", &event),
            Some(ChatAlert::Resub {
                username: "Ange".to_string(),
                tier: "2000".to_string(),
                cumulative_months: 8,
                message: "toujours là !".to_string(),
            })
        );
    }

    #[test]
    fn should_build_a_cheer_alert() {
        let event = serde_json::json!({"user_name": "Jay", "bits": 500, "message": "gg"});
        assert_eq!(
            alert_from_event("channel.cheer", &event),
            Some(ChatAlert::Cheer {
                username: Some("Jay".to_string()),
                bits: 500,
                message: "gg".to_string(),
            })
        );
    }

    #[test]
    fn should_build_an_anonymous_cheer_alert_when_twitch_omits_the_name() {
        let event = serde_json::json!({"bits": 100, "message": ""});
        assert_eq!(
            alert_from_event("channel.cheer", &event),
            Some(ChatAlert::Cheer {
                username: None,
                bits: 100,
                message: String::new()
            })
        );
    }

    #[test]
    fn should_build_a_raid_alert() {
        let event = serde_json::json!({"from_broadcaster_user_name": "Ange", "viewers": 42});
        assert_eq!(
            alert_from_event("channel.raid", &event),
            Some(ChatAlert::Raid {
                from_username: "Ange".to_string(),
                viewers: 42
            })
        );
    }

    #[test]
    fn should_return_none_for_an_unknown_subscription_type() {
        assert_eq!(
            alert_from_event("channel.update", &serde_json::json!({})),
            None
        );
    }

    #[test]
    fn should_target_the_broadcaster_as_its_own_moderator_for_follow() {
        // La condition `channel.follow` exige un modérateur — Hikari ne modère jamais que
        // son propre salon (même principe que `moderation.rs`).
        let condition = follow_condition("141981764");
        assert_eq!(condition["broadcaster_user_id"], "141981764");
        assert_eq!(condition["moderator_user_id"], "141981764");
    }

    #[test]
    fn should_target_incoming_raids_not_outgoing_ones() {
        // `to_broadcaster_user_id` (les raids reçus), jamais `from_broadcaster_user_id`
        // (ce qui alerterait sur les raids que Hikari lance chez les autres).
        let condition = raid_condition("141981764");
        assert_eq!(condition["to_broadcaster_user_id"], "141981764");
        assert!(condition.get("from_broadcaster_user_id").is_none());
    }

    #[test]
    fn should_build_a_subscription_body_with_websocket_transport() {
        let body = subscription_body(
            "channel.cheer",
            "1",
            broadcaster_condition("141981764"),
            "AQoQexAWVYKSTIu4ec_2VAxyuhAB",
        );
        assert_eq!(body["type"], "channel.cheer");
        assert_eq!(body["version"], "1");
        assert_eq!(body["condition"]["broadcaster_user_id"], "141981764");
        assert_eq!(body["transport"]["method"], "websocket");
        assert_eq!(
            body["transport"]["session_id"],
            "AQoQexAWVYKSTIu4ec_2VAxyuhAB"
        );
    }
}
