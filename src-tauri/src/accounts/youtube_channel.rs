//! Infos de diffusion YouTube — titre, description, catégorie, tags (F-054, pendant Jay
//! demandait « as-tu fait le panneau pour YouTube aussi » après le volet Twitch,
//! 2026-09-19).
//!
//! YouTube n'a PAS l'équivalent de « catégorie Twitch » sur le direct lui-même : un
//! direct EST une vidéo (`liveBroadcasts` et `videos` pointent le même id), et
//! titre/description/catégorie/tags vivent sur la ressource `videos`, jamais en PATCH
//! partiel — Google documente que `videos.update` REMPLACE tout le `snippet` fourni et
//! EFFACE ce qui en est absent (developers.google.com/youtube/v3/docs/videos/update,
//! vérifié 2026-09-19). D'où la forme de ce module : lire le `snippet` COMPLET juste
//! avant d'écrire, fusionner la demande dessus, renvoyer le tout — jamais un `Option`
//! par champ comme côté Twitch, la forme brute (`serde_json::Value`) porte des champs
//! que Hikari ne modélise pas (langue par défaut, miniatures...) sans les perdre.
//!
//! Trois appels, dans cet ordre : `liveBroadcasts.list` (quel direct est actif ?) →
//! `videos.list` (son snippet complet) → `videos.update` (le snippet fusionné). Jamais de
//! snippet mis en cache entre deux commandes : « relu frais à chaque publication » est
//! déjà la règle posée pour B12 (PET, jeton) — elle s'applique de la même façon ici, pour
//! la même raison (autre chose a pu changer le snippet entre-temps).

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::accounts::vault::Secret;

const API: &str = "https://www.googleapis.com/youtube/v3";

/// Un appel GET à l'API YouTube — jeton porteur, pas d'en-tête `Client-Id` (ce n'est pas
/// Twitch : Google identifie l'app par le jeton OAuth lui-même, jamais par un en-tête
/// séparé).
async fn get(http: &reqwest::Client, access_token: &Secret, url: &str) -> Result<String> {
    let reponse = http
        .get(url)
        .bearer_auth(access_token.expose())
        .send()
        .await
        .context("appel à YouTube")?;
    lire_reponse(reponse).await
}

/// Un appel PUT à l'API YouTube, corps JSON — `videos.update` n'a pas de PATCH, seulement
/// PUT (voir le doc de module).
async fn put(
    http: &reqwest::Client,
    access_token: &Secret,
    url: &str,
    body: &Value,
) -> Result<String> {
    let reponse = http
        .put(url)
        .bearer_auth(access_token.expose())
        .json(body)
        .send()
        .await
        .context("appel à YouTube")?;
    lire_reponse(reponse).await
}

async fn lire_reponse(reponse: reqwest::Response) -> Result<String> {
    let statut = reponse.status();
    let corps = reponse.text().await.context("réponse YouTube illisible")?;
    if !statut.is_success() {
        bail!("YouTube a refusé ({statut}) : {corps}");
    }
    Ok(corps)
}

/// L'identifiant du direct ACTIF du compte connecté — c'est aussi l'identifiant de la
/// vidéo (`videos.list`/`videos.update` le prennent tel quel).
pub fn parse_active_broadcast_id(body: &str) -> Result<String> {
    let value: Value = serde_json::from_str(body).context("réponse YouTube illisible (direct)")?;
    let id = value
        .get("items")
        .and_then(|items| items.get(0))
        .and_then(|entry| entry.get("id"))
        .and_then(|id| id.as_str());
    match id {
        Some(id) if !id.is_empty() => Ok(id.to_string()),
        _ => bail!("aucun direct actif sur ce compte YouTube"),
    }
}

/// Ce que le panneau montre — extrait du `snippet` complet, jamais l'inverse : ce type
/// n'est JAMAIS ce qui part en écriture (voir le doc de module), seulement ce qui
/// s'affiche.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct VideoInfo {
    pub title: String,
    pub description: String,
    pub category_id: String,
    pub tags: Vec<String>,
}

