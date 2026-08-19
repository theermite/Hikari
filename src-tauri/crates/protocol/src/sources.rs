//! What a scene can hold: capture kinds (monitor, window, game, image, video, camera),
//! their libobs identifiers, and the source-name validation shared by both sides.

use serde::{Deserialize, Serialize};

/// The libobs source-kind identifier for a monitor (screen) capture — shared vocabulary
/// so a deck can render the right icon without guessing.
pub const MONITOR_CAPTURE_KIND: &str = "monitor_capture";

/// The libobs source-kind identifier for a webcam (DirectShow) source — same id the real
/// win-dshow OBS plugin registers, never invented (B-cam).
pub const CAMERA_KIND: &str = "dshow_input";

/// The fixed name the engine gives its webcam source — ONE camera source total, reused by
/// every scene that shows it (Jay, 2026-07-24: « la caméra est unique »).
///
/// Lives HERE rather than in the engine because both sides of the wire need it: the app
/// falls back to this name to replace a camera saved before the name was recorded, and the
/// engine answers to it. The engine binary links libobs and therefore runs no tests
/// (`test = false`), so a constant kept there could never be pinned by one.
pub const CAMERA_SOURCE_NAME: &str = "Webcam";

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

/// The libobs source-kind identifier for a game / fullscreen-application capture — the id
/// the real win-capture plugin registers (verified 2026-08-05 in `libobs-simple` 8.0.1,
/// which mirrors obs-studio's own).
pub const GAME_CAPTURE_KIND: &str = "game_capture";

/// The libobs source-kind identifier for a single-window capture. Same verification.
pub const WINDOW_CAPTURE_KIND: &str = "window_capture";

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
}

/// Validates a candidate source name against the sources ALREADY IN THAT SCENE.
///
/// Same two rules as a scene name, and the same reason to enforce them early: libobs
/// silently renames a duplicate ("Webcam 2"), after which the panel no longer finds the
/// source it thinks it is naming.
pub fn validate_source_name(name: &str, existing: &[String]) -> Result<(), crate::scenes::SceneNameError> {
    crate::scenes::validate_scene_name(name, existing)
}
