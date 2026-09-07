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
    /// Du texte écrit à l'écran — un titre, un pseudo, un message d'attente.
    ///
    /// Ni une capture ni un fichier : la CIBLE est le texte lui-même, tapé par
    /// l'utilisateur. C'est la seule famille dont le contenu ne vient pas de la
    /// machine, et c'est pour ça qu'elle ne demande ni liste ni sélecteur.
    Text,
}

impl SourceKind {
    /// The libobs source id to build. A wrong id yields a source libobs silently refuses.
    pub fn libobs_id(self) -> &'static str {
        match self {
            SourceKind::Game => GAME_CAPTURE_KIND,
            SourceKind::Window => WINDOW_CAPTURE_KIND,
            SourceKind::Monitor => MONITOR_CAPTURE_KIND,
            SourceKind::Text => TEXT_SOURCE_KIND,
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
/// L'identifiant du greffon de texte, LU DANS LE BINAIRE embarqué le 2026-09-07 —
/// jamais recopié d'une documentation.
///
/// Pourquoi cette précaution : les versions récentes d'OBS ont publié `text_gdiplus_v2`
/// puis `_v3`, et un identifiant inexistant ne provoque AUCUNE erreur — libobs rend
/// simplement une source nulle, et l'utilisateur voit un ajout qui ne fait rien. Le
/// greffon que nous embarquons n'expose que `text_gdiplus`, sans suffixe.
pub const TEXT_SOURCE_KIND: &str = "text_gdiplus";
/// La propriété qui porte le texte affiché, vérifiée dans le même binaire.
pub const TEXT_CONTENT_PROPERTY: &str = "text";

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

/// Les clés de réglage du greffon de texte, EXTRAITES DU BINAIRE embarqué le 2026-09-07
/// (`obs-text.dll`, OBS 32.0.4) — jamais recopiées d'une documentation.
///
/// Même précaution que pour l'identifiant du greffon, et pour la même raison : une clé
/// inexistante ne provoque AUCUNE erreur. libobs l'ignore, le réglage ne s'applique pas, et
/// l'utilisateur voit un curseur qui ne fait rien.
pub const TEXT_FONT_PROPERTY: &str = "font";
pub const TEXT_FONT_FACE: &str = "face";
pub const TEXT_FONT_SIZE: &str = "size";
pub const TEXT_FONT_FLAGS: &str = "flags";
pub const TEXT_COLOR_PROPERTY: &str = "color";
pub const TEXT_OUTLINE_PROPERTY: &str = "outline";
pub const TEXT_OUTLINE_SIZE_PROPERTY: &str = "outline_size";
pub const TEXT_OUTLINE_COLOR_PROPERTY: &str = "outline_color";
pub const TEXT_ALIGN_PROPERTY: &str = "align";

/// Les drapeaux de style d'une police libobs, valeurs de `obs_font_style` — additionnables.
const FONT_FLAG_BOLD: i64 = 1;
const FONT_FLAG_ITALIC: i64 = 2;

/// L'alignement horizontal, tel que le greffon l'attend : une chaîne, pas un nombre.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TextAlign {
    Left,
    Center,
    Right,
}

impl TextAlign {
    pub fn libobs_value(self) -> &'static str {
        match self {
            TextAlign::Left => "left",
            TextAlign::Center => "center",
            TextAlign::Right => "right",
        }
    }
}

/// Ce que l'utilisateur règle sur une source texte.
///
/// Volontairement PLUS PETIT que ce que le greffon expose : le dégradé, le mode journal de
/// chat et les dimensions forcées sont laissés de côté. Un panneau qui montre tout ne se
/// règle plus — et ces trois-là ne servent presque jamais à un direct.
///
/// Le CONTOUR est là bien que Jay ne l'ait pas demandé : c'est lui qui rend un texte lisible
/// sur n'importe quelle scène. Sans lui, un titre disparaît dès que le fond passe au clair.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TextSettings {
    pub face: String,
    pub size: i64,
    pub bold: bool,
    pub italic: bool,
    /// Couleur du texte, en composantes rouge/vert/bleu de 0 à 255.
    pub color: Rgb,
    pub outline: bool,
    pub outline_size: i64,
    pub outline_color: Rgb,
    pub align: TextAlign,
}

