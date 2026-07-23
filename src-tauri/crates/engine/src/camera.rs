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
use libobs_wrapper::data::{ObsData, ObsDataSetters};
use libobs_wrapper::scenes::ObsSceneItemRef;
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
    let properties = probe.get_properties().context("liste des propriétés dshow_input")?;

    let Some(ObsProperty::List(list)) = properties.get("video_device_id") else {
        return Ok(Vec::new());
    };
    Ok(list
        .items()
        .iter()
        .filter_map(|item| match item.value() {
            ObsListItemValue::String(device_id) => {
                Some(CameraDevice { name: item.name().clone(), device_id: device_id.clone() })
            }
            _ => None,
        })
        .collect())
}

/// The fixed name given to the webcam source added to the "main" scene — one camera at a
/// time by convention (see `main.rs`'s `camera_device_id` doc for what this simplifies).
pub const CAMERA_SOURCE_NAME: &str = "Webcam";

/// Builds the `dshow_input` source for `device_id` and adds it to `scene` under
/// `CAMERA_SOURCE_NAME`. Shared by the first `AddCamera` and by `rebuild_camera`'s
/// toggle-via-rebuild sequence (see `main.rs`) — one place that knows how a camera scene
/// item gets created.
pub fn add_camera_to_scene(
    context: &mut ObsContext,
    device_id: &str,
) -> Result<ObsSceneItemRef<ObsSourceRef>> {
    let mut scene = context
        .get_scene("main")
        .context("recherche scène 'main'")?
        .context("scène 'main' introuvable")?;
    context
        .source_builder::<DshowInputSourceBuilder, _>(CAMERA_SOURCE_NAME)
        .context("préparation source caméra")?
        .set_video_device_id(device_id)
        .add_to_scene(&mut scene)
        .context("ajout caméra à la scène")
}

/// Applies the real NVIDIA background-removal filter (`nv_greenscreen_filter`) to
/// `source` — id and its `"mode"` property confirmed from the real obs-studio nv-filters
/// plugin source (github.com/obsproject/obs-studio, `plugins/nv-filters/nvidia-videofx-filter.c`,
/// verified 2026-07-23), never guessed. `nv-filters.dll` is confirmed loaded on this
/// machine (startup log: "[NVIDIA VIDEO FX]: enabled, redistributable found").
///
/// One-way: `libobs-wrapper` 9.0.4 tracks an applied filter's removal guard on the
/// SOURCE's own internal list, with no public API to detach it before the source itself
/// is dropped (verified in `ObsSourceRef::apply_filter`'s source) — there is no
/// `remove_background_removal` counterpart yet.
pub fn apply_background_removal(source: &ObsSourceRef) -> Result<()> {
    let runtime = source.runtime().clone();
    let mut settings = ObsData::new(runtime.clone()).context("réglages fond IA")?;
    settings.set_int("mode", 0).context("réglage mode fond IA")?; // S_MODE_QUALITY
    let filter = ObsFilterRef::new("nv_greenscreen_filter", "Fond IA", Some(settings.into()), None, runtime)
        .context("création filtre fond IA")?;
    source.apply_filter(&filter).context("application filtre fond IA")?;
    Ok(())
}

/// Applies a circular alpha mask (`mask_filter`, image-based — OBS has no built-in
/// geometric circle shape, verified via the real `mask-filter.c` source) to `source`,
/// using the circle PNG shipped next to the engine binary. Same one-way limitation as
/// `apply_background_removal`.
pub fn apply_circle_mask(source: &ObsSourceRef) -> Result<()> {
    let runtime = source.runtime().clone();
    let mask_path = circle_mask_path().context("chemin masque cercle")?;
    let mut settings = ObsData::new(runtime.clone()).context("réglages masque cercle")?;
    settings
        .set_string("type", "mask_alpha_filter.effect")
        .context("réglage type masque")?
        .set_string("image_path", mask_path.to_string_lossy().to_string())
        .context("réglage image masque")?
        // The mask asset is a fixed 1:1 square; the camera's own resolution rarely is.
        // Without stretching, `mask_filter` centers the square at its native size inside
        // the wider/taller video frame, leaving the video's edges outside that square
        // fully unmasked (the vertical strips Jay saw either side of the circle).
        .set_bool("stretch", true)
        .context("réglage étirement masque")?;
    let filter = ObsFilterRef::new("mask_filter", "Masque cercle", Some(settings.into()), None, runtime)
        .context("création filtre masque")?;
    source.apply_filter(&filter).context("application filtre masque")?;
    Ok(())
}

/// Absolute path to the circle mask asset, resolved next to the engine's own binary —
/// same colocation pattern as the OBS runtime files it already needs alongside it
/// (packaging for a release bundle is separate debt, not yet relevant pre-installer).
fn circle_mask_path() -> Result<std::path::PathBuf> {
    let exe = std::env::current_exe().context("résolution du chemin de l'exécutable")?;
    let dir = exe.parent().context("résolution du dossier de l'exécutable")?;
    Ok(dir.join("assets").join("circle-mask.png"))
}
