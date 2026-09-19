//! Infos de diffusion Twitch — titre, catégorie, tags (F-054) et compteur de spectateurs
//! en direct (F-062) — changement/lecture rapides depuis Hikari plutôt que depuis le site
//! Twitch.
//!
//! Réutilise le pont HTTP déjà écrit pour la clé de diffusion
//! (`twitch_stream::helix`/`helix_patch`) — mêmes deux en-têtes que Twitch exige partout
//! (Client-Id, jeton porteur), jamais réécrits une troisième fois.
//!
//! Les fonctions de lecture (`parse_channel_info`, `parse_categories`,
//! `parse_viewer_count`) sont PURES, comme le reste des lecteurs Twitch de ce module
//! (`twitch_stream.rs`) : vérifiables sans réseau, sur les formes exactes que Twitch
//! documente (dev.twitch.tv/docs/api/reference, Get/Modify Channel Information, Search
//! Categories, Get Streams — vérifié 2026-09-19).

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};

use crate::accounts::twitch_stream::{helix, helix_patch};
use crate::accounts::vault::Secret;

/// Ce que Twitch rend pour la chaîne du compte connecté (`GET /helix/channels`).
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ChannelInfo {
    pub title: String,
    pub game_id: String,
    pub game_name: String,
    pub tags: Vec<String>,
}

/// Lit la réponse de `GET /helix/channels` — un seul diffuseur demandé, donc `data[0]`.
pub fn parse_channel_info(body: &str) -> Result<ChannelInfo> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("réponse Twitch illisible (infos de la chaîne)")?;
    let entry = value
        .get("data")
        .and_then(|data| data.get(0))
        .context("Twitch n'a pas rendu d'infos pour cette chaîne")?;
    let texte = |champ: &str| {
        entry
            .get(champ)
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string()
    };
    let tags = entry
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|tags| {
            tags.iter()
                .filter_map(|t| t.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    Ok(ChannelInfo {
        title: texte("title"),
        game_id: texte("game_id"),
        game_name: texte("game_name"),
        tags,
    })
}

/// Une catégorie/jeu suggéré par la recherche Twitch.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct CategorySuggestion {
    pub id: String,
    pub name: String,
    pub box_art_url: String,
}

/// Lit la réponse de `GET /helix/search/categories`. Une entrée sans `id` NI `name` est
/// écartée plutôt que de rendre une suggestion vide — un choix inutilisable dans le
/// sélecteur n'aide personne.
pub fn parse_categories(body: &str) -> Result<Vec<CategorySuggestion>> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("réponse Twitch illisible (catégories)")?;
    let entries = value
        .get("data")
        .and_then(|data| data.as_array())
        .context("Twitch n'a pas rendu de liste de catégories")?;
    Ok(entries
        .iter()
        .filter_map(|entry| {
            let id = entry.get("id")?.as_str()?.to_string();
            let name = entry.get("name")?.as_str()?.to_string();
            let box_art_url = entry
                .get("box_art_url")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string();
            Some(CategorySuggestion {
                id,
                name,
                box_art_url,
            })
        })
        .collect())
}

/// Ce que Jay veut changer — chaque champ absent reste tel quel côté Twitch (`PATCH`
/// documente : seuls les champs présents sont modifiés). `Option` porte cette distinction
/// « ne pas toucher » vs « remplacer par une valeur vide », que `String` seule ne peut pas
/// porter.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ChannelInfoPatch {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub game_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
}

/// Refuse AVANT l'appel réseau tout ce que Twitch refuserait de toute façon — un
/// aller-retour évité vaut mieux qu'une erreur Twitch à traduire. Limites documentées
/// (Modify Channel Information, vérifié 2026-09-19) : titre 1-140 caractères, 10 tags au
/// plus, chaque tag 1-25 caractères.
pub fn validate_patch(patch: &ChannelInfoPatch) -> Result<(), String> {
    if let Some(title) = &patch.title {
        if title.is_empty() {
            return Err("le titre ne peut pas être vide".to_string());
        }
        if title.chars().count() > 140 {
            return Err("le titre dépasse 140 caractères (limite Twitch)".to_string());
        }
    }
    if let Some(tags) = &patch.tags {
        if tags.len() > 10 {
            return Err("10 tags au maximum (limite Twitch)".to_string());
        }
        if let Some(mauvais) = tags
            .iter()
            .find(|tag| tag.is_empty() || tag.chars().count() > 25)
        {
            return Err(format!(
                "tag invalide ({mauvais:?}) — 1 à 25 caractères, jamais vide"
            ));
        }
    }
    if patch.title.is_none() && patch.game_id.is_none() && patch.tags.is_none() {
        return Err("rien à mettre à jour".to_string());
    }
    Ok(())
}

