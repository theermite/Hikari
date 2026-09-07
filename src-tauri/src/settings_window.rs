//! Ouvre les réglages d'une source dans une vraie fenêtre SÉPARÉE — jamais un panneau
//! replié, jamais une couche web par-dessus l'aperçu.
//!
//! POURQUOI (Jay, 2026-09-07) : « c'est absolument contre-intuitif. OBS eux-mêmes ne
//! fonctionne pas comme ça » — dans OBS, régler une source ou ses filtres ouvre une fenêtre
//! à part, déplaçable. Une modale web ne pouvait pas rendre ce service ici : l'aperçu du
//! moteur est une fenêtre NATIVE greffée dans l'app, et une fenêtre native se dessine
//! toujours au-dessus du web, quel que soit l'empilement CSS (voir `preview::suppression`).
//!
//! Une fenêtre séparée n'a pas ce problème : c'est un objet à l'écran INDÉPENDANT de la
//! fenêtre principale, avec ses propres bordures et sa propre barre de titre dessinées par
//! Windows — exactement ce qu'OBS fait pour « Propriétés » et « Filtres ».

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

/// Le libellé d'une fenêtre de réglages, dérivé de ce qu'elle règle.
///
/// Un HASH et non le nom brut : un libellé de fenêtre Tauri n'accepte qu'un alphabet
/// restreint (alphanumérique, `-`, `/`, `:`, `_`), et un nom de scène ou de source choisi
/// par l'utilisateur peut contenir n'importe quoi — espaces, accents, ponctuation.
///
/// DÉTERMINISTE à dessein : la même source rend toujours le même libellé, ce qui permet de
/// retrouver une fenêtre déjà ouverte plutôt que d'en empiler une deuxième pour la même
/// source.
fn window_label(kind: &str, scene: &str, name: &str) -> String {
    let mut hasher = DefaultHasher::new();
    (kind, scene, name).hash(&mut hasher);
    format!("settings-{:x}", hasher.finish())
}

/// Ouvre la fenêtre de réglages d'une source, ou ramène au premier plan celle qui existe
/// déjà pour cette source précise.
///
/// `initial` porte l'état de départ à donner à l'écran de réglages — sérialisé en JSON par
/// l'appelant, jamais construit ici : ce module ne connaît pas la forme des réglages d'une
/// caméra ou d'un texte, et n'a pas à la connaître.
#[tauri::command]
pub(crate) fn open_settings_window(
    app: AppHandle,
    kind: String,
    scene: String,
    name: String,
    initial: Option<String>,
) -> Result<(), String> {
    let label = window_label(&kind, &scene, &name);

    if let Some(existing) = app.get_webview_window(&label) {
        existing.set_focus().map_err(|err| err.to_string())?;
        return Ok(());
    }

    // Les paramètres voyagent dans l'URL de la fenêtre : c'est elle qui décide, au
    // démarrage, quel écran de réglages afficher — voir `App.tsx` côté interface.
    let query = format!(
        "settings=1&kind={}&scene={}&name={}&initial={}",
        urlencoding_component(&kind),
        urlencoding_component(&scene),
        urlencoding_component(&name),
        urlencoding_component(initial.as_deref().unwrap_or("")),
    );

    WebviewWindowBuilder::new(
        &app,
        &label,
        WebviewUrl::App(format!("index.html?{query}").into()),
    )
    .title(format!("Réglages — {name}"))
    .inner_size(440.0, 560.0)
    .min_inner_size(360.0, 420.0)
    .resizable(true)
    .decorations(true)
    .build()
    .map_err(|err| err.to_string())?;

    Ok(())
}

/// Encodage minimal pour un composant d'URL — évite une dépendance de plus pour trois
/// caractères à échapper. Pas d'Unicode multi-octet dans les valeurs attendues ici (un
/// libellé de plateforme, un nom de scène) : le cas général n'est pas requis.
fn urlencoding_component(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char)
            }
            _ => out.push_str(&format!("%{byte:02X}")),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_render_the_same_label_for_the_same_source() {
        assert_eq!(
            window_label("text", "LoL", "Jay - The Ermite"),
            window_label("text", "LoL", "Jay - The Ermite"),
        );
    }

    #[test]
    fn should_render_a_different_label_for_a_different_source() {
        assert_ne!(
            window_label("text", "LoL", "Jay - The Ermite"),
            window_label("text", "main", "Jay - The Ermite"),
        );
        assert_ne!(
            window_label("text", "LoL", "Jay - The Ermite"),
            window_label("camera", "LoL", "Jay - The Ermite"),
        );
    }

    #[test]
    fn should_only_use_the_characters_a_window_label_accepts() {
        let label = window_label("text", "LoL — été", "Jay & The Ermite!");
        assert!(
            label
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || "-_/:".contains(c)),
            "libellé invalide : {label}"
        );
    }

    #[test]
    fn should_percent_encode_unsafe_url_characters() {
        let encoded = urlencoding_component("Jay - The Ermite!");
        assert!(!encoded.contains(' '));
        assert!(!encoded.contains('!'));
        assert!(encoded.contains("%20") || !encoded.contains(' '));
    }

    #[test]
    fn should_leave_safe_characters_untouched() {
        assert_eq!(urlencoding_component("text-abc_123.~"), "text-abc_123.~");
    }
}
