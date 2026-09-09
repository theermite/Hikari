//! Camera source (B-cam tranche 1) — a webcam as a scene source, the same mechanism OBS
//! itself uses (`dshow_input`). Property key confirmed from the real win-dshow plugin
//! source (`VIDEO_DEVICE_ID`), never guessed. Adding the source into a LIVE, rendered
//! scene is separate debt (needs the continuous engine process, not yet launched by the
//! app — see PET B1 "Dette restante"); this module covers detection only.

use anyhow::{Context, Result};
use hikari_protocol::CameraDevice;
use libobs_simple::define_object_manager;
use libobs_wrapper::context::ObsContext;
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::properties::types::ObsListItemValue;
use libobs_wrapper::data::properties::{ObsProperty, ObsPropertyObject};
use libobs_wrapper::data::{ObsData, ObsDataPointers, ObsDataSetters};
use libobs_wrapper::graphics::Vec2;
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemExtSceneTrait, SceneItemTrait};
use libobs_wrapper::sources::{ObsFilterRef, ObsSourceBuilder, ObsSourceRef, ObsSourceTrait};
// `libobs-wrapper` re-exports the raw sys crate as `sys`; the macro below expands a
// literal `libobs::obs_source` path, so it needs a local alias named `libobs` rather than
// a second, independently-resolved `libobs` dependency (which could drift from the exact
// version `libobs-wrapper` itself links against).
use libobs_wrapper::sys as libobs;

define_object_manager!(
    #[derive(Debug)]
    /// A webcam / capture-card source (Windows DirectShow) — the same source OBS itself
    /// registers as `dshow_input`.
    struct DshowInputSource("dshow_input", *mut libobs::obs_source) for ObsSourceRef {
        /// Encoded device identifier (`"name:path"`) — the exact value libobs reports in
        /// the `video_device_id` property list, never hand-built.
        #[obs_property(type_t = "string")]
        video_device_id: String,
    }
);

// `libobs-simple`'s own `impl_default_builder!` helper is crate-private (not exported) —
// this is its exact body, transcribed (verified against `libobs-simple` 8.0.1 source,
// `src/sources/macro_helper.rs`), not invented.
impl ObsSourceBuilder for DshowInputSourceBuilder {
    type T = ObsSourceRef;

    fn build(self) -> Result<Self::T, libobs_wrapper::utils::ObsError> {
        use libobs_wrapper::data::ObsObjectBuilder;
        let runtime = self.runtime.clone();
        ObsSourceRef::new_from_info(self.object_build()?, runtime)
    }
}

/// Probes the real camera devices libobs sees on this machine: builds a throwaway
/// `dshow_input` source (never added to any scene, never kept), reads its
/// `video_device_id` list property, and turns it into the plain wire type. Never a
/// hardcoded/presumed device list (F-003's spirit applied to cameras).
pub fn probe_camera_devices(context: &ObsContext) -> Result<Vec<CameraDevice>> {
    let probe = context
        .source_builder::<DshowInputSourceBuilder, _>("hikari-camera-probe")
        .context("préparation sonde caméra")?
        .build()
        .context("sonde caméra dshow_input")?;
    let properties = probe
        .get_properties()
        .context("liste des propriétés dshow_input")?;

    let Some(ObsProperty::List(list)) = properties.get("video_device_id") else {
        return Ok(Vec::new());
    };
    Ok(list
        .items()
        .iter()
        .filter_map(|item| match item.value() {
            ObsListItemValue::String(device_id) => Some(CameraDevice {
                name: item.name().clone(),
                device_id: device_id.clone(),
            }),
            _ => None,
        })
        .collect())
}

/// The naming rule for camera sources, and the historic fallback name.
///
/// Défini dans `hikari-protocol` : l'app s'en sert aussi (repli du rejeu de session), et ce
/// binaire ne tourne aucun test, donc une constante gardée ici ne serait épinglée par aucun.
/// Ré-exporté pour que le code caméra garde son propre vocabulaire.
pub use hikari_protocol::{camera_source_name, CAMERA_SOURCE_NAME};

