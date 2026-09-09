//! Où diffuser sur Twitch, et avec quelle clé.
//!
//! Ce que ça règle (Jay, 2026-09-06) : il a connecté son compte Twitch, cliqué
//! « Démarrer », et l'application a annoncé « en direct » — alors que rien n'arrivait sur
//! Twitch. La diffusion partait vers `rtmp://localhost:1935/live`, la valeur de repli du
//! moteur, c'est-à-dire nulle part.
//!
//! Deux choses manquaient entre son compte et le moteur : SA clé, et l'adresse d'un
//! serveur d'entrée Twitch. Les voici. La permission de lire la clé était déjà demandée à
//! la connexion (`channel:read:stream_key`) — elle n'avait simplement jamais servi.
//!
//! Les fonctions ci-dessous sont PURES : elles lisent une réponse déjà reçue. C'est ce qui
//! les rend vérifiables sans réseau, sur les formes exactes que Twitch documente.

use anyhow::{bail, Context, Result};

use crate::accounts::vault::Secret;

/// L'adresse par défaut de Twitch, si la liste des serveurs d'entrée est injoignable.
///
/// Twitch ne publie pas d'adresse « automatique » : sa liste ne contient que des serveurs
/// géographiques, dont un marqué par défaut. Cette valeur est celle de ce serveur au
/// 2026-09-06 ; elle sert de repli, jamais de premier choix — un repli silencieux qui
/// devient la norme est exactement ce qui a produit le défaut du jour.
pub const TWITCH_INGEST_FALLBACK: &str = "rtmp://live.twitch.tv/app";

/// L'identifiant du compte connecté, lu dans la réponse de `GET /helix/users`.
///
/// Nécessaire parce que la lecture de la clé se fait PAR diffuseur, et que Twitch ne
/// déduit pas le diffuseur du jeton : il faut le lui nommer.
pub fn parse_user_id(body: &str) -> Result<String> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("réponse Twitch illisible (compte)")?;
    let id = value
        .get("data")
        .and_then(|data| data.get(0))
        .and_then(|user| user.get("id"))
        .and_then(|id| id.as_str());
    match id {
        Some(id) if !id.is_empty() => Ok(id.to_string()),
        _ => bail!("Twitch n'a pas rendu l'identifiant du compte connecté"),
    }
}

/// Le nom LISIBLE du compte connecte, lu dans la meme reponse que son identifiant.
///
/// Pourquoi ca compte (Jay, 2026-09-07) : il a plusieurs comptes Twitch — un compte de test
/// sans public, et son compte principal. « J'ai besoin de savoir sur quel compte je suis. »
/// Sans ce nom, « connecte » ne repond pas a la seule question qui l'interesse avant un
/// direct.
///
/// Aucune permission supplementaire : `GET /helix/users` est deja appele pour trouver la
/// cle, et porte ce nom depuis toujours — il etait simplement jete.
///
/// Retombe sur `login` quand `display_name` manque : les deux existent sur tout compte
/// Twitch, et un nom approchant vaut mieux qu'aucun nom.
pub fn parse_user_display_name(body: &str) -> Result<String> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("reponse Twitch illisible (compte)")?;
    let user = value.get("data").and_then(|data| data.get(0));
    let nom = user
        .and_then(|user| user.get("display_name"))
        .and_then(|nom| nom.as_str())
        .filter(|nom| !nom.is_empty())
        .or_else(|| {
            user.and_then(|user| user.get("login"))
                .and_then(|nom| nom.as_str())
                .filter(|nom| !nom.is_empty())
        });
    match nom {
        Some(nom) => Ok(nom.to_string()),
        None => bail!("Twitch n'a pas rendu le nom du compte connecte"),
    }
}

