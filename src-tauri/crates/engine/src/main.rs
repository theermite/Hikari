//! Hikari — engine process (ADR-013). Loads `libobs` in ITS OWN process (the controller
//! launches it by path, never links it) and reports over the JSON-line wire protocol
//! (`hikari-protocol`, ADR-011).
//!
//! B1a: initialize libobs, build a scene with a screen (monitor) capture, emit the scene's
//! sources. B1b: create a native preview window (`obs_display`), announce its HWND
//! (`PreviewReady`), stay alive so the controller can graft that window into the Tauri app
//! (cross-process `SetParent`, proven at the `spikes/b1b-preview` spike). B2a (this file,
//! extended): real RTMP streaming on `StartStream`/`StopStream`, target read from the
//! engine's OWN environment (never over the wire — OAuth/vault target is B2b).
//!
//! API transcribed from the proven spikes (B0.0 for the scene/sources/streaming, B1b for
//! the preview window + wire announcement). This is the integrated port, not throwaway code.
//!
//! Split by domain (2026-08-20, file over the 500-line ceiling): [`lifecycle_ops`] (startup,
//! stream/multistream) · [`scene_ops`] (create/switch/delete scene) · [`camera_ops`] (the
//! physical webcam) · [`source_ops`] (captures in a scene) · [`audio_ops`] (the mixer) ·
//! [`drag_ops`] (mouse placement, B7) · [`event_loop`] (the winit `ApplicationHandler`) ·
//! [`stdin_reader`] (parses `ControllerCommand` lines) · [`bootstrap`] (`run()` + the two
//! one-shot detection modes). Every `impl App` block below is one MORE inherent impl of the
//! same type — Rust merges them at compile time, so nothing here changed behaviour.

mod audio;
mod audio_ops;
mod bootstrap;
mod camera;
mod camera_ops;
mod camera_slide_ops;
mod drag_ops;
mod event_loop;
mod events;
mod filters;
mod lifecycle_ops;
mod mask;
mod mask_retry_ops;
mod multistream;
mod outline;
mod scene_ops;
mod scenes;
mod source_ops;
mod sources;
mod stdin_reader;
mod stream;
mod text_ops;
mod transitions;

// Ré-exporté pour que chaque module continue d'écrire `crate::EngineEvent`, sans savoir
// dans quel fichier l'énumération vit réellement.
pub(crate) use events::EngineEvent;

use std::io::Write;

use anyhow::Result;
use hikari_protocol::{ControllerCommand, EngineMessage};
use libobs_wrapper::display::ObsDisplayRef;
use libobs_wrapper::scenes::ObsSceneItemRef;
use libobs_wrapper::sources::ObsSourceRef;
use libobs_wrapper::unsafe_send::Sendable;
use multistream::PlatformStream;
use stream::StreamState;
use winit::window::Window;

/// The display name given to the scene's screen-capture source.
const MONITOR_CAPTURE_NAME: &str = "Monitor Capture";
/// Preview window's own resolution before it is grafted (the controller resizes it to
/// fit the app once grafted — this is just a sane starting size).
const PREVIEW_START_WIDTH: u32 = 960;
const PREVIEW_START_HEIGHT: u32 = 540;
const TARGET_ASPECT: f32 = 16.0 / 9.0;
/// How often the mixer's level bars are refreshed (B6). Fast enough that a bar tracks the
/// voice rather than lagging behind it, slow enough not to flood the pipe — the frame
/// counters' two-second beat would make the bars lurch, hence a separate cadence.
const AUDIO_LEVEL_INTERVAL: std::time::Duration = std::time::Duration::from_millis(50);
/// How often an in-progress camera glide is advanced (B7, option A) — a 60fps step, fast
/// enough that the motion reads as continuous rather than a series of jumps.
const CAMERA_SLIDE_TICK: std::time::Duration = std::time::Duration::from_millis(16);
/// How often a mask waiting on a not-yet-ready camera is retried (2026-09-09, relecture
/// indépendante avant publication). Ni un rendu par image (une caméra qui démarre met des
/// dizaines de millisecondes, pas une image, à produire sa première trame) ni un délai qui
/// se voit — quatre tentatives par seconde suffisent largement à rattraper l'instant où le
/// pilote commence enfin à rendre.
const MASK_RETRY_TICK: std::time::Duration = std::time::Duration::from_millis(250);
/// Plafond d'ÂGE avant d'abandonner un masque en attente et de le dire à l'utilisateur
/// (2026-09-09, relecture indépendante avant publication, TROISIÈME passage — un compteur de
/// tentatives ACTIVES, posé au second passage, ne progressait jamais pour une entrée dont la
/// scène ne redevenait jamais active : l'attente ne se terminait donc jamais. L'âge, lui,
/// avance quoi qu'il arrive — voir `hikari_protocol::decide_mask_retry`). 10 s, largement
/// au-delà du temps de démarrage normal d'une caméra.
const MASK_RETRY_MAX_AGE: std::time::Duration = std::time::Duration::from_secs(10);

