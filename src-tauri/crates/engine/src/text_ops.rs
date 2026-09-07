//! L'apparence d'une source texte : police, taille, couleur, contour, alignement.
//!
//! POURQUOI ce module existe (Jay, 2026-09-07) : « une source de texte sans réglage, sans
//! personnalisation, je trouve ça très inutile ». Le greffon `text_gdiplus` porte tous ces
//! réglages depuis toujours ; rien ne les atteignait. On ne code donc RIEN de neuf côté
//! rendu — on branche ce que le moteur sait déjà faire.
//!
//! POURQUOI un appel brut pour la police : `libobs-wrapper` 9.0.4 ne sait poser que des
//! chaînes, des entiers et des booléens (vérifié dans sa source). Or la police est un OBJET
//! imbriqué — `face`, `size`, `flags` vivent dans un sous-ensemble nommé `font`. Le pont ne
//! l'expose pas, donc l'objet est construit par appel direct, sur le fil OBS, exactement
//! comme l'ordre des sources et les filtres.

use anyhow::{Context, Result};
use hikari_protocol::{
    TEXT_ALIGN_PROPERTY, TEXT_COLOR_PROPERTY, TEXT_CONTENT_PROPERTY, TEXT_FONT_FACE,
    TEXT_FONT_FLAGS, TEXT_FONT_PROPERTY, TEXT_FONT_SIZE, TEXT_OUTLINE_COLOR_PROPERTY,
    TEXT_OUTLINE_PROPERTY, TEXT_OUTLINE_SIZE_PROPERTY, TextSettings, libobs_color,
};
use libobs_wrapper::runtime::ObsRuntime;
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::sys as libobs;
use std::ffi::CString;

/// Applique `settings` à la source portée par `item`.
///
/// Prend l'élément de scène et non un nom : c'est l'appelant qui sait déjà où il est, et le
/// rechercher une seconde fois ouvrirait un chemin où les deux pourraient diverger — même
/// contrat que `sources::set_visible`.
pub fn apply(
    runtime: &ObsRuntime,
    item: &ObsSceneItemRef<ObsSourceRef>,
    settings: &TextSettings,
) -> Result<()> {
    let runtime = runtime.clone();
    let item_ptr = item.as_ptr().clone();

    // Tout est posé en UN SEUL passage sur le fil OBS. Deux passages laisseraient un instant
    // où la police a changé mais pas sa couleur — visible en direct, et sans raison.
    let face = CString::new(settings.face.as_str()).context("nom de police illisible")?;
    let align = CString::new(settings.align.libobs_value()).context("alignement illisible")?;
    let cle_font = CString::new(TEXT_FONT_PROPERTY)?;
    let cle_face = CString::new(TEXT_FONT_FACE)?;
    let cle_size = CString::new(TEXT_FONT_SIZE)?;
    let cle_flags = CString::new(TEXT_FONT_FLAGS)?;
    let cle_color = CString::new(TEXT_COLOR_PROPERTY)?;
    let cle_outline = CString::new(TEXT_OUTLINE_PROPERTY)?;
    let cle_outline_size = CString::new(TEXT_OUTLINE_SIZE_PROPERTY)?;
    let cle_outline_color = CString::new(TEXT_OUTLINE_COLOR_PROPERTY)?;
    let cle_align = CString::new(TEXT_ALIGN_PROPERTY)?;

    let taille = settings.size;
    let drapeaux = settings.font_flags();
    let couleur = libobs_color(settings.color);
    let contour = settings.outline;
    let contour_taille = settings.outline_size;
    let contour_couleur = libobs_color(settings.outline_color);

    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: le pointeur vient d'un `SmartPointerSendable` vivant (la source est
            // toujours dans la scène et nous en tenons une référence), et nous sommes sur le
            // fil OBS — même argument que `filters::set_enabled`.
            let reglages = libobs::obs_data_create();
            let police = libobs::obs_data_create();

            libobs::obs_data_set_string(police, cle_face.as_ptr(), face.as_ptr());
            libobs::obs_data_set_int(police, cle_size.as_ptr(), taille);
            libobs::obs_data_set_int(police, cle_flags.as_ptr(), drapeaux);
            libobs::obs_data_set_obj(reglages, cle_font.as_ptr(), police);
            // L'objet police est retenu par `set_obj` : on relâche NOTRE référence, sinon
            // elle fuit à chaque changement de réglage.
            libobs::obs_data_release(police);

            libobs::obs_data_set_int(reglages, cle_color.as_ptr(), couleur);
            libobs::obs_data_set_bool(reglages, cle_outline.as_ptr(), contour);
            libobs::obs_data_set_int(reglages, cle_outline_size.as_ptr(), contour_taille);
            libobs::obs_data_set_int(reglages, cle_outline_color.as_ptr(), contour_couleur);
            libobs::obs_data_set_string(reglages, cle_align.as_ptr(), align.as_ptr());

            // `update` FUSIONNE : les réglages qu'on ne nomme pas gardent leur valeur. Le
            // texte lui-même n'est donc pas touché — il n'a rien à faire dans ce module.
            let source = libobs::obs_sceneitem_get_source(item_ptr.get_ptr());
            libobs::obs_source_update(source, reglages);
            libobs::obs_data_release(reglages);
        })
        .context("application des réglages de texte")
}

/// Change le CONTENU d'une source texte déjà posée — jamais sa police, sa couleur ou son
/// contour, qui vivent dans `apply` ci-dessus.
///
/// Refuse un texte vide plutôt que de le poser : ce serait un rectangle invisible que
/// l'utilisateur chercherait dans sa scène sans jamais le voir — même garde qu'à la
/// création de la source (voir `sources.rs`, `SourceKind::Text`).
pub fn set_content(
    runtime: &ObsRuntime,
    item: &ObsSceneItemRef<ObsSourceRef>,
    text: &str,
) -> Result<()> {
    anyhow::ensure!(!text.trim().is_empty(), "un texte vide ne se voit pas");

    let runtime = runtime.clone();
    let item_ptr = item.as_ptr().clone();
    let valeur = CString::new(text).context("texte illisible")?;
    let cle = CString::new(TEXT_CONTENT_PROPERTY)?;

    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: même argument que `apply` — pointeur vivant, fil OBS.
            let reglages = libobs::obs_data_create();
            libobs::obs_data_set_string(reglages, cle.as_ptr(), valeur.as_ptr());
            let source = libobs::obs_sceneitem_get_source(item_ptr.get_ptr());
            libobs::obs_source_update(source, reglages);
            libobs::obs_data_release(reglages);
        })
        .context("écriture du contenu du texte")
}
