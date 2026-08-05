//! Sources de scène (brique Sources) — lister ce que la machine peut capturer, et poser
//! une capture dans une scène.
//!
//! POURQUOI cette brique existe : jusqu'ici le moteur ne connaissait que DEUX sources, une
//! capture d'écran posée en dur au démarrage et la webcam. Une scène ne pouvait donc rien
//! montrer d'autre — ni le jeu, ni une fenêtre, ni un autre écran. C'est le trou entre
//! « ça diffuse » et « je peux m'en servir » (Jay, 2026-08-05).
//!
//! Les sources appartiennent à une SCÈNE, contrairement à l'audio qui vit sur des canaux
//! globaux. C'est tout l'intérêt des scènes : montrer le jeu dans l'une, un écran d'attente
//! dans l'autre.

use anyhow::{Context, Result};
use hikari_protocol::{SourceKind, CaptureTarget, SourceOrder};
// `WindowInfo`/`WindowSearchMode` viennent de `libobs-window-helper`, mais on passe par la
// réexportation de `libobs-simple` : ajouter une dépendance directe la ferait dériver de la
// version que `libobs-simple` lie réellement.
use libobs_simple::sources::windows::{
    GameCaptureSourceBuilder, MonitorCaptureSourceBuilder, WindowCaptureSourceBuilder, WindowInfo,
    WindowSearchMode,
};
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::{ObsData, ObsDataSetters};
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemExtSceneTrait, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::sys as libobs;

/// Les fenêtres à proposer : celles qui portent un titre visible, comme OBS lui-même.
const WINDOW_SEARCH_MODE: WindowSearchMode =
    WindowSearchMode::ExcludeMinimized;

/// Tout ce que la machine peut capturer À CET INSTANT : jeux lancés, fenêtres ouvertes,
/// écrans branchés.
///
/// Relu à chaque demande, jamais mis en cache : un jeu lancé après l'ouverture du panneau
/// doit apparaître sans redémarrer quoi que ce soit. Un échec sur une famille rend une liste
/// vide pour elle plutôt que de faire tomber les deux autres — trois questions indépendantes.
pub fn list_capture_targets() -> (Vec<CaptureTarget>, Vec<CaptureTarget>, Vec<CaptureTarget>) {
    let games = GameCaptureSourceBuilder::get_windows(WINDOW_SEARCH_MODE)
        .map(|windows| {
            windows
                .into_iter()
                .map(|window| CaptureTarget {
                    label: window_label(&window),
                    id: window.obs_id,
                })
                .collect()
        })
        .unwrap_or_default();

    let windows = WindowCaptureSourceBuilder::get_windows(WINDOW_SEARCH_MODE)
        .map(|found| {
            found
                .into_iter()
                .map(|window| CaptureTarget {
                    label: window_label(&window.0),
                    id: window.0.obs_id,
                })
                .collect()
        })
        .unwrap_or_default();

    let monitors = MonitorCaptureSourceBuilder::get_monitors()
        .map(|found| {
            found
                .into_iter()
                .enumerate()
                .map(|(index, monitor)| CaptureTarget {
                    // Le nom système d'un écran ("\\.\DISPLAY1") ne dit rien à personne :
                    // on numérote pour l'affichage, on garde le nom pour libobs.
                    label: format!("Écran {}", index + 1),
                    id: monitor.0.name.clone(),
                })
                .collect()
        })
        .unwrap_or_default();

    (games, windows, monitors)
}

/// Ce que l'utilisateur lit pour reconnaître une fenêtre : son titre, ou à défaut le nom du
/// programme. Jamais l'identifiant libobs, illisible.
fn window_label(window: &WindowInfo) -> String {
    window
        .title
        .clone()
        .filter(|title| !title.trim().is_empty())
        .or_else(|| window.class.clone())
        .unwrap_or_else(|| window.obs_id.clone())
}