/// Emit one protocol message as a single JSON line on stdout. A serialization failure is
/// reported on stderr rather than swallowed (it must never crash the engine). `pub(crate)`
/// so every domain module can report the same way.
pub(crate) fn emit(msg: &EngineMessage) {
    match hikari_protocol::to_line(msg) {
        // `println!` PANIQUE quand le tuyau est ferme, et c'est arrive : l'application
        // fermee, le moteur ecrivait encore et mourait sur « The pipe is being closed »
        // (vecu par Jay, 2026-09-07). Un plantage est le pire des arrets — il ne libere
        // rien proprement, et il salit le journal d'une trace qui ressemble a un bug.
        //
        // L'ecriture manuelle rend l'erreur au lieu de paniquer. Un tuyau ferme n'est pas
        // une panne : c'est la fin normale, et le lecteur d'entree la traite deja en
        // arretant le moteur.
        Ok(line) => {
            let mut sortie = std::io::stdout().lock();
            if writeln!(sortie, "{line}").is_ok() {
                let _ = sortie.flush();
            }
        }
        Err(err) => eprintln!("[engine] failed to serialize {msg:?}: {err}"),
    }
}

/// La composition retenue au démarrage : ce que le moteur DESSINE.
///
/// Lue à deux moments éloignés — au démarrage pour construire l'image, puis à chaque
/// diffusion pour en déduire le débit. Les deux DOIVENT s'accorder : une image composée en
/// 1080 et un débit calculé pour du 720 produisent exactement le défaut qu'on corrige.
pub(crate) fn composition() -> hikari_protocol::Composition {
    // Personne n'a mesuré : on compose comme sur un écran modeste. Ce chemin ne devrait
    // jamais servir — il existe pour que l'absence de mesure produise un réglage PRUDENT
    // plutôt qu'un plantage.
    *COMPOSITION.get_or_init(|| hikari_protocol::composition(1280, 720))
}

/// Retient la composition de cette machine. Appelée UNE fois, au démarrage, depuis
/// l'endroit qui connaît la taille de l'écran.
pub(crate) fn set_composition(screen_width: u32, screen_height: u32) {
    let choisi = hikari_protocol::composition(screen_width, screen_height);
    eprintln!(
        "[engine] composition choisie : {}x{} a {} i/s (ecran {screen_width}x{screen_height})",
        choisi.width, choisi.height, choisi.fps
    );
    let _ = COMPOSITION.set(choisi);
}

static COMPOSITION: std::sync::OnceLock<hikari_protocol::Composition> = std::sync::OnceLock::new();

/// Keeps the 16:9 aspect ratio when the controller resizes the grafted window (cross-process
/// `MoveWindow`, proven at the spike). Pure aspect-fit math, transcribed unchanged.
pub(crate) fn fit_size(win_w: u32, win_h: u32) -> (u32, u32) {
    // Clamp BOTH dimensions before any arithmetic — see the sibling `fit_size` in
    // `preview_bridge.rs` (a test there caught a 0×0 defect from clamping only the ratio
    // comparison, not the branch arithmetic).
    let win_w = win_w.max(1);
    let win_h = win_h.max(1);
    if win_w as f32 / win_h as f32 > TARGET_ASPECT {
        ((((win_h as f32) * TARGET_ASPECT) as u32).max(1), win_h)
    } else {
        (win_w, (((win_w as f32) / TARGET_ASPECT) as u32).max(1))
    }
}