/// Builds the `dshow_input` source for `device_id` under `source_name` — called ONCE per
/// DEVICE, the first time that device is added to any scene. Does not add it to a scene
/// (see `add_existing_camera_to_scene`, used for this first placement and every later
/// scene that reuses the same source).
///
/// `source_name` must already be unique among the open cameras
/// (`hikari_protocol::camera_source_name`): libobs keys its sources by name, so two
/// cameras sharing one name are one source — the exact defect this replaces.
pub fn build_camera_source(
    context: &mut ObsContext,
    source_name: &str,
    device_id: &str,
) -> Result<ObsSourceRef> {
    context
        .source_builder::<DshowInputSourceBuilder, _>(source_name)
        .context("préparation source caméra")?
        .set_video_device_id(device_id)
        .build()
        .context("construction source caméra")
}

/// Relance l'appareil derrière une source caméra, sans la retirer de ses scènes.
///
/// CE QUE ÇA RÈGLE (Jay, 2026-09-07, pendant un direct de 1 h 51) : « ma caméra s'est
/// arrêtée de fonctionner, elle a figé ; j'ai dû la supprimer de la scène et la remettre ».
/// Une caméra USB décroche — bande passante, veille du pilote, câble bousculé — et l'image
/// reste figée sur sa dernière prise. Rien ne la remet en marche.
///
/// Retirer puis remettre marchait, mais ce geste coûte cher EN DIRECT : la source perd son
/// cadrage, ses filtres et sa place dans la pile, et il faut tout refaire pendant que les
/// spectateurs regardent. Relancer garde tout.
///
/// COMMENT : réécrire ses réglages à l'identique. `libobs` referme et rouvre l'appareil
/// quand on lui redonne son identifiant — c'est le même chemin que suit OBS quand
/// l'utilisateur rouvre les propriétés d'une caméra et valide sans rien changer.
///
/// `libobs-wrapper` 9.0.4 n'expose pas la mise à jour d'une source (vérifié dans sa
/// source), donc l'appel est brut, sur le fil OBS — même contrat que les filtres, l'audio
/// et l'ordre d'empilement.
pub fn restart_camera(
    context: &mut ObsContext,
    source: &ObsSourceRef,
    device_id: &str,
) -> Result<()> {
    let runtime = context.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages relance caméra")?;
    settings
        // Le nom EXACT de la propriété, celui que la liste des appareils expose. Une
        // faute ici serait muette : libobs accepte n'importe quelle clé et ignore celles
        // qu'il ne connaît pas.
        .set_string("video_device_id", device_id)
        .context("identifiant appareil pour la relance")?;
    let source_ptr = source.as_ptr();
    let settings_ptr = settings.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: les deux pointeurs viennent de valeurs VIVANTES dont nous tenons une
            // référence, et nous sommes sur le fil OBS — même argument que les autres
            // appels bruts de ce dépôt.
            libobs::obs_source_update(source_ptr.get_ptr(), settings_ptr.get_ptr());
        })
        .context("relance de la caméra")
}