/// Une couleur telle que l'utilisateur la choisit — trois composantes, pas un entier.
///
/// POURQUOI ne pas transporter directement l'entier de libobs : son ORDRE D'OCTETS est une
/// convention interne au moteur. La garder d'un seul côté évite qu'une moitié du code pense
/// en rouge-vert-bleu pendant que l'autre pense l'inverse — le genre d'écart qui donne un
/// bleu là où l'utilisateur a cliqué sur du rouge.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl TextSettings {
    /// Les drapeaux de style à poser sur la police.
    pub fn font_flags(&self) -> i64 {
        let mut flags = 0;
        if self.bold {
            flags += FONT_FLAG_BOLD;
        }
        if self.italic {
            flags += FONT_FLAG_ITALIC;
        }
        flags
    }
}

/// La couleur au format que le greffon attend.
///
/// libobs range ses couleurs en BLEU-VERT-ROUGE et non l'inverse, avec l'opacité dans
/// l'octet de poids fort. ⚠️ Cet ordre est une convention du moteur que le binaire ne
/// documente pas : il se vérifie à l'écran au premier essai — un rouge qui sort bleu le dit
/// tout de suite, et se corrige en inversant deux lignes ici.
///
/// L'opacité est toujours pleine : le greffon porte son propre réglage `opacity`, et deux
/// façons de rendre un texte transparent en feraient une de trop.
pub fn libobs_color(color: Rgb) -> i64 {
    let (r, g, b) = (color.r as i64, color.g as i64, color.b as i64);
    0xff00_0000 | (b << 16) | (g << 8) | r
}

#[cfg(test)]
mod text_settings_tests {
    use super::*;

    fn rgb(r: u8, g: u8, b: u8) -> Rgb {
        Rgb { r, g, b }
    }

    #[test]
    fn should_put_the_red_component_in_the_low_byte() {
        // Rouge pur. Si l'ordre etait inverse, cette valeur porterait le rouge en haut et
        // l'utilisateur verrait du bleu — le defaut se voit a l'oeil, ce test le nomme.
        // Opacite pleine, bleu nul, vert nul, rouge plein — dans cet ordre d'octets.
        assert_eq!(libobs_color(rgb(255, 0, 0)), 0xff_00_00_ff);
    }

    #[test]
    fn should_keep_full_opacity_on_every_colour() {
        for couleur in [rgb(0, 0, 0), rgb(255, 255, 255), rgb(12, 34, 56)] {
            assert_eq!(libobs_color(couleur) >> 24 & 0xff, 0xff);
        }
    }

    #[test]
    fn should_round_trip_each_component_to_its_own_byte() {
        let valeur = libobs_color(rgb(0x12, 0x34, 0x56));
        assert_eq!(valeur & 0xff, 0x12, "rouge");
        assert_eq!(valeur >> 8 & 0xff, 0x34, "vert");
        assert_eq!(valeur >> 16 & 0xff, 0x56, "bleu");
    }

    #[test]
    fn should_add_style_flags_rather_than_replace_them() {
        let mut reglages = TextSettings {
            face: "Inter".into(),
            size: 48,
            bold: true,
            italic: true,
            color: rgb(255, 255, 255),
            outline: true,
            outline_size: 4,
            outline_color: rgb(0, 0, 0),
            align: TextAlign::Left,
        };
        // Gras ET italique valent la somme des deux, jamais l'un des deux.
        assert_eq!(reglages.font_flags(), FONT_FLAG_BOLD + FONT_FLAG_ITALIC);
        reglages.italic = false;
        assert_eq!(reglages.font_flags(), FONT_FLAG_BOLD);
        reglages.bold = false;
        assert_eq!(reglages.font_flags(), 0);
    }

    #[test]
    fn should_name_each_alignment_the_way_the_plugin_expects() {
        assert_eq!(TextAlign::Left.libobs_value(), "left");
        assert_eq!(TextAlign::Center.libobs_value(), "center");
        assert_eq!(TextAlign::Right.libobs_value(), "right");
    }
}