/// Le `snippet` d'une vidéo YouTube — rendu comme `Value` BRUT (jamais désérialisé en
/// struct typée) : c'est ce même objet, à peine modifié, qui doit repartir en écriture
/// (`merge_patch`) sans perdre les champs que Hikari ne connaît pas.
pub fn parse_video_snippet(body: &str) -> Result<Value> {
    let value: Value = serde_json::from_str(body).context("réponse YouTube illisible (vidéo)")?;
    value
        .get("items")
        .and_then(|items| items.get(0))
        .and_then(|entry| entry.get("snippet"))
        .cloned()
        .context("YouTube n'a pas rendu le snippet de cette vidéo")
}

/// Lit `snippet` (brut) pour l'affichage — un champ manquant devient une chaîne/liste
/// vide plutôt qu'une erreur : `categoryId` par exemple n'est pas garanti présent sur
/// tous les comptes.
pub fn parse_video_info(snippet: &Value) -> VideoInfo {
    let texte = |champ: &str| {
        snippet
            .get(champ)
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string()
    };
    let tags = snippet
        .get("tags")
        .and_then(|v| v.as_array())
        .map(|tags| {
            tags.iter()
                .filter_map(|t| t.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    VideoInfo {
        title: texte("title"),
        description: texte("description"),
        category_id: texte("categoryId"),
        tags,
    }
}

/// Ce que Jay veut changer — comme côté Twitch (`ChannelInfoPatch`), `None` = ne touche
/// pas ce champ. La différence est dans `merge_patch` : Twitch envoie ce patch tel quel
/// (PATCH partiel réel) ; ici, le patch est fusionné SUR le snippet complet AVANT
/// l'envoi, parce que `videos.update` ne connaît pas la notion de "champ non fourni".
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct VideoInfoPatch {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub category_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
}

/// Refuse AVANT l'appel réseau ce que YouTube refuserait de toute façon — limites
/// documentées (developers.google.com/youtube/v3/docs/videos/update, vérifié
/// 2026-09-19) : titre 1-100 caractères, description ≤5000 caractères. YouTube ne
/// documente pas de limite PAR tag à cet endroit (contrairement à Twitch) — ne rien
/// inventer, laisser YouTube répondre pour ce cas-là (son message d'erreur voyage tel
/// quel jusqu'à l'écran, voir `lire_reponse`).
pub fn validate_patch(patch: &VideoInfoPatch) -> Result<(), String> {
    if let Some(title) = &patch.title {
        if title.is_empty() {
            return Err("le titre ne peut pas être vide".to_string());
        }
        if title.chars().count() > 100 {
            return Err("le titre dépasse 100 caractères (limite YouTube)".to_string());
        }
    }
    if let Some(description) = &patch.description {
        if description.chars().count() > 5000 {
            return Err("la description dépasse 5000 caractères (limite YouTube)".to_string());
        }
    }
    if patch.title.is_none()
        && patch.description.is_none()
        && patch.category_id.is_none()
        && patch.tags.is_none()
    {
        return Err("rien à mettre à jour".to_string());
    }
    Ok(())
}

/// Fusionne `patch` SUR `snippet` (cloné, jamais modifié en place) — chaque champ
/// présent REMPLACE, chaque champ absent laisse la valeur déjà lue intacte. C'est cette
/// fusion, pas `patch` seul, qui part dans `videos.update` : le contrat "remplace tout"
/// de YouTube l'exige (voir le doc de module).
pub fn merge_patch(snippet: &Value, patch: &VideoInfoPatch) -> Value {
    // `snippet` vient TOUJOURS de `parse_video_snippet`, qui ne rend que ce que
    // `entry.get("snippet")` a effectivement trouvé — un objet JSON par contrat YouTube.
    // Jamais de `panic!` ici pour autant : si la forme surprenait un jour, repartir d'un
    // objet vide plutôt que de planter cette commande — les champs du patch s'écrivent
    // quand même, seuls les champs non modélisés (langue par défaut...) se perdraient,
    // jamais toute la mise à jour.
    let mut merged = if snippet.is_object() {
        snippet.clone()
    } else {
        json!({})
    };
    let object = merged.as_object_mut().expect("json!({}) est un objet");
    if let Some(title) = &patch.title {
        object.insert("title".to_string(), json!(title));
    }
    if let Some(description) = &patch.description {
        object.insert("description".to_string(), json!(description));
    }
    if let Some(category_id) = &patch.category_id {
        object.insert("categoryId".to_string(), json!(category_id));
    }
    if let Some(tags) = &patch.tags {
        object.insert("tags".to_string(), json!(tags));
    }
    merged
}

/// Une catégorie YouTube proposée (`videoCategories.list`) — taxonomie fixée par Google,
/// jamais une recherche libre comme côté Twitch.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct CategoryOption {
    pub id: String,
    pub name: String,
}

pub fn parse_categories(body: &str) -> Result<Vec<CategoryOption>> {
    let value: Value =
        serde_json::from_str(body).context("réponse YouTube illisible (catégories)")?;
    let items = value
        .get("items")
        .and_then(|items| items.as_array())
        .context("YouTube n'a pas rendu de liste de catégories")?;
    Ok(items
        .iter()
        .filter_map(|entry| {
            let id = entry.get("id")?.as_str()?.to_string();
            let name = entry.get("snippet")?.get("title")?.as_str()?.to_string();
            Some(CategoryOption { id, name })
        })
        .collect())
}

/// L'identifiant du direct actif du compte connecté.
pub async fn fetch_active_broadcast_id(
    http: &reqwest::Client,
    access_token: &Secret,
) -> Result<String> {
    let url = format!("{API}/liveBroadcasts?part=id&broadcastStatus=active&mine=true");
    let body = get(http, access_token, &url)
        .await
        .context("recherche du direct actif YouTube")?;
    parse_active_broadcast_id(&body)
}

/// Le `snippet` complet de la vidéo `video_id` — brut, voir le doc de module.
pub async fn fetch_video_snippet(
    http: &reqwest::Client,
    access_token: &Secret,
    video_id: &str,
) -> Result<Value> {
    let url = format!("{API}/videos?part=snippet&id={video_id}");
    let body = get(http, access_token, &url)
        .await
        .context("lecture des infos de la vidéo")?;
    parse_video_snippet(&body)
}

/// Les catégories disponibles pour `region_code` (« FR » par défaut, Jay diffuse en
/// France — voir l'appelant).
pub async fn fetch_categories(
    http: &reqwest::Client,
    access_token: &Secret,
    region_code: &str,
) -> Result<Vec<CategoryOption>> {
    let url = format!("{API}/videoCategories?part=snippet&regionCode={region_code}");
    let body = get(http, access_token, &url)
        .await
        .context("lecture des catégories YouTube")?;
    parse_categories(&body)
}

/// Le direct actif du compte connecté, infos ACTUELLES — combine les deux premiers
/// appels (voir le doc de module) pour l'ouverture du panneau.
pub async fn fetch_active_video_info(
    http: &reqwest::Client,
    access_token: &Secret,
) -> Result<VideoInfo> {
    let video_id = fetch_active_broadcast_id(http, access_token).await?;
    let snippet = fetch_video_snippet(http, access_token, &video_id).await?;
    Ok(parse_video_info(&snippet))
}

/// Écrit `patch` sur le direct actif du compte connecté — relit le snippet FRAIS avant de
/// fusionner (voir le doc de module), jamais un snippet gardé d'un appel précédent.
pub async fn update_active_video_info(
    http: &reqwest::Client,
    access_token: &Secret,
    patch: &VideoInfoPatch,
) -> Result<()> {
    if let Err(motif) = validate_patch(patch) {
        bail!(motif);
    }
    let video_id = fetch_active_broadcast_id(http, access_token).await?;
    let snippet = fetch_video_snippet(http, access_token, &video_id).await?;
    let merged = merge_patch(&snippet, patch);
    let url = format!("{API}/videos?part=snippet");
    let body = json!({ "id": video_id, "snippet": merged });
    put(http, access_token, &url, &body)
        .await
        .context("mise à jour des infos de la vidéo")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const DIRECT: &str = r#"{"items":[{"id":"dQw4w9WgXcQ","snippet":{"title":"x"}}]}"#;

    #[test]
    fn should_read_the_active_broadcast_id() {
        assert_eq!(parse_active_broadcast_id(DIRECT).unwrap(), "dQw4w9WgXcQ");
    }

    #[test]
    fn should_refuse_when_no_broadcast_is_active() {
        assert!(parse_active_broadcast_id(r#"{"items":[]}"#).is_err());
        assert!(parse_active_broadcast_id("pas du json").is_err());
    }

    const VIDEO: &str = r#"{"items":[{"id":"dQw4w9WgXcQ","snippet":{
        "publishedAt":"2026-09-19T10:00:00Z",
        "channelId":"UC123",
        "title":"Session de dev Hikari",
        "description":"On code un panneau YouTube.",
        "categoryId":"20",
        "tags":["francais","dev"],
        "defaultLanguage":"fr"
    }}]}"#;

    #[test]
    fn should_read_the_full_snippet_as_a_raw_value() {
        let snippet = parse_video_snippet(VIDEO).unwrap();
        // Un champ que Hikari ne modélise pas (`defaultLanguage`) doit survivre à la
        // lecture — c'est tout le sens de garder cette forme brute.
        assert_eq!(snippet["defaultLanguage"], "fr");
        assert_eq!(snippet["title"], "Session de dev Hikari");
    }

    #[test]
    fn should_refuse_a_video_answer_with_no_data() {
        assert!(parse_video_snippet(r#"{"items":[]}"#).is_err());
        assert!(parse_video_snippet("pas du json").is_err());
    }

    #[test]
    fn should_extract_typed_info_from_the_snippet() {
        let snippet = parse_video_snippet(VIDEO).unwrap();
        let info = parse_video_info(&snippet);
        assert_eq!(info.title, "Session de dev Hikari");
        assert_eq!(info.description, "On code un panneau YouTube.");
        assert_eq!(info.category_id, "20");
        assert_eq!(info.tags, vec!["francais", "dev"]);
    }

    #[test]
    fn should_default_missing_fields_to_empty_rather_than_fail() {
        let info = parse_video_info(&json!({"title": "seul le titre"}));
        assert_eq!(info.title, "seul le titre");
        assert_eq!(info.description, "");
        assert_eq!(info.category_id, "");
        assert_eq!(info.tags, Vec::<String>::new());
    }

    fn patch(title: Option<&str>, description: Option<&str>) -> VideoInfoPatch {
        VideoInfoPatch {
            title: title.map(str::to_string),
            description: description.map(str::to_string),
            category_id: None,
            tags: None,
        }
    }

    #[test]
    fn should_merge_only_the_given_fields_and_keep_the_rest() {
        let snippet = parse_video_snippet(VIDEO).unwrap();
        let merged = merge_patch(&snippet, &patch(Some("Nouveau titre"), None));

        assert_eq!(merged["title"], "Nouveau titre");
        // Jamais touché par le patch : DOIT rester la valeur lue, pas disparaître.
        assert_eq!(merged["description"], "On code un panneau YouTube.");
        assert_eq!(merged["defaultLanguage"], "fr");
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
    fn should_refuse_a_title_over_100_characters() {
        let trop_long = "x".repeat(101);
        assert!(validate_patch(&patch(Some(&trop_long), None)).is_err());
    }

    #[test]
    fn should_accept_a_title_of_exactly_100_characters() {
        let pile = "x".repeat(100);
        assert!(validate_patch(&patch(Some(&pile), None)).is_ok());
    }

    #[test]
    fn should_refuse_a_description_over_5000_characters() {
        let trop_long = "x".repeat(5001);
        assert!(validate_patch(&patch(None, Some(&trop_long))).is_err());
    }

    #[test]
    fn should_refuse_a_patch_with_nothing_to_update() {
        assert_eq!(
            validate_patch(&VideoInfoPatch::default()),
            Err("rien à mettre à jour".to_string())
        );
    }

    const CATEGORIES: &str = r#"{"items":[
        {"id":"20","snippet":{"title":"Gaming"}},
        {"id":"24","snippet":{"title":"Entertainment"}}
    ]}"#;

    #[test]
    fn should_read_category_options() {
        let categories = parse_categories(CATEGORIES).unwrap();
        assert_eq!(
            categories,
            vec![
                CategoryOption {
                    id: "20".to_string(),
                    name: "Gaming".to_string()
                },
                CategoryOption {
                    id: "24".to_string(),
                    name: "Entertainment".to_string()
                },
            ]
        );
    }

    #[test]
    fn should_refuse_a_categories_answer_that_is_not_the_expected_shape() {
        for body in ["", "pas du json", "{}"] {
            assert!(parse_categories(body).is_err(), "body = {body}");
        }
    }
}