/// Les infos ACTUELLES de la chaîne du compte connecté.
pub async fn fetch_channel_info(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
) -> Result<ChannelInfo> {
    let url = format!("https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}");
    let body = helix(http, client_id, access_token, &url)
        .await
        .context("lecture des infos de la chaîne")?;
    parse_channel_info(&body)
}

/// Les catégories Twitch dont le nom correspond à `query` — pour un sélecteur qui
/// cherche au fur et à mesure de la frappe, jamais une liste à parcourir à la main.
pub async fn search_categories(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    query: &str,
) -> Result<Vec<CategorySuggestion>> {
    let url = format!(
        "https://api.twitch.tv/helix/search/categories?query={}",
        urlencoding::encode(query)
    );
    let body = helix(http, client_id, access_token, &url)
        .await
        .context("recherche de catégories Twitch")?;
    parse_categories(&body)
}

/// Écrit `patch` sur la chaîne du compte connecté. Refuse localement (`validate_patch`)
/// avant tout appel réseau — Twitch n'est interrogé que sur une demande déjà valide.
pub async fn update_channel_info(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
    patch: &ChannelInfoPatch,
) -> Result<()> {
    if let Err(motif) = validate_patch(patch) {
        bail!(motif);
    }
    let url = format!("https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}");
    helix_patch(http, client_id, access_token, &url, patch)
        .await
        .context("mise à jour des infos de la chaîne")?;
    Ok(())
}

/// Le compteur de spectateurs ACTUEL du compte connecté — `None` si le direct n'est pas
/// en cours (Twitch rend une liste vide dans ce cas, jamais une entrée avec `viewer_count:
/// 0` — un stream de 0 spectateur RÉEL est indiscernable d'un stream arrêté sans ce
/// distinguo, voir `parse_viewer_count`).
pub async fn fetch_viewer_count(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    broadcaster_id: &str,
) -> Result<Option<u32>> {
    let url = format!("https://api.twitch.tv/helix/streams?user_id={broadcaster_id}");
    let body = helix(http, client_id, access_token, &url)
        .await
        .context("lecture du compteur de spectateurs")?;
    parse_viewer_count(&body)
}

/// Lit la réponse de `GET /helix/streams?user_id=...` — `data` est VIDE quand ce diffuseur
/// n'est pas en direct (documenté par Twitch), jamais une entrée à `viewer_count: 0`. Ce
/// distinguo est le seul moyen honnête d'afficher soit un vrai chiffre, soit « n/a » —
/// jamais un zéro qui laisserait croire que personne ne regarde un direct qui n'existe pas
/// (même principe que `LiveBar.tsx`, qui refuse déjà d'inventer un zéro).
pub fn parse_viewer_count(body: &str) -> Result<Option<u32>> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("réponse Twitch illisible (spectateurs)")?;
    let entries = value
        .get("data")
        .and_then(|data| data.as_array())
        .context("Twitch n'a pas rendu de liste de directs")?;
    Ok(entries
        .first()
        .and_then(|entry| entry.get("viewer_count"))
        .and_then(|count| count.as_u64())
        .map(|count| count as u32))
}

#[cfg(test)]
mod tests {
    use super::*;

