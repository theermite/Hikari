//! What a scene can hold: capture kinds (monitor, window, game, image, video, camera),
//! their libobs identifiers, and the source-name validation shared by both sides.

use serde::{Deserialize, Serialize};

use crate::platform::{
    CAMERA_KIND, GAME_CAPTURE_KIND, MONITOR_CAPTURE_KIND, WINDOW_CAPTURE_KIND,
};

/// The historic name of the single webcam source, kept as a FALLBACK (2026-09-06).
///
/// Until then Hikari opened exactly one camera and always called it this (Jay, 2026-07-24:
/// « la caméra est unique »). Cameras are now named after the device the user picked, but
/// this value still has two jobs: replaying a session saved before the name was recorded,
/// and naming a device that reports no usable name of its own.
///
/// Lives HERE rather than in the engine because both sides of the wire need it. The engine
/// binary links libobs and therefore runs no tests (`test = false`), so a constant kept
/// there could never be pinned by one.
pub const CAMERA_SOURCE_NAME: &str = "Webcam";

/// The libobs source name to give a camera for `device_name`, unique among `taken`.
///
/// libobs keys its sources BY NAME. Two cameras sharing one name are one source, which is
/// precisely the defect this replaces: every device resolved to `"Webcam"`, so picking a
/// second one silently returned the first. Two identical webcams also report the identical
/// device label, so uniqueness cannot come from the device alone — it is decided here,
/// against the names already in use.
pub fn camera_source_name(device_name: &str, taken: &[String]) -> String {
    let trimmed = device_name.trim();
    let base = if trimmed.is_empty() { CAMERA_SOURCE_NAME } else { trimmed };
    if !taken.iter().any(|name| name == base) {
        return base.to_string();
    }
    let mut n = 2usize;
    loop {
        let candidate = format!("{base} ({n})");
        if !taken.iter().any(|name| name == &candidate) {
            return candidate;
        }
        n += 1;
    }
}

/// One source inside a scene (e.g. a monitor capture). `kind` names the libobs source
/// family so a deck can render an icon without guessing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceInfo {
    pub name: String,
    pub kind: String,
}

impl SourceInfo {
    /// Describe a monitor (screen) capture source. Pure: no libobs, so the engine's
    /// source-listing logic is unit-testable without the OBS runtime.
    pub fn monitor_capture(name: impl Into<String>) -> Self {
        Self { name: name.into(), kind: MONITOR_CAPTURE_KIND.to_string() }
    }

    /// Describe a webcam (DirectShow) source. Pure, same reason as `monitor_capture`.
    pub fn camera(name: impl Into<String>) -> Self {
        Self { name: name.into(), kind: CAMERA_KIND.to_string() }
    }
}

/// One camera (DirectShow) device libobs reports as available on this machine — `device_id`
/// is the exact encoded value (`"name:path"`) the `dshow_input` source's `video_device_id`
/// property expects, never hand-built (B-cam, real win-dshow plugin behavior).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CameraDevice {
    pub name: String,
    pub device_id: String,
}

/// What a capture source points at (brique Sources).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    /// A game or fullscreen application — the fast path, hooks the app directly.
    Game,
    /// One window, whatever it is. Works where the game hook cannot.
    Window,
    /// A whole screen.
    Monitor,
    /// A still image on disk — logo, overlay, waiting screen.
    Image,
    /// A video file on disk, played in a loop.
    Video,
    /// The webcam. Recreated by its OWN command (`AddCamera`) because it is ONE physical
    /// source shared across scenes — never by `AddCaptureSource`, which would open the
    /// device a second time.
    Camera,
}

impl SourceKind {
    /// The libobs source id to build. A wrong id yields a source libobs silently refuses.
    pub fn libobs_id(self) -> &'static str {
        match self {
            SourceKind::Game => GAME_CAPTURE_KIND,
            SourceKind::Window => WINDOW_CAPTURE_KIND,
            SourceKind::Monitor => MONITOR_CAPTURE_KIND,
            SourceKind::Image => IMAGE_SOURCE_KIND,
            SourceKind::Video => VIDEO_SOURCE_KIND,
            SourceKind::Camera => CAMERA_KIND,
        }
    }

    /// Whether this kind designates a FILE on disk rather than something to capture live.
    /// The panel asks for a file instead of listing targets.
    pub fn is_file(self) -> bool {
        matches!(self, SourceKind::Image | SourceKind::Video)
    }
}