/// La clé de diffusion, lue dans la réponse de `GET /helix/streams/key`.
///
/// Rend une chaîne nue et non un secret enveloppé : l'appelant l'enveloppe aussitôt. Cette
/// fonction est le seul endroit où la valeur existe à découvert, et elle ne l'écrit nulle
/// part — surtout pas dans un message d'erreur.
pub fn parse_stream_key(body: &str) -> Result<String> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("réponse Twitch illisible (clé de diffusion)")?;
    let key = value
        .get("data")
        .and_then(|data| data.get(0))
        .and_then(|entry| entry.get("stream_key"))
        .and_then(|key| key.as_str());
    match key {
        Some(key) if !key.is_empty() => Ok(key.to_string()),
        _ => bail!("Twitch n'a pas rendu de clé de diffusion pour ce compte"),
    }
}

/// L'adresse du serveur d'entrée à utiliser, lue dans la liste publique de Twitch.
///
/// Twitch décrit chaque serveur par un GABARIT contenant `{stream_key}` — parce qu'un
/// lecteur ordinaire colle les deux. Le moteur, lui, veut le serveur et la clé séparés :
/// le gabarit est donc coupé à cet endroit. Sans cette coupe, la clé se retrouverait dans
/// l'adresse, et le moteur la collerait une seconde fois.
///
/// Le serveur retenu est celui que Twitch marque par défaut. À défaut, le premier
/// disponible — jamais un choix au hasard, l'ordre d'une liste n'est pas une préférence.
pub fn ingest_server(body: &str) -> Result<String> {
    let value: serde_json::Value =
        serde_json::from_str(body).context("liste des serveurs Twitch illisible")?;
    let servers = value
        .get("ingests")
        .and_then(|ingests| ingests.as_array())
        .context("liste des serveurs Twitch sans entrée")?;
    let chosen = servers
        .iter()
        .find(|server| server.get("default").and_then(serde_json::Value::as_bool) == Some(true))
        .or_else(|| {
            servers.iter().find(|server| {
                server
                    .get("availability")
                    .and_then(serde_json::Value::as_f64)
                    .unwrap_or(0.0)
                    > 0.0
            })
        })
        .context("aucun serveur Twitch disponible")?;
    let template = chosen
        .get("url_template")
        .and_then(serde_json::Value::as_str)
        .context("serveur Twitch sans adresse")?;
    Ok(strip_key_placeholder(template))
}

/// Coupe le gabarit juste avant l'emplacement de la clé, et retire la barre qui les sépare.
/// Un gabarit sans emplacement est rendu tel quel : couper ce qui n'existe pas mutilerait
/// une adresse valable.
fn strip_key_placeholder(template: &str) -> String {
    match template.find("/{stream_key}") {
        Some(cut) => template[..cut].to_string(),
        None => template
            .trim_end_matches("{stream_key}")
            .trim_end_matches('/')
            .to_string(),
    }
}

/// La destination Twitch du compte connecté : serveur d'entrée, clé de diffusion, et le NOM
/// du compte.
///
/// Le nom vient de la MEME réponse que l'identifiant (`GET /helix/users`), déjà appelée
/// ici : l'afficher ne coûte donc aucun appel de plus, ni aucune permission de plus. Il
/// était simplement jeté jusqu'au 2026-09-07.
///
/// Trois appels, dans cet ordre, parce que chacun a besoin du précédent : qui est connecté,
/// quelle est SA clé, et par quel serveur passer. Un échec à n'importe quelle étape rend
/// une erreur — jamais une destination à moitié remplie, qui ferait échouer la diffusion
/// plus loin sans dire où.
///
/// La clé revient enveloppée : elle ne doit apparaître ni dans un journal, ni dans un
/// message d'erreur, ni dans un affichage.
pub async fn fetch_target(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
) -> Result<(String, Secret, Option<String>)> {
    let compte = helix(
        http,
        client_id,
        access_token,
        "https://api.twitch.tv/helix/users",
    )
    .await
    .context("lecture du compte Twitch")?;
    let broadcaster = parse_user_id(&compte)?;
    // Un nom illisible n'empêche PAS de diffuser : c'est un confort d'affichage, jamais une
    // condition. Le refuser ici transformerait une gêne en panne.
    let nom = parse_user_display_name(&compte).ok();

    let url = format!("https://api.twitch.tv/helix/streams/key?broadcaster_id={broadcaster}");
    let reponse = helix(http, client_id, access_token, &url)
        .await
        .context("lecture de la clé Twitch")?;
    let key = Secret::new(parse_stream_key(&reponse)?);

    // La liste des serveurs est publique : ni jeton, ni identifiant d'application. Son
    // échec ne doit pas empêcher de diffuser — d'où le repli, ANNONCÉ et non silencieux.
    let server = match http.get("https://ingest.twitch.tv/ingests").send().await {
        Ok(reponse) => match reponse.text().await {
            Ok(corps) => ingest_server(&corps).unwrap_or_else(|err| {
                eprintln!(
                    "[twitch] serveurs indisponibles ({err}), repli sur l'adresse par défaut"
                );
                TWITCH_INGEST_FALLBACK.to_string()
            }),
            Err(err) => {
                eprintln!("[twitch] serveurs illisibles ({err}), repli sur l'adresse par défaut");
                TWITCH_INGEST_FALLBACK.to_string()
            }
        },
        Err(err) => {
            eprintln!("[twitch] serveurs injoignables ({err}), repli sur l'adresse par défaut");
            TWITCH_INGEST_FALLBACK.to_string()
        }
    };
    Ok((server, key, nom))
}