/// The state that must be dropped in this exact order: the display FIRST, then the OBS
/// context. Field declaration order IS drop order in Rust — this used to be reversed
/// (`context` declared before `display`), which freed the context while the display still
/// held references, causing an extra libobs memory leak (2 instead of the 1 documented,
/// upstream-known leak). Found + fixed after the spike (dette noted in its README).
struct ObsInner {
    display: ObsDisplayRef,
    context: libobs_wrapper::context::ObsContext,
    /// The one fade transition Hikari keeps on the output channel for the app's whole life
    /// (B7) — created once at `try_init`, never rebuilt per switch. Every `SwitchScene`
    /// fades THROUGH it (`transitions::start_transition`) instead of a scene ever touching
    /// the output channel directly.
    transition: ObsSourceRef,
    /// The real, currently-composed scene sources — grown by `handle_add_camera`. Kept
    /// here (never re-derived from libobs) so every `Sources` emission reflects the whole
    /// scene, never just the last-added delta.
    sources: Vec<hikari_protocol::SourceInfo>,
    /// Every camera currently open, keyed by its device identifier (2026-09-06).
    ///
    /// One libobs source per PHYSICAL DEVICE, created the first time that device is asked
    /// for and reused (never rebuilt) by every later scene. Before this, a single
    /// `camera_source` held whichever device had been opened first, so choosing a second
    /// camera silently returned the first — no error, just the wrong picture.
    cameras: std::collections::HashMap<String, OpenCamera>,
    /// Which (scene, device) pairs are on screen, and their own scene item. Position and
    /// scale are per pair: one device can sit differently in each scene that shows it.
    camera_items: std::collections::HashMap<(String, String), CameraItem>,
    /// Each (scene, device) pair's OWN desired filter state (fond IA, forme de masque) —
    /// applied to that camera's filters only when the scene is live on the output channel
    /// (`SwitchScene`), the "scene automation toggles my filters" flow Jay uses in OBS.
    scene_filter_state:
        std::collections::HashMap<(String, String), (bool, hikari_protocol::MaskShape)>,
    /// Les (scène, appareil) dont le masque VOULU n'a pas pu être posé parce que la caméra
    /// n'avait pas encore produit sa première image (2026-09-09, relecture indépendante
    /// avant publication — régression trouvée avant de publier : au rejeu d'une session,
    /// `AddCamera` est immédiatement suivi de `SetMaskShape`, avant que le pilote n'ait
    /// rendu quoi que ce soit ; l'ancien masque, une image fixe, ne dépendait d'aucune
    /// taille et ne connaissait pas ce problème). Retenté à chaque tick tant que la paire
    /// reste ici — voir `retry_pending_masks`. La valeur porte l'INSTANT de mise en attente
    /// (jamais un compteur de tentatives — troisième passage de relecture, voir
    /// `MASK_RETRY_MAX_AGE` et `hikari_protocol::decide_mask_retry`) ET le dernier
    /// échantillon de taille lu (septième passage — une caméra relancée peut annoncer une
    /// taille non nulle mais PÉRIMÉE tant qu'aucune image de la nouvelle configuration n'est
    /// arrivée ; deux lectures identiques de suite sont exigées, voir
    /// `hikari_protocol::confirm_camera_size`).
    mask_retry_pending:
        std::collections::HashMap<(String, String), crate::mask_retry_ops::MaskWait>,
    /// The scene currently live on the output channel (multi-scene, tranche 1) — libobs
    /// exposes no "which scene is on this channel" getter, so this is the one piece of
    /// state the engine must track itself rather than read back.
    active_scene: String,
    /// Every source of the ACTIVE scene with its rectangle, FRONT-FIRST — cached (B7).
    ///
    /// WHY front-first: a click designates the source the user actually sees, so the hit
    /// test walks the stack from the top down and stops at the first match.
    ///
    /// WHY a cache: the cursor shape is decided on EVERY mouse move, and measuring one
    /// source costs four round-trips to the OBS thread (position, scale, size, stack
    /// order). Doing that per source per move made the preview stutter. The cache is exact
    /// rather than approximate because nothing but this engine moves these sources — every
    /// writer clears it through `scene_layout_changed`.
    item_rects: Option<Vec<ItemRect>>,
    /// La carte du dernier geste quand elle était INCOMPLÈTE — une source venait d'être
    /// posée et ne produisait pas encore d'image, donc elle mesurait 0×0. Elle sert à ce
    /// geste-ci et sera remesurée au suivant : la retenir dans `item_rects` rendrait cette
    /// source inattrapable jusqu'à ce qu'un autre geste vide le cache (Jay, 2026-09-06).
    pending_item_rects: Vec<ItemRect>,
    /// The mixer (B6) — audio sources in insertion order, so a source keeps its channel and
    /// its place in the panel for its whole life.
    audio: Vec<MixerSource>,
    /// What each scene holds (brique Sources), in the order the user added it. Keyed by
    /// scene name. Cameras live in `camera_items` instead — a camera source is shared
    /// across the scenes that show it, a rule this generic list would break.
    scene_sources: std::collections::HashMap<String, Vec<SceneSource>>,
    /// The `(scene, source name)` pairs locked against the mouse (brique Sources).
    ///
    /// Keyed by the PAIR rather than stored on `SceneSource`, so a camera obeys the same
    /// lock without being pulled into that list — a camera source is shared across the
    /// scenes showing it, and its lock is per scene like its placement. Absent = free.
    locked: std::collections::HashSet<(String, String)>,
    /// Les sources CACHÉES, par paire (scène, nom). L'ensemble retient l'exception, jamais
    /// la règle : une source dont personne n'a rien dit est montrée, et une scène neuve
    /// n'a donc rien à écrire ici.
    hidden: std::collections::HashSet<(String, String)>,
}