/// Construit une source de capture et la pose dans `scene`.
///
/// Les réglages sont écrits à la main plutôt que par les constructeurs de `libobs-simple` :
/// ceux-ci rendent un type DIFFÉRENT par famille de capture, ce qui empêcherait de ranger
/// toutes les sources d'une scène dans une même liste. Ici tout ressort en `ObsSourceRef`,
/// exactement comme la caméra et l'audio.
///
/// La méthode de capture est forcée à WGC (Windows Graphics Capture) : c'est la voie moderne,
/// et elle évite la contrainte de conscience du zoom écran que DXGI impose au processus.
pub fn add_capture_to_scene(
    context: &mut ObsContext,
    kind: SourceKind,
    target_id: &str,
    name: &str,
    scene_name: &str,
) -> Result<ObsSceneItemRef<ObsSourceRef>> {
    let runtime = context.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages source de capture")?;
    match kind {
        SourceKind::Game => {
            settings
                // "window" : viser CETTE application, jamais « n'importe quel plein écran »,
                // qui changerait de cible dès que l'utilisateur bascule ailleurs.
                .set_string("capture_mode", "window")
                .context("réglage mode de capture jeu")?
                .set_string("window", target_id)
                .context("réglage fenêtre du jeu")?
                .set_bool("capture_cursor", true)
                .context("réglage curseur")?;
        }
        SourceKind::Window => {
            settings
                .set_string("window", target_id)
                .context("réglage fenêtre")?
                .set_int("method", libobs::window_capture_method_METHOD_WGC as i64)
                .context("réglage méthode de capture fenêtre")?
                .set_bool("cursor", true)
                .context("réglage curseur")?;
        }
        SourceKind::Monitor => {
            settings
                .set_string("monitor_id", target_id)
                .context("réglage écran")?
                .set_int("method", libobs::display_capture_method_DISPLAY_METHOD_WGC as i64)
                .context("réglage méthode de capture écran")?
                .set_bool("capture_cursor", true)
                .context("réglage curseur")?;
        }
        SourceKind::Image => {
            settings
                .set_string(hikari_protocol::IMAGE_PATH_PROPERTY, target_id)
                .context("réglage chemin de l'image")?;
        }
        SourceKind::Video => {
            settings
                .set_string(hikari_protocol::VIDEO_PATH_PROPERTY, target_id)
                .context("réglage chemin de la vidéo")?
                // Sans ce drapeau, la source attend une adresse réseau et n'ouvre jamais le
                // fichier — le nom de la propriété ne suffit pas à le lui dire.
                .set_bool("is_local_file", true)
                .context("réglage fichier local")?
                // En boucle par défaut : un habillage vidéo qui s'arrête au bout de dix
                // secondes et laisse un cadre noir n'est jamais l'intention.
                .set_bool("looping", true)
                .context("réglage lecture en boucle")?;
        }
    }

    let source = ObsSourceRef::new(kind.libobs_id(), name, Some(settings.into()), None, runtime)
        .context("construction source de capture")?;
    let mut scene = context
        .get_scene(scene_name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene.add_source(source).context("ajout de la source à la scène")
}

/// Déplace `item` d'un cran devant ou derrière les autres sources de sa scène.
///
/// `libobs-wrapper` 9.0.4 n'expose pas l'ordre d'empilement (vérifié dans sa source), donc
/// on passe par l'appel brut sur le fil OBS, même contrat que les filtres et l'audio.
pub fn set_order(
    runtime: &libobs_wrapper::runtime::ObsRuntime,
    item: &ObsSceneItemRef<ObsSourceRef>,
    direction: SourceOrder,
) -> Result<()> {
    let movement = match direction {
        SourceOrder::Front => libobs::obs_order_movement_OBS_ORDER_MOVE_UP,
        SourceOrder::Back => libobs::obs_order_movement_OBS_ORDER_MOVE_DOWN,
    };
    let runtime = runtime.clone();
    let ptr = item.as_ptr().clone();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: sur le fil OBS, et le pointeur vient d'un pointeur intelligent vivant
            // (l'élément est encore dans la scène, nous en tenons une référence).
            libobs::obs_sceneitem_set_order(ptr.get_ptr(), movement);
        })
        .context("changement d'ordre de la source")
}

/// La taille native de la source portée par un élément de scène, avant toute mise à
/// l'échelle — nécessaire pour savoir où l'utilisateur clique.
///
/// Passe par la source de l'élément plutôt que par une référence rangée à côté : ça marche
/// pour TOUTE source, y compris celles dont on ne garde pas la poignée. Rend `(0, 0)` tant
/// que la source n'a pas produit sa première image ; l'appelant traite ça comme « rien à
/// attraper » plutôt que de deviner une taille.
pub fn item_base_size(
    runtime: &libobs_wrapper::runtime::ObsRuntime,
    item: &ObsSceneItemRef<ObsSourceRef>,
) -> Result<(u32, u32)> {
    let runtime = runtime.clone();
    let ptr = item.as_ptr().clone();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: sur le fil OBS, pointeur intelligent vivant. `obs_sceneitem_get_source`
            // rend une référence empruntée, jamais à libérer ici.
            let source = libobs::obs_sceneitem_get_source(ptr.get_ptr());
            if source.is_null() {
                return (0, 0);
            }
            (libobs::obs_source_get_width(source), libobs::obs_source_get_height(source))
        })
        .context("lecture de la taille d'une source")
}

/// La position d'un élément dans la pile de sa scène — plus le nombre est grand, plus il est
/// devant. Sert à savoir QUELLE source un clic désigne quand plusieurs se recouvrent.
pub fn order_position(
    runtime: &libobs_wrapper::runtime::ObsRuntime,
    item: &ObsSceneItemRef<ObsSourceRef>,
) -> Result<i32> {
    let runtime = runtime.clone();
    let ptr = item.as_ptr().clone();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: sur le fil OBS, pointeur intelligent vivant.
            libobs::obs_sceneitem_get_order_position(ptr.get_ptr())
        })
        .context("lecture de la position d'une source")
}

/// Retire `item` de `scene_name` — le vrai détachement, pas seulement l'oubli de notre
/// poignée. La scène garde son propre exemplaire (`libobs-wrapper` 9.0.4), donc laisser
/// tomber notre référence ne suffirait pas : c'est la cause racine des doublons « Webcam 2 »
/// trouvée le 2026-07-24.
pub fn remove_from_scene(
    context: &mut ObsContext,
    scene_name: &str,
    item: ObsSceneItemRef<ObsSourceRef>,
) -> Result<()> {
    let mut scene = context
        .get_scene(scene_name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene.remove_scene_item(item).context("retrait de la source de la scène")
}