/// Adds the ALREADY-BUILT camera `source` to `scene_name` as a new scene item — reuses the
/// source already open for that device (never builds a second `dshow_input` on the SAME
/// device, which would reopen it and risk the driver rejecting a 2nd concurrent capture).
/// Several scenes can hold their own scene item pointing at one source, each with its own
/// position and scale.
pub fn add_existing_camera_to_scene(
    context: &mut ObsContext,
    source: ObsSourceRef,
    scene_name: &str,
) -> Result<ObsSceneItemRef<ObsSourceRef>> {
    let mut scene = context
        .get_scene(scene_name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene.add_source(source).context("ajout caméra à la scène")
}

/// Moves the camera by `(dx, dy)` scene pixels from its current position (B7), clamped by
/// `hikari_protocol::clamp_camera_position`. Returns the real, post-clamp transform (never
/// the requested delta) so the caller reports what actually happened.
pub fn nudge_camera(
    item: &ObsSceneItemRef<ObsSourceRef>,
    dx: i32,
    dy: i32,
) -> Result<(i32, i32, i32)> {
    let current = item
        .get_source_position()
        .context("lecture position caméra")?;
    let (x, y) =
        hikari_protocol::clamp_camera_position(*current.x() as i32 + dx, *current.y() as i32 + dy);
    item.set_source_position(Vec2::new(x as f32, y as f32))
        .context("déplacement caméra")?;
    let scale = item.get_source_scale().context("lecture échelle caméra")?;
    Ok((x, y, (scale.x() * 100.0).round() as i32))
}

/// Sets the camera's position outright (B7, glisser-souris), clamped by
/// `hikari_protocol::clamp_camera_position`. Distinct from `nudge_camera`, which adds a
/// delta: a drag already knows the absolute point the cursor is on, and re-reading the
/// current position each mouse-move would accumulate rounding drift over a long gesture.
/// Same "return the real, post-clamp transform" contract as its two siblings.
pub fn set_camera_position(
    item: &ObsSceneItemRef<ObsSourceRef>,
    x: i32,
    y: i32,
) -> Result<(i32, i32, i32)> {
    let (x, y) = hikari_protocol::clamp_camera_position(x, y);
    item.set_source_position(Vec2::new(x as f32, y as f32))
        .context("déplacement caméra")?;
    let scale = item.get_source_scale().context("lecture échelle caméra")?;
    Ok((x, y, (scale.x() * 100.0).round() as i32))
}

/// Sets position AND scale in one go (B7, redimensionnement à la souris) — the two must
/// move together, or the camera would visibly jump between the two writes as the anchor
/// corner drifted for a frame. `scale` is applied on both axes (aspect kept); the caller
/// clamps it before calling.
pub fn set_camera_transform(
    item: &ObsSceneItemRef<ObsSourceRef>,
    x: i32,
    y: i32,
    scale: f32,
) -> Result<(i32, i32, i32)> {
    let (x, y) = hikari_protocol::clamp_camera_position(x, y);
    item.set_source_scale(Vec2::new(scale, scale))
        .context("mise à l'échelle caméra")?;
    item.set_source_position(Vec2::new(x as f32, y as f32))
        .context("déplacement caméra")?;
    Ok((x, y, (scale * 100.0).round() as i32))
}

/// Remplacée par `sources::item_base_size`, qui lit la taille depuis l'ÉLÉMENT de scène et
/// marche donc pour toute source, pas seulement celle dont on garde la poignée
/// (généralisation du geste souris, 2026-08-05). Conservée : elle reste la voie directe
/// quand on tient déjà la source, et le pré-vol pourra en avoir besoin.
#[allow(dead_code)]
/// The camera source's own pixel size, before any scene scaling — the webcam's native
/// resolution as libobs reports it.
///
/// `libobs-wrapper` 9.0.4 wraps no size getter (checked in its source, 2026-08-04), so this
/// dispatches the raw `obs_source_get_width`/`_height` on the OBS thread, the same
/// `run_with_obs_result` contract `set_filter_enabled` already uses. Returns `(0, 0)` while
/// the device is still opening — the caller treats that as "nothing to grab" rather than
/// guessing a size.
pub fn source_base_size(source: &ObsSourceRef) -> Result<(u32, u32)> {
    let runtime = source.runtime().clone();
    let ptr = source.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: same argument as `set_filter_enabled` — the pointer comes from a live
            // smart pointer we still hold a reference to, and we are on the OBS thread.
            (
                libobs::obs_source_get_width(ptr.get_ptr()),
                libobs::obs_source_get_height(ptr.get_ptr()),
            )
        })
        .context("lecture taille source caméra")
}