/// Where one source of the active scene sits, in canvas pixels.
struct ItemRect {
    name: String,
    x: f32,
    y: f32,
    width: f32,
    height: f32,
}

/// One capture the user put into a scene.
struct SceneSource {
    name: String,
    /// The libobs source-kind id, kept so the panel can show what it is without asking.
    kind: String,
    /// Sa famille et ce qu'elle capture — gardés pour que l'app puisse la RECRÉER au
    /// lancement suivant. Sans eux, une session sauvegardée ne serait pas rejouable.
    source_kind: hikari_protocol::SourceKind,
    target_id: String,
    item: ObsSceneItemRef<ObsSourceRef>,
}

/// One libobs capture behind a mixer entry, with everything the engine must free later.
struct LiveCapture {
    source: ObsSourceRef,
    /// The libobs output channel it occupies. Kept explicitly so removing it frees the right
    /// channel — recomputing it from list order would free the wrong one once any earlier
    /// capture has been removed.
    channel: u32,
    /// The room-noise suppression filter, created alongside the capture when the kind
    /// supports it, then toggled in place. `None` on desktop sound, which has no room noise.
    noise_filter: Option<libobs_wrapper::sources::ObsFilterRef>,
}

/// One entry in the mixer — what the user sees as a single device.
///
/// It can be backed by TWO libobs captures of the same device. WHY: libobs has ONE volume
/// per source, applied to both the stream and the headphones, so a single capture cannot
/// have an audience volume and a headphone volume at once (OBS has the same limit). When the
/// user asks for "both hear it", the engine opens a second capture routed to the headphones
/// only — each capture then carries its own volume. Decision Jay, 2026-08-05: the second
/// capture costs CPU, and a few devices refuse to be opened twice; that is accepted, because
/// the alternative is the multi-tool assembly Hikari exists to remove.
struct MixerSource {
    name: String,
    kind: hikari_protocol::AudioSourceKind,
    /// The capture the AUDIENCE hears. Absent when only the streamer listens.
    public: Option<LiveCapture>,
    /// The capture the STREAMER hears. Absent when only the audience listens.
    monitor: Option<LiveCapture>,
    /// The live level meter, attached to whichever capture exists. `None` when libobs
    /// refused — a missing bar costs a display, never the sound.
    meter: Option<audio::LevelMeter>,
    /// Slider positions, remembered so unmuting restores exactly what the user chose.
    volume_percent: i32,
    monitor_volume_percent: i32,
    muted: bool,
    monitoring: hikari_protocol::AudioMonitoring,
    noise_suppression: bool,
    noise_method: hikari_protocol::NoiseMethod,
    noise_level_db: f32,
    /// The device this entry captures, kept so a second capture can be opened later without
    /// asking the panel again.
    device_id: String,
}

impl MixerSource {
    /// Every capture currently open behind this entry.
    fn captures(&self) -> impl Iterator<Item = &LiveCapture> {
        self.public.iter().chain(self.monitor.iter())
    }
}

/// An in-progress camera gesture (B7, souris) — a move or a resize, decided at press time
/// by where the cursor was.
enum DragState {
    /// Moving. `grab_offset` is where inside the source the user grabbed it, in canvas
    /// pixels. Keeping that offset is what makes the source follow the cursor instead of
    /// jumping so its corner snaps under the pointer on the first move.
    Move {
        name: String,
        grab_offset_x: f32,
        grab_offset_y: f32,
    },
    /// Resizing from a corner. `anchor` is the OPPOSITE corner, in canvas pixels — it stays
    /// pinned for the whole gesture, so the source grows away from a fixed point instead of
    /// sliding while it resizes. Read once at press time: re-deriving it from the live
    /// rectangle each move would chase its own changes.
    Resize {
        name: String,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    },
}

/// The filters a camera source carries once created — kept together since they're always
/// created alongside their camera. `mask` porte n'importe quelle forme (Aucun/Cercle/Coins
/// arrondis, `hikari_protocol::MaskShape`) — reconfiguré en place, jamais recréé.
struct CameraFilters {
    background_removal: libobs_wrapper::sources::ObsFilterRef,
    mask: libobs_wrapper::sources::ObsFilterRef,
}