/// Le nom du compte connecte, et rien d'autre.
///
/// Un seul appel, celui que `fetch_target` fait deja pour trouver l'identifiant. Existe a
/// part pour le moment de la CONNEXION, ou l'on a besoin du nom sans avoir besoin de la
/// cle : demander la cle a ce moment-la ferait sortir un secret du coffre pour rien.
pub async fn fetch_display_name(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
) -> Result<String> {
    let compte = helix(
        http,
        client_id,
        access_token,
        "https://api.twitch.tv/helix/users",
    )
    .await
    .context("lecture du compte Twitch")?;
    parse_user_display_name(&compte)
}

/// Un appel à l'interface Twitch, avec les deux en-têtes qu'elle exige. Le corps est rendu
/// tel quel : la lecture appartient aux fonctions pures ci-dessus, vérifiables sans réseau.
async fn helix(
    http: &reqwest::Client,
    client_id: &str,
    access_token: &Secret,
    url: &str,
) -> Result<String> {
    let reponse = http
        .get(url)
        .header("Client-Id", client_id)
        .bearer_auth(access_token.expose())
        .send()
        .await
        .context("appel à Twitch")?;
    let statut = reponse.status();
    let corps = reponse.text().await.context("réponse Twitch illisible")?;
    if !statut.is_success() {
        // Le corps peut contenir le détail de Twitch, jamais un secret : il est repris.
        bail!("Twitch a refusé ({statut}) : {corps}");
    }
    Ok(corps)
}

#[cfg(test)]
mod tests {

    #[test]
    fn should_read_the_display_name_of_the_connected_account() {
        let body =
            r#"{"data":[{"id":"141981764","login":"twitchdev","display_name":"TwitchDev"}]}"#;
        assert_eq!(parse_user_display_name(body).unwrap(), "TwitchDev");
    }

    #[test]
    fn should_fall_back_to_the_login_when_the_display_name_is_missing() {
        let body = r#"{"data":[{"id":"1","login":"krom_kam"}]}"#;
        assert_eq!(parse_user_display_name(body).unwrap(), "krom_kam");
    }

    #[test]
    fn should_fail_when_twitch_returns_no_account() {
        assert!(parse_user_display_name(r#"{"data":[]}"#).is_err());
        assert!(parse_user_display_name("pas du json").is_err());
    }
    use super::*;

    /// Forme exacte documentée par Twitch pour `GET /helix/streams/key`
    /// (dev.twitch.tv/docs/api/reference, vérifiée le 2026-09-06).
    const CLE: &str = r#"{"data":[{"stream_key":"live_44322889_a34ub"}]}"#;
    /// Forme exacte de `GET /helix/users`.
    const COMPTE: &str = r#"{"data":[{"id":"141981764","login":"theermite"}]}"#;
    /// Forme exacte de la liste publique `ingest.twitch.tv/ingests` (vérifiée le 2026-09-06).
    const SERVEURS: &str = r#"{"ingests":[
        {"_id":1,"availability":1.0,"default":false,"name":"Paris","url_template":"rtmp://par.contribute.live-video.net/app/{stream_key}","priority":0},
        {"_id":2,"availability":1.0,"default":true,"name":"Default","url_template":"rtmp://ingest.global-contribute.live-video.net/app/{stream_key}","priority":0}
    ]}"#;