/// The libobs source-kind identifier for a still image — the real obs-studio image-source
/// plugin id (verified 2026-08-05 against its source).
pub const IMAGE_SOURCE_KIND: &str = "image_source";
/// The property carrying the image's path.
pub const IMAGE_PATH_PROPERTY: &str = "file";

/// The libobs source-kind identifier for a media file. Same verification, obs-ffmpeg plugin.
pub const VIDEO_SOURCE_KIND: &str = "ffmpeg_source";
/// The property carrying the video's path. Different from the image's — a shared name would
/// have been convenient and is simply not what OBS uses.
pub const VIDEO_PATH_PROPERTY: &str = "local_file";

/// One thing the user can capture: a game, a window, or a screen. `id` is the exact value
/// libobs expects in the source's own setting, never rebuilt by hand; `label` is what the
/// user reads.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CaptureTarget {
    pub id: String,
    pub label: String,
}

/// Which way a source moves in the stack of a scene (brique Sources).
///
/// Said in what the user sees — in front of or behind the others — never in list-index
/// terms, which nobody can picture.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceOrder {
    /// Closer to the viewer: drawn over the others.
    Front,
    /// Further away: drawn under the others.
    Back,
}

/// One source inside a scene, as the engine really holds it.
///
/// Carries everything needed to RECREATE it identically at the next launch — kind, what it
/// points at, and where it sits. Anything missing here is a setting the user would have to
/// redo by hand, so the completeness of this struct IS the persistence guarantee.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SceneSourceInfo {
    pub name: String,
    /// The libobs source-kind id, so a panel can show the right icon without guessing.
    pub kind: String,
    /// Which family it belongs to — what a rebuild needs, the libobs id alone being a
    /// display detail.
    pub source_kind: SourceKind,
    /// What it captures: a window id, a monitor id, or a file path.
    pub target_id: String,
    /// Where it sits in the canvas, and how big — the placement the user chose with the
    /// mouse, worth exactly as much as the source itself.
    pub x: i32,
    pub y: i32,
    pub scale_percent: i32,
    /// Locked against the mouse IN THIS SCENE — a placement the user considers settled.
    ///
    /// Per scene, not per source: the same webcam is framed once and for all in a talking
    /// scene while it still moves freely in a gameplay scene. The lock is enforced where the
    /// gesture is resolved (the click hit test ignores it), never by hiding a button — a
    /// source that can still be grabbed is not locked, whatever the panel shows.
    #[serde(default)]
    pub locked: bool,
    /// For a CAMERA source: this scene's OWN desired state for the NVIDIA
    /// background-removal filter — the value applied to that camera's filter whenever this
    /// scene becomes live, never the filter's current global state.
    ///
    /// Per camera AND per scene since 2026-09-06 (several cameras can share a scene, each
    /// with its own look). Always `false` on a non-camera source. `serde(default)` because
    /// a session saved before that date has no such field, and a missing field must replay
    /// as "filter off" rather than refuse the whole scene.
    #[serde(default)]
    pub background_removal: bool,
    /// Same contract as `background_removal`, for the circular mask filter.
    #[serde(default)]
    pub circle_mask: bool,
    /// Montrée à l'écran, ou cachée sans être retirée. Cachée, la source garde son
    /// cadrage, ses filtres et sa place dans la pile — c'est ce qui distingue le geste du
    /// direct (masquer le temps d'une manipulation) de la décision de retirer.
    ///
    /// Par défaut VRAIE, et pas simplement « la valeur par défaut du type ». Une session
    /// enregistrée avant ce champ ne le porte pas : la lire avec `false` cacherait toutes
    /// les sources de l'utilisateur au premier lancement de la version qui l'ajoute.
    #[serde(default = "shown")]
    pub visible: bool,
}

/// La valeur d'une source dont personne n'a jamais dit si elle était montrée : elle l'est.
fn shown() -> bool {
    true
}

/// Validates a candidate source name against the sources ALREADY IN THAT SCENE.
///
/// Same two rules as a scene name, and the same reason to enforce them early: libobs
/// silently renames a duplicate ("Webcam 2"), after which the panel no longer finds the
/// source it thinks it is naming.
pub fn validate_source_name(name: &str, existing: &[String]) -> Result<(), crate::scenes::SceneNameError> {
    crate::scenes::validate_scene_name(name, existing)
}
