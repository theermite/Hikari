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

/// The fixed name given to the physical webcam source — ONE camera source total (Jay,
/// 2026-07-24: "la caméra est unique"), reused across every scene it appears in, exactly
/// like OBS itself (a source added to several scenes is the same source, not a clone).
pub const CAMERA_SOURCE_NAME: &str = "Webcam";

/// Builds the `dshow_input` source for `device_id` — called ONCE, the first time a camera
/// is added to any scene. Does not add it to a scene itself (see `add_existing_camera_to_scene`,
/// used both for this first placement and every later scene that reuses the same source).
pub fn build_camera_source(context: &mut ObsContext, device_id: &str) -> Result<ObsSourceRef> {
    context
        .source_builder::<DshowInputSourceBuilder, _>(CAMERA_SOURCE_NAME)
        .context("préparation source caméra")?
        .set_video_device_id(device_id)
        .build()
        .context("construction source caméra")
}

/// Adds the ALREADY-BUILT camera `source` to `scene_name` as a new scene item — reuses the
/// one physical source (never builds a second `dshow_input`, which would reopen the device
/// and risk the driver rejecting a 2nd concurrent capture). Multiple scenes can hold their
/// own scene item pointing at this same source, each with its own position/scale.
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
pub fn nudge_camera(item: &ObsSceneItemRef<ObsSourceRef>, dx: i32, dy: i32) -> Result<(i32, i32, i32)> {
    let current = item.get_source_position().context("lecture position caméra")?;
    let (x, y) = hikari_protocol::clamp_camera_position(*current.x() as i32 + dx, *current.y() as i32 + dy);
    item.set_source_position(Vec2::new(x as f32, y as f32)).context("déplacement caméra")?;
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
    item.set_source_position(Vec2::new(x as f32, y as f32)).context("déplacement caméra")?;
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
    item.set_source_scale(Vec2::new(scale, scale)).context("mise à l'échelle caméra")?;
    item.set_source_position(Vec2::new(x as f32, y as f32)).context("déplacement caméra")?;
    Ok((x, y, (scale * 100.0).round() as i32))
}

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
    let position = item.get_source_position().context("lecture position caméra")?;
    let current_scale = item.get_source_scale().context("lecture échelle caméra")?;
    let factor = if grow { 1.0 + hikari_protocol::CAMERA_SCALE_STEP } else { 1.0 / (1.0 + hikari_protocol::CAMERA_SCALE_STEP) };
    let new_scale = hikari_protocol::clamp_camera_scale(current_scale.x() * factor);
    item.set_source_scale(Vec2::new(new_scale, new_scale)).context("mise à l'échelle caméra")?;
    Ok((*position.x() as i32, *position.y() as i32, (new_scale * 100.0).round() as i32))
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
    scene.remove_scene_item(item).context("retrait caméra de la scène")
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
    settings.set_int("mode", 0).context("réglage mode fond IA")?; // S_MODE_QUALITY
    let filter = ObsFilterRef::new("nv_greenscreen_filter", "Fond IA", Some(settings.into()), None, runtime)
        .context("création filtre fond IA")?;
    source.apply_filter(&filter).context("attache filtre fond IA")?;
    set_filter_enabled(&filter, false).context("désactivation initiale filtre fond IA")?;
    Ok(filter)
}

/// Creates a circular alpha mask filter (`mask_filter`, image-based — OBS has no built-in
/// geometric circle shape, verified via the real `mask-filter.c` source) on `source`,
/// using the circle PNG shipped next to the engine binary, attached DISABLED. Same
/// create-once-then-toggle contract as `create_background_removal_filter`.
pub fn create_circle_mask_filter(source: &ObsSourceRef) -> Result<ObsFilterRef> {
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
    source.apply_filter(&filter).context("attache filtre masque")?;
    set_filter_enabled(&filter, false).context("désactivation initiale filtre masque")?;
    Ok(filter)
}

/// Toggles `filter` on/off in place — the real per-filter switch OBS itself exposes (the
/// "eye" icon), `obs_source_set_enabled` on the filter's own source handle (a libobs filter
/// IS an `obs_source_t` internally). Confirmed present in the raw C bindings 2026-07-24
/// (`libobs-sys` 5.0.1, `obs_source_set_enabled`) — `libobs-wrapper` doesn't wrap it yet, so
/// this dispatches the raw call on the OBS thread via the source's own runtime, the same
/// thread-safety contract every safe wrapper method uses internally (`run_with_obs!`).
/// Replaces the rebuild-the-whole-camera approach from 2026-07-23 (visible reinit blip) —
/// no rebuild, no blip, instant.
pub fn set_filter_enabled(filter: &ObsFilterRef, enabled: bool) -> Result<()> {
    let runtime = filter.runtime().clone();
    let ptr = filter.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: `ptr` is valid because it comes from a live `SmartPointerSendable`
            // (the filter is still attached, we hold a reference to it) — same safety
            // argument the wrapper's own `apply_filter`/`obs_source_filter_add` calls make.
            libobs::obs_source_set_enabled(ptr.get_ptr(), enabled);
        })
        .context("activation/désactivation filtre")
}

/// Absolute path to the circle mask asset, resolved next to the engine's own binary —
/// same colocation pattern as the OBS runtime files it already needs alongside it
/// (packaging for a release bundle is separate debt, not yet relevant pre-installer).
fn circle_mask_path() -> Result<std::path::PathBuf> {
    let exe = std::env::current_exe().context("résolution du chemin de l'exécutable")?;
    let dir = exe.parent().context("résolution du dossier de l'exécutable")?;
    Ok(dir.join("assets").join("circle-mask.png"))
}