/// The live output canvas size (B7, glisser-souris) — the coordinate space every scene item
/// position is expressed in, needed to turn a cursor position into a camera position.
///
/// Read from libobs itself via `obs_get_video_info` rather than assumed from the startup
/// settings: the two can differ (a downscale is applied at output), and a wrong canvas size
/// makes the camera trail the cursor at the wrong speed.
pub fn canvas_size(runtime: &libobs_wrapper::runtime::ObsRuntime) -> Result<(u32, u32)> {
    // Only the two numbers cross the thread boundary, never `obs_video_info` itself: it
    // carries raw pointers (`graphics_module`), so it is not `Send` and the compiler refuses
    // to move it out of the OBS thread — correctly, since those pointers belong there.
    let size = runtime
        .run_with_obs_result(|| unsafe {
            let mut ovi: libobs::obs_video_info = std::mem::zeroed();
            // Safety: `obs_get_video_info` only writes into the struct we own, and we are on
            // the OBS thread. A `false` return means video is not initialized yet.
            if libobs::obs_get_video_info(&mut ovi) {
                Some((ovi.base_width, ovi.base_height))
            } else {
                None
            }
        })
        .context("lecture réglages vidéo")?;
    size.context("vidéo libobs non initialisée")
}

/// Grows (`grow = true`) or shrinks the camera by one fixed step (B7), clamped by
/// `hikari_protocol::clamp_camera_scale`. Same "return the real result" contract as
/// `nudge_camera`.
pub fn scale_camera(item: &ObsSceneItemRef<ObsSourceRef>, grow: bool) -> Result<(i32, i32, i32)> {
    let position = item
        .get_source_position()
        .context("lecture position caméra")?;
    let current_scale = item.get_source_scale().context("lecture échelle caméra")?;
    let factor = if grow {
        1.0 + hikari_protocol::CAMERA_SCALE_STEP
    } else {
        1.0 / (1.0 + hikari_protocol::CAMERA_SCALE_STEP)
    };
    let new_scale = hikari_protocol::clamp_camera_scale(current_scale.x() * factor);
    item.set_source_scale(Vec2::new(new_scale, new_scale))
        .context("mise à l'échelle caméra")?;
    Ok((
        *position.x() as i32,
        *position.y() as i32,
        (new_scale * 100.0).round() as i32,
    ))
}

/// Detaches `item` from `scene_name` — the real removal, not merely dropping our own
/// `ObsSceneItemRef` handle. `add_source`'s own doc says it plainly: "you can safely drop
/// these items, they are stored within the scene if you don't need them" — the scene keeps
/// its OWN clone in `attached_scene_items` (`libobs-wrapper` 9.0.4 source,
/// `scenes/scene_item/traits.rs`), so our field going out of scope never lowered the
/// refcount to zero. Root cause of the "duplicate name Webcam N" warnings found 2026-07-24.
pub fn remove_camera_from_scene(
    context: &mut ObsContext,
    scene_name: &str,
    item: ObsSceneItemRef<ObsSourceRef>,
) -> Result<()> {
    let mut scene = context
        .get_scene(scene_name)
        .context("recherche scène")?
        .context("scène introuvable")?;
    scene
        .remove_scene_item(item)
        .context("retrait caméra de la scène")
}

/// Creates the real NVIDIA background-removal filter (`nv_greenscreen_filter`) on `source`
/// and attaches it DISABLED — id and its `"mode"` property confirmed from the real
/// obs-studio nv-filters plugin source (github.com/obsproject/obs-studio,
/// `plugins/nv-filters/nvidia-videofx-filter.c`, verified 2026-07-23), never guessed.
/// `nv-filters.dll` is confirmed loaded on this machine (startup log: "[NVIDIA VIDEO FX]:
/// enabled, redistributable found"). Created ONCE per camera source, then toggled with
/// `set_filter_enabled` (Jay, 2026-07-24 : "un filtre est activé ou non", the real OBS
/// per-filter enable switch — `obs_source_set_enabled` — never a rebuild).
pub fn create_background_removal_filter(source: &ObsSourceRef) -> Result<ObsFilterRef> {
    let runtime = source.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages fond IA")?;
    settings
        .set_int("mode", 0)
        .context("réglage mode fond IA")?; // S_MODE_QUALITY
    let filter = ObsFilterRef::new(
        "nv_greenscreen_filter",
        "Fond IA",
        Some(settings.into()),
        None,
        runtime,
    )
    .context("création filtre fond IA")?;
    source
        .apply_filter(&filter)
        .context("attache filtre fond IA")?;
    set_filter_enabled(&filter, false).context("désactivation initiale filtre fond IA")?;
    Ok(filter)
}