    const CHAINE: &str = r#"{"data":[{
        "broadcaster_id":"141981764",
        "broadcaster_login":"theermite",
        "broadcaster_name":"TheErmite",
        "broadcaster_language":"fr",
        "game_id":"509658",
        "game_name":"Just Chatting",
        "title":"Session de dev Hikari",
        "delay":0,
        "tags":["Francais","Developpement"],
        "content_classification_labels":[],
        "is_branded_content":false
    }]}"#;

    #[test]
    fn should_read_the_channel_title_category_and_tags() {
        let info = parse_channel_info(CHAINE).unwrap();
        assert_eq!(info.title, "Session de dev Hikari");
        assert_eq!(info.game_id, "509658");
        assert_eq!(info.game_name, "Just Chatting");
        assert_eq!(info.tags, vec!["Francais", "Developpement"]);
    }

    #[test]
    fn should_read_an_empty_tag_list_as_empty_not_absent() {
        let sans_tags = r#"{"data":[{"title":"x","game_id":"1","game_name":"y","tags":[]}]}"#;
        assert_eq!(parse_channel_info(sans_tags).unwrap().tags, Vec::<String>::new());
    }

    #[test]
    fn should_refuse_a_channel_answer_with_no_data() {
        assert!(parse_channel_info(r#"{"data":[]}"#).is_err());
        assert!(parse_channel_info("pas du json").is_err());
    }

    const CATEGORIES: &str = r#"{"data":[
        {"id":"33214","name":"Fortnite","box_art_url":"https://x/{width}x{height}.jpg"},
        {"id":"509658","name":"Just Chatting","box_art_url":"https://x/{width}x{height}.jpg"}
    ]}"#;

    #[test]
    fn should_read_category_suggestions() {
        let categories = parse_categories(CATEGORIES).unwrap();
        assert_eq!(categories.len(), 2);
        assert_eq!(categories[0].id, "33214");
        assert_eq!(categories[0].name, "Fortnite");
    }

    #[test]
    fn should_skip_a_category_entry_missing_id_or_name() {
        let incomplete = r#"{"data":[{"name":"sans id"},{"id":"1"},{"id":"2","name":"ok"}]}"#;
        let categories = parse_categories(incomplete).unwrap();
        assert_eq!(categories, vec![CategorySuggestion {
            id: "2".to_string(),
            name: "ok".to_string(),
            box_art_url: String::new(),
        }]);
    }

    #[test]
    fn should_refuse_a_category_answer_that_is_not_the_expected_shape() {
        for body in ["", "pas du json", "{}"] {
            assert!(parse_categories(body).is_err(), "body = {body}");
        }
    }

    fn patch(title: Option<&str>, tags: Option<Vec<&str>>) -> ChannelInfoPatch {
        ChannelInfoPatch {
            title: title.map(str::to_string),
            game_id: None,
            tags: tags.map(|tags| tags.into_iter().map(str::to_string).collect()),
        }
    }

    #[test]
    fn should_accept_a_valid_title_only_patch() {
        assert!(validate_patch(&patch(Some("Nouveau titre"), None)).is_ok());
    }

    #[test]
    fn should_refuse_an_empty_title() {
        assert_eq!(
            validate_patch(&patch(Some(""), None)),
            Err("le titre ne peut pas être vide".to_string())
        );
    }

    #[test]
    fn should_refuse_a_title_over_140_characters() {
        let trop_long = "x".repeat(141);
        assert!(validate_patch(&patch(Some(&trop_long), None)).is_err());
    }

    #[test]
    fn should_accept_a_title_of_exactly_140_characters() {
        let pile = "x".repeat(140);
        assert!(validate_patch(&patch(Some(&pile), None)).is_ok());
    }

    #[test]
    fn should_refuse_more_than_ten_tags() {
        let onze: Vec<&str> = (0..11).map(|_| "tag").collect();
        assert!(validate_patch(&patch(None, Some(onze))).is_err());
    }

    #[test]
    fn should_refuse_an_empty_tag() {
        assert!(validate_patch(&patch(None, Some(vec!["ok", ""]))).is_err());
    }

    #[test]
    fn should_refuse_a_tag_over_25_characters() {
        let trop_long: String = "x".repeat(26);
        assert!(validate_patch(&patch(None, Some(vec![&trop_long]))).is_err());
    }

    #[test]
    fn should_refuse_a_patch_with_nothing_to_update() {
        assert_eq!(
            validate_patch(&ChannelInfoPatch::default()),
            Err("rien à mettre à jour".to_string())
        );
    }

    #[test]
    fn should_read_the_viewer_count_of_a_live_stream() {
        let body = r#"{"data":[{"id":"1","user_id":"141981764","viewer_count":78365,"type":"live"}]}"#;
        assert_eq!(parse_viewer_count(body).unwrap(), Some(78365));
    }

    #[test]
    fn should_read_no_viewer_count_when_the_stream_is_not_live() {
        // Twitch rend `data:[]` quand ce diffuseur n'est pas en direct — jamais une entrée
        // à 0. Confondre les deux ferait afficher « 0 spectateur » sur un stream arrêté.
        assert_eq!(parse_viewer_count(r#"{"data":[]}"#).unwrap(), None);
    }

    #[test]
    fn should_refuse_a_viewer_count_answer_that_is_not_the_expected_shape() {
        for body in ["", "pas du json", "{}"] {
            assert!(parse_viewer_count(body).is_err(), "body = {body}");
        }
    }

    #[test]
    fn should_serialize_only_the_fields_that_are_set() {
        // Un champ `None` doit DISPARAÎTRE du JSON, jamais devenir `null` — Twitch
        // documente qu'un champ absent n'est pas touché, `null` aurait un autre sens.
        let json = serde_json::to_string(&patch(Some("t"), None)).unwrap();
        assert!(json.contains("\"title\""));
        assert!(!json.contains("game_id"));
        assert!(!json.contains("tags"));
    }
}