    #[test]
    fn should_read_the_stream_key_twitch_returns() {
        assert_eq!(parse_stream_key(CLE).unwrap(), "live_44322889_a34ub");
    }

    #[test]
    fn should_refuse_an_answer_that_carries_no_key() {
        // Un compte sans clé rend une liste vide. Rendre une chaîne vide ferait démarrer
        // une diffusion vers nulle part — exactement le défaut que ce module supprime.
        assert!(parse_stream_key(r#"{"data":[]}"#).is_err());
        assert!(parse_stream_key(r#"{"data":[{"stream_key":""}]}"#).is_err());
    }

    #[test]
    fn should_never_put_the_key_in_its_own_error() {
        // Un message d'erreur voyage dans les journaux et jusqu'à l'écran. La clé, jamais.
        let err = parse_stream_key(r#"{"data":[{"stream_key":""}]}"#)
            .unwrap_err()
            .to_string();

        assert!(!err.contains("stream_key"), "err = {err}");
    }

    #[test]
    fn should_read_the_account_id() {
        assert_eq!(parse_user_id(COMPTE).unwrap(), "141981764");
    }

    #[test]
    fn should_refuse_an_account_answer_without_an_id() {
        assert!(parse_user_id(r#"{"data":[]}"#).is_err());
    }

    #[test]
    fn should_choose_the_server_twitch_marks_as_default() {
        // Jamais le premier de la liste : l'ordre d'une liste n'est pas une préférence.
        assert_eq!(
            ingest_server(SERVEURS).unwrap(),
            "rtmp://ingest.global-contribute.live-video.net/app"
        );
    }

    #[test]
    fn should_fall_back_to_an_available_server_when_none_is_default() {
        let sans_defaut = r#"{"ingests":[
            {"availability":0.0,"default":false,"url_template":"rtmp://hs.example/app/{stream_key}"},
            {"availability":1.0,"default":false,"url_template":"rtmp://ok.example/app/{stream_key}"}
        ]}"#;

        assert_eq!(ingest_server(sans_defaut).unwrap(), "rtmp://ok.example/app");
    }

    #[test]
    fn should_cut_the_template_before_the_key_placeholder() {
        // Le moteur veut le serveur et la clé SÉPARÉS. Laisser l'emplacement dans
        // l'adresse ferait coller la clé deux fois.
        let serveurs =
            r#"{"ingests":[{"default":true,"url_template":"rtmp://x.example/app/{stream_key}"}]}"#;
        let serveur = ingest_server(serveurs).unwrap();

        assert!(!serveur.contains("{stream_key}"), "serveur = {serveur}");
        assert!(!serveur.ends_with('/'), "serveur = {serveur}");
    }

    #[test]
    fn should_keep_an_address_that_has_no_placeholder() {
        // Couper ce qui n'existe pas mutilerait une adresse valable.
        let serveurs = r#"{"ingests":[{"default":true,"url_template":"rtmp://x.example/app"}]}"#;

        assert_eq!(ingest_server(serveurs).unwrap(), "rtmp://x.example/app");
    }

    #[test]
    fn should_refuse_a_server_list_that_is_empty() {
        assert!(ingest_server(r#"{"ingests":[]}"#).is_err());
    }

    #[test]
    fn should_refuse_a_body_that_is_not_the_expected_shape() {
        for body in ["", "pas du json", "{}", "[]"] {
            assert!(parse_stream_key(body).is_err(), "body = {body}");
            assert!(parse_user_id(body).is_err(), "body = {body}");
            assert!(ingest_server(body).is_err(), "body = {body}");
        }
    }
}