/// The scene item of one camera in one scene — its placement, as libobs holds it.
///
/// Aliased because the full path appears in every camera helper's signature, and reading
/// three nested generic types tells nobody what the value IS.
type CameraItem = ObsSceneItemRef<ObsSourceRef>;

/// One open camera: its libobs source, the display name it answers to, and its filters.
///
/// The name is held here rather than re-derived because libobs keys sources BY NAME, and
/// two identical webcams report the identical device label — the unique name is decided
/// once, at creation (`hikari_protocol::camera_source_name`), and must not drift after.
struct OpenCamera {
    source: ObsSourceRef,
    name: String,
    filters: CameraFilters,
}

/// `stream` and `multistream` MUST be declared before `obs`: their outputs depend on
/// `obs.context` (same libobs context), and Rust drops struct fields in declaration order
/// (see `ObsInner`'s own comment for the exact class of bug this prevents — an
/// `ObsOutputRef` dropped after its parent context would either leak or touch an
/// already-destroyed context). The normal exit path (`exiting()`) already stops both and
/// clears `obs` in the right order; this field order is the belt-and-braces guard for an
/// abnormal drop (e.g. a future winit
/// callback panic) that would skip `exiting()` and drop `App` directly.
struct App {
    window: Option<Sendable<Window>>,
    stream: Option<StreamState>,
    multistream: Vec<PlatformStream>,
    /// When multistream frame stats were last reported — a single shared tick for the
    /// whole batch (unlike `StreamState`, `PlatformStream` doesn't carry its own timer,
    /// since every target reports on the same cadence).
    multistream_last_stats_at: std::time::Instant,
    /// When the mixer's levels were last reported (B6) — its own beat, much faster than the
    /// frame counters'.
    audio_last_levels_at: std::time::Instant,
    /// Le dernier essai d'un masque en attente (2026-09-09) — sa propre cadence, pour ne
    /// pas retenter à chaque battement d'un glissement de caméra en vol si les deux
    /// coïncident.
    mask_retry_last_at: std::time::Instant,
    /// Last known cursor position in the preview window, in physical pixels. winit reports
    /// press/release WITHOUT coordinates, so the position has to be remembered from the
    /// preceding move event.
    cursor: Option<(f32, f32)>,
    /// The preview's fitted size, kept in step with `Resized` — the divisor that turns a
    /// preview pixel into a canvas pixel.
    fitted: (u32, u32),
    /// The drag in progress, if any (B7, glisser-souris).
    drag: Option<DragState>,
    /// The camera glide in progress, if any (B7, option A — `SwitchScene` when a device is
    /// shown in both the outgoing and the incoming scene). `about_to_wait` advances it every
    /// tick; unrelated to `drag`, which is a mouse gesture, never an automatic one.
    camera_slide: Option<CameraSlide>,
    obs: Option<ObsInner>,
}

/// A camera gliding from its placement in the scene just left to its OWN saved placement in
/// the scene just entered (B7, option A) — never a placement invented for the occasion:
/// `to` is read from the incoming scene's own scene item BEFORE the slide starts, exactly
/// what it already held.
struct CameraSlide {
    scene: String,
    device_id: String,
    from: (i32, i32, f32),
    to: (i32, i32, f32),
    started_at: std::time::Instant,
    duration: std::time::Duration,
}

fn main() -> Result<()> {
    let outcome = if std::env::args().any(|arg| arg == "--detect-encoders") {
        bootstrap::detect_encoders_and_exit()
    } else if std::env::args().any(|arg| arg == "--detect-cameras") {
        bootstrap::detect_cameras_and_exit()
    } else {
        bootstrap::run()
    };
    if let Err(err) = outcome {
        // Report the failure on the wire before dying, so the controller never sees a
        // silent death (B0.0 lesson: a mute failure costs a day).
        emit(&EngineMessage::Error {
            message: err.to_string(),
        });
        std::io::stdout().flush().ok();
        return Err(err);
    }
    Ok(())
}

// No `cargo test` target here: `test = false` in Cargo.toml disables the harness because
// linking libobs (obs.dll) prevents a test binary from even loading headless. The pure,
// headless-testable protocol logic is covered in the `hikari-protocol` crate; the pure
// preview graft math (`fit_size`, `child_style_bits`) is duplicated (tiny, 3-5 lines) on
// the controller side in `preview_bridge.rs`, where it IS unit-tested (no libobs there).
// The real libobs scene + preview build is validated by RUNNING `hikari-engine` with the
// OBS runtime (integration regime, like the B0.0/B1b spikes).
