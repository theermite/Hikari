//! Le filtre de masque d'une caméra (forme + calcul de l'image) — extrait de `camera.rs` le
//! 2026-09-09, ce fichier ayant atteint le plafond BLOQUANT de 500 lignes une fois la
//! relecture indépendante d'avant publication appliquée. Pure séparation de fichier, aucun
//! changement de comportement au moment de l'extraction.

use anyhow::{Context, Result};
use libobs_wrapper::data::object::ObsObjectTrait;
use libobs_wrapper::data::{ObsData, ObsDataSetters};
use libobs_wrapper::sources::{ObsFilterRef, ObsSourceRef, ObsSourceTrait};

use crate::filters::set_enabled as set_filter_enabled;

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

/// Ce que [`set_mask_shape`] a réellement pu faire — distingue un vrai échec (fichier,
/// réglage OBS) d'une caméra simplement pas encore prête, pour que l'appelant sache s'il
/// doit réessayer plus tard plutôt que crier une erreur (2026-09-09, relecture indépendante
/// avant publication : un rejeu de session pose la caméra puis son masque dans la même
/// respiration, avant que le pilote n'ait rendu la moindre image — l'ancien masque, une
/// image fixe, ne dépendait d'aucune taille et ne connaissait pas ce cas).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MaskApplyOutcome {
    Applied,
    CameraNotReadyYet,
}

/// Reconfigure un filtre de masque déjà attaché pour porter `shape` — jamais une recréation.
///
/// `Aucun` désactive le filtre : la vidéo reprend sa forme native, exactement comme avant
/// que ce système n'existe. Toute autre forme lit la taille RÉELLE de `source` (jamais un
/// carré supposé — la déformation en ellipse que Jay a vue le 2026-09-09) et pointe
/// `image_path` vers un fichier calculé à cette proportion, mis en cache par forme + taille
/// (voir [`circle_mask_path`], [`rounded_mask_path`]). Rend
/// [`MaskApplyOutcome::CameraNotReadyYet`] plutôt qu'une erreur quand la taille n'est pas
/// encore connue — l'appelant décide alors de réessayer, jamais nous.
pub fn set_mask_shape(
    filter: &ObsFilterRef,
    source: &ObsSourceRef,
    shape: hikari_protocol::MaskShape,
) -> Result<MaskApplyOutcome> {
    if matches!(shape, hikari_protocol::MaskShape::None) {
        set_filter_enabled(filter, false).context("désactivation du masque")?;
        return Ok(MaskApplyOutcome::Applied);
    }
    let runtime = filter.runtime().clone();
    let (width, height) = crate::sources::source_base_size(&runtime, source)
        .context("taille de la caméra pour le masque")?;
    if width == 0 || height == 0 {
        return Ok(MaskApplyOutcome::CameraNotReadyYet);
    }
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
    set_filter_enabled(filter, true).context("activation du masque")?;
    Ok(MaskApplyOutcome::Applied)
}

/// La version du calcul qui produit un masque — PORTÉE dans le nom de chaque fichier mis en
/// cache (2026-09-09, relecture indépendante avant publication : sans elle, changer un jour
/// la formule de calcul laisserait les fichiers déjà sur le disque servir l'ancien dessin
/// indéfiniment, silencieusement — la clé du cache doit dépendre du calcul, pas seulement
/// de ce qu'il produit aujourd'hui). À incrémenter chaque fois que `generate_circle_mask_rgba`
/// ou `generate_rounded_mask_rgba` change de résultat pour les mêmes arguments.
const MASK_GENERATOR_VERSION: u32 = 1;

/// Écrit `pixels` (RGBA8, `mask_w`×`mask_h`) au format PNG, sans filtrage adaptatif par
/// ligne ni compression forte — les deux ensemble faisaient l'essentiel du coût mesuré (voir
/// `hikari_protocol::MASK_MAX_DIMENSION`) pour un fichier qui ne sert qu'en local, jamais transmis : sa
/// taille sur disque n'a aucune importance, sa vitesse d'écriture si.
///
/// Écrit d'abord sous un nom TEMPORAIRE puis renomme vers `path` (2026-09-09, relecture
/// indépendante avant publication) : un `rename` est atomique sur un même volume, donc un
/// moteur interrompu en plein encodage laisse au pire un fichier `.tmp` orphelin, jamais un
/// PNG tronqué à `path` — celui-là aurait été relu comme valide indéfiniment par
/// `path.exists()`, sans jamais se réparer tout seul.
fn write_mask_png(path: &std::path::Path, pixels: &[u8], mask_w: u32, mask_h: u32) -> Result<()> {
    use image::codecs::png::{CompressionType, FilterType, PngEncoder};
    use image::{ExtendedColorType, ImageEncoder};

    let tmp_path = path.with_extension("png.tmp");
    let file = std::fs::File::create(&tmp_path).context("création du fichier de masque")?;
    let encoder = PngEncoder::new_with_quality(file, CompressionType::Fast, FilterType::NoFilter);
    encoder
        .write_image(pixels, mask_w, mask_h, ExtendedColorType::Rgba8)
        .context("encodage du masque")?;
    std::fs::rename(&tmp_path, path).context("finalisation du fichier de masque")
}

/// Le chemin de l'image de masque circulaire pour un cadre `width`×`height`.
///
/// Générée une fois par couple de dimensions (le nom de fichier les porte, avec la version
/// du calcul — voir [`MASK_GENERATOR_VERSION`]), puis relue à chaque appel suivant — la
/// résolution native d'une caméra ne change qu'en changeant d'appareil, donc ce cache ne
/// grossit jamais sans raison. Écrite dans le dossier temporaire du système, comme le
/// masque à coins arrondis : ni l'un ni l'autre n'a besoin d'être embarqué par l'installeur,
/// ils se recréent seuls.
fn circle_mask_path(width: u32, height: u32) -> Result<std::path::PathBuf> {
    let (mask_w, mask_h) = hikari_protocol::scaled_mask_size(width, height);
    let path = std::env::temp_dir().join(format!(
        "hikari-mask-circle-v{MASK_GENERATOR_VERSION}-{mask_w}x{mask_h}.png"
    ));
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
    let (mask_w, mask_h) = hikari_protocol::scaled_mask_size(width, height);
    let path = std::env::temp_dir().join(format!(
        "hikari-mask-rounded-v{MASK_GENERATOR_VERSION}-{radius_percent}-{mask_w}x{mask_h}.png"
    ));
    if path.exists() {
        return Ok(path);
    }
    let pixels = hikari_protocol::generate_rounded_mask_rgba(radius_percent, mask_w, mask_h);
    write_mask_png(&path, &pixels, mask_w, mask_h)?;
    Ok(path)
}