/// Creates the mask filter (`mask_filter`, image-based — OBS has no built-in geometric
/// shape, verified via the real `mask-filter.c` source) on `source`, attached DISABLED, with
/// NO image yet — [`set_mask_shape`] supplies one the first time a real shape is asked for,
/// once the camera's true proportions are known (see its own doc: a guessed square here
/// would reproduce the exact ellipse defect this module now avoids). Created ONCE per
/// camera, then reconfigured in place — never recreated when the user changes shape or
/// radius (même contrat que `create_background_removal_filter`).
pub fn create_mask_filter(source: &ObsSourceRef) -> Result<ObsFilterRef> {
    let runtime = source.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages masque")?;
    settings
        .set_string("type", "mask_alpha_filter.effect")
        .context("réglage type masque")?
        // The mask image is generated at the camera's OWN aspect ratio (2026-09-09), so
        // stretching it onto the video frame is a uniform scale, never a distortion — the
        // opposite of the fixed 1:1 square this used to ship (a circle stretched onto a
        // 16:9 camera became an ellipse, exactly what Jay saw and flagged).
        .set_bool("stretch", true)
        .context("réglage étirement masque")?;
    let filter = ObsFilterRef::new(
        "mask_filter",
        "Masque",
        Some(settings.into()),
        None,
        runtime,
    )
    .context("création filtre masque")?;
    source
        .apply_filter(&filter)
        .context("attache filtre masque")?;
    set_filter_enabled(&filter, false).context("désactivation initiale filtre masque")?;
    Ok(filter)
}

/// Reconfigure un filtre de masque déjà attaché pour porter `shape` — jamais une recréation.
///
/// `Aucun` désactive le filtre : la vidéo reprend sa forme native, exactement comme avant
/// que ce système n'existe. Toute autre forme lit la taille RÉELLE de `source` (jamais un
/// carré supposé — la déformation en ellipse que Jay a vue le 2026-09-09) et pointe
/// `image_path` vers un fichier calculé à cette proportion, mis en cache par forme + taille
/// (voir [`circle_mask_path`], [`rounded_mask_path`]).
pub fn set_mask_shape(
    filter: &ObsFilterRef,
    source: &ObsSourceRef,
    shape: hikari_protocol::MaskShape,
) -> Result<()> {
    if matches!(shape, hikari_protocol::MaskShape::None) {
        return set_filter_enabled(filter, false).context("désactivation du masque");
    }
    let runtime = filter.runtime().clone();
    let (width, height) = crate::sources::source_base_size(&runtime, source)
        .context("taille de la caméra pour le masque")?;
    anyhow::ensure!(
        width > 0 && height > 0,
        "la caméra n'a pas encore produit d'image — le masque se posera au prochain réglage"
    );
    let path = match shape {
        hikari_protocol::MaskShape::None => unreachable!("écarté ci-dessus"),
        hikari_protocol::MaskShape::Circle => {
            circle_mask_path(width, height).context("génération masque cercle")?
        }
        hikari_protocol::MaskShape::Rounded { radius_percent } => {
            rounded_mask_path(radius_percent, width, height)
                .context("génération masque coins arrondis")?
        }
    };
    let mut settings = ObsData::new(runtime).context("réglages masque")?;
    settings
        .set_string("image_path", path.to_string_lossy().to_string())
        .context("réglage image masque")?;
    filter
        .update_settings(settings)
        .context("mise à jour de l'image du masque")?;
    set_filter_enabled(filter, true).context("activation du masque")
}

/// Toggles a camera filter on/off in place. The implementation moved to
/// `filters::set_enabled` on 2026-08-04, when the audio mixer needed the exact same
/// operation — nothing about it was ever camera-specific. Re-exported under its old name so
/// the camera code keeps reading in its own vocabulary.
pub use crate::filters::set_enabled as set_filter_enabled;

