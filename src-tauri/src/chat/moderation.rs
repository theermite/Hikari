//! Actions de modération en ligne (Twitch) — mise en sourdine (timeout) et bannissement,
//! déclenchées sur le message survolé dans le panneau Chat. Auto-modération (spam, liens,
//! mots interdits) reste hors de cette partie : elle demande une DÉTECTION, pas seulement
//! un appel API — brique à part.
//!
//! YouTube n'a pas d'équivalent ici : le scope `youtube.readonly` ne le permettrait pas de
//! toute façon, et élargir un scope est une décision, jamais une dérive silencieuse (même
//! principe que `accounts::twitch::required_scopes`).
//!
//! Hikari modère toujours SON PROPRE salon — `moderator_id` vaut donc systématiquement
//! `broadcaster_id`, jamais un tiers (aucune notion de modérateur invité dans cette
//! partie).
//!
//! Forme de requête vérifiée 2026-09-14 : `broadcaster_id` et `moderator_id` sont des
//! paramètres de requête (jamais dans le corps), `user_id`/`duration`/`reason` forment un
//! objet UNIQUE (jamais un tableau) — confirmée par deux bibliothèques tierces qui
//! reflètent la référence Twitch (`twitch_api` Rust et `helix` Go), la page officielle
//! n'ayant pas rendu son exemple `curl` à la lecture directe.

use crate::accounts::vault::Secret;

const BANS_URL: &str = "https://api.twitch.tv/helix/moderation/bans";

/// L'adresse à appeler pour bannir/mettre en sourdine dans le salon de `broadcaster_id`.
/// Pure — vérifiable sans réseau.
fn ban_request_url(broadcaster_id: &str) -> String {
    format!("{BANS_URL}?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}")
}

/// Le corps de la requête — `duration` absent EST le bannissement permanent (forme que
/// Twitch documente, jamais une valeur à part). Pure — vérifiable sans réseau.
fn ban_request_body(user_id: &str, duration_secs: Option<u32>) -> serde_json::Value {
    let mut data = serde_json::json!({ "user_id": user_id });
    if let Some(secs) = duration_secs {
        data["duration"] = serde_json::json!(secs);
    }
    serde_json::json!({ "data": data })
}

/// Met `user_id` en sourdine pour `duration_secs` secondes.
pub async fn timeout_user(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
    user_id: &str,
    duration_secs: u32,
) -> Result<(), String> {
    ban(
        http,
        client_id,
        access_token,
        broadcaster_id,
        user_id,
        Some(duration_secs),
    )
    .await
}

/// Bannit `user_id` définitivement.
pub async fn ban_user(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
    user_id: &str,
) -> Result<(), String> {
    ban(http, client_id, access_token, broadcaster_id, user_id, None).await
}

async fn ban(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
    user_id: &str,
    duration_secs: Option<u32>,
) -> Result<(), String> {
    let response = http
        .post(ban_request_url(broadcaster_id))
        .header("Client-Id", client_id)
        .bearer_auth(access_token.expose())
        .json(&ban_request_body(user_id, duration_secs))
        .send()
        .await
        .map_err(|err| err.to_string())?;
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("Twitch a refusé ({status}) : {body}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_target_the_same_id_as_both_broadcaster_and_moderator() {
        // Hikari ne modère jamais qu'un tiers : les deux paramètres pointent le même
        // compte, celui qui a autorisé l'application.
        let url = ban_request_url("141981764");
        assert!(url.contains("broadcaster_id=141981764"));
        assert!(url.contains("moderator_id=141981764"));
    }

    #[test]
    fn should_include_a_duration_for_a_timeout() {
        let body = ban_request_body("9876", Some(600));
        assert_eq!(body["data"]["user_id"], "9876");
        assert_eq!(body["data"]["duration"], 600);
    }

    #[test]
    fn should_omit_the_duration_field_for_a_permanent_ban() {
        // L'ABSENCE du champ est ce que Twitch documente comme le bannissement permanent —
        // une valeur à part (0, null...) ne serait pas la même chose.
        let body = ban_request_body("9876", None);
        assert_eq!(body["data"]["user_id"], "9876");
        assert!(body["data"].get("duration").is_none());
    }
}