/// Plafond du plus grand côté d'un masque calculé, en pixels — la caméra peut filmer en
/// 4K, mais le masque n'a besoin de rien de plus fin que ça pour rester net une fois étiré :
/// mesuré le 2026-09-09, générer à 1024 pleine résolution coûtait jusqu'à 1,7 s (bloquant le
/// seul fil du moteur — le « en attente du moteur » que Jay a subi), contre ~70 ms à cette
/// taille avec le même encodage.
const MASK_MAX_DIMENSION: u32 = 512;

/// Les dimensions RÉELLES du masque à générer pour un cadre `width`×`height` — mêmes
/// proportions, réduites pour ne jamais dépasser [`MASK_MAX_DIMENSION`] sur le plus grand
/// côté. Jamais un carré : c'est exactement l'ancien défaut.
fn scaled_mask_size(width: u32, height: u32) -> (u32, u32) {
    let longest = width.max(height).max(1);
    if longest <= MASK_MAX_DIMENSION {
        return (width.max(1), height.max(1));
    }
    let scale = MASK_MAX_DIMENSION as f32 / longest as f32;
    (
        ((width as f32 * scale).round() as u32).max(1),
        ((height as f32 * scale).round() as u32).max(1),
    )
}

/// Écrit `pixels` (RGBA8, `mask_w`×`mask_h`) au format PNG, sans filtrage adaptatif par
/// ligne ni compression forte — les deux ensemble faisaient l'essentiel du coût mesuré (voir
/// [`MASK_MAX_DIMENSION`]) pour un fichier qui ne sert qu'en local, jamais transmis : sa
/// taille sur disque n'a aucune importance, sa vitesse d'écriture si.
fn write_mask_png(path: &std::path::Path, pixels: &[u8], mask_w: u32, mask_h: u32) -> Result<()> {
    use image::codecs::png::{CompressionType, FilterType, PngEncoder};
    use image::{ExtendedColorType, ImageEncoder};

    let file = std::fs::File::create(path).context("création du fichier de masque")?;
    let encoder = PngEncoder::new_with_quality(file, CompressionType::Fast, FilterType::NoFilter);
    encoder
        .write_image(pixels, mask_w, mask_h, ExtendedColorType::Rgba8)
        .context("encodage du masque")
}

/// Le chemin de l'image de masque circulaire pour un cadre `width`×`height`.
///
/// Générée une fois par couple de dimensions (le nom de fichier les porte), puis relue à
/// chaque appel suivant — la résolution native d'une caméra ne change qu'en changeant
/// d'appareil, donc ce cache ne grossit jamais sans raison. Écrite dans le dossier temporaire
/// du système, comme le masque à coins arrondis : ni l'un ni l'autre n'a besoin d'être
/// embarqué par l'installeur, ils se recréent seuls.
fn circle_mask_path(width: u32, height: u32) -> Result<std::path::PathBuf> {
    let (mask_w, mask_h) = scaled_mask_size(width, height);
    let path = std::env::temp_dir().join(format!("hikari-mask-circle-{mask_w}x{mask_h}.png"));
    if path.exists() {
        return Ok(path);
    }
    let pixels = hikari_protocol::generate_circle_mask_rgba(mask_w, mask_h);
    write_mask_png(&path, &pixels, mask_w, mask_h)?;
    Ok(path)
}

/// Le chemin de l'image de masque à coins arrondis pour CE rayon, sur un cadre
/// `width`×`height` — mêmes règles de cache que [`circle_mask_path`], plus le rayon dans le
/// nom de fichier.
fn rounded_mask_path(radius_percent: i32, width: u32, height: u32) -> Result<std::path::PathBuf> {
    let radius_percent = hikari_protocol::clamp_mask_radius(radius_percent);
    let (mask_w, mask_h) = scaled_mask_size(width, height);
    let path = std::env::temp_dir().join(format!(
        "hikari-mask-rounded-{radius_percent}-{mask_w}x{mask_h}.png"
    ));
    if path.exists() {
        return Ok(path);
    }
    let pixels = hikari_protocol::generate_rounded_mask_rgba(radius_percent, mask_w, mask_h);
    write_mask_png(&path, &pixels, mask_w, mask_h)?;
    Ok(path)
}
