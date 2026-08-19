//! Pure canvas math for the mouse-driven camera (B7): snapping, clamping, the
//! window-to-canvas conversion, hit testing, and corner-based resize.

/// Distance d'accroche de l'aimantation, en pixels de canevas (B7).
///
/// Assez large pour attraper sans viser, assez courte pour qu'une source posée volontairement
/// à 30 pixels d'un bord y reste.
pub const SNAP_DISTANCE: f32 = 16.0;

/// Colle une source aux repères du cadre quand elle en approche : les quatre bords, et les
/// deux axes centraux.
///
/// L'aimantation CORRIGE, elle ne téléporte pas — une position ne bouge jamais de plus de
/// [`SNAP_DISTANCE`], propriété épinglée par un proptest. Loin de tout repère, la source suit
/// la souris au pixel près : aimanter ce qu'on place volontairement de travers serait pire
/// que ne rien aimanter.
pub fn snap_position(
    x: f32,
    y: f32,
    width: f32,
    height: f32,
    canvas_w: u32,
    canvas_h: u32,
) -> (f32, f32) {
    let snap_axis = |value: f32, targets: [f32; 3]| {
        targets
            .into_iter()
            .filter(|target| target.is_finite() && (value - target).abs() <= SNAP_DISTANCE)
            // Le repère le plus proche gagne, jamais le premier trouvé : deux repères
            // voisins (un bord et le centre sur une petite source) doivent départager.
            .min_by(|a, b| {
                (value - a).abs().total_cmp(&(value - b).abs())
            })
            .unwrap_or(value)
    };
    let (canvas_w, canvas_h) = (canvas_w as f32, canvas_h as f32);
    (
        snap_axis(x, [0.0, canvas_w - width, (canvas_w - width) / 2.0]),
        snap_axis(y, [0.0, canvas_h - height, (canvas_h - height) / 2.0]),
    )
}

/// Clamp bounds for camera moves (B7) — a generous sanity range, not exact canvas
/// containment: it stops the camera drifting to absurd coordinates, it never guarantees
/// "stays inside the frame".
///
/// An earlier note here claimed the live canvas size was unreadable outside libobs's render
/// thread (`obs_get_video_info` behind a private dispatch). That was wrong:
/// `ObsRuntime::run_with_obs_result` is public, and `camera::canvas_size` reads it that way
/// since the drag brick (2026-08-04). The bound stays a deliberate sanity range all the
/// same — clamping to the exact canvas would forbid a camera deliberately parked
/// half-offscreen, which OBS allows.
pub const CAMERA_POSITION_BOUND: i32 = 4000;

/// Multiplicative step applied per `ScaleCamera` click (B7) — ±10%, small enough that a
/// misclick is easy to undo with the opposite button.
pub const CAMERA_SCALE_STEP: f32 = 0.1;
/// Scale floor for `ScaleCamera` (B7) — below this the camera would be too small to see.
pub const CAMERA_SCALE_MIN: f32 = 0.2;
/// Scale ceiling for `ScaleCamera` (B7) — above this a single webcam would dwarf the canvas.
pub const CAMERA_SCALE_MAX: f32 = 3.0;

/// Clamps a candidate camera position to `CAMERA_POSITION_BOUND` on both axes. Pure, so
/// the sanity bound is proven by unit tests without a real engine process.
pub fn clamp_camera_position(x: i32, y: i32) -> (i32, i32) {
    (x.clamp(-CAMERA_POSITION_BOUND, CAMERA_POSITION_BOUND), y.clamp(-CAMERA_POSITION_BOUND, CAMERA_POSITION_BOUND))
}

/// Clamps a candidate camera scale factor to `[CAMERA_SCALE_MIN, CAMERA_SCALE_MAX]`. Pure,
/// same reason as `clamp_camera_position`.
pub fn clamp_camera_scale(scale: f32) -> f32 {
    scale.clamp(CAMERA_SCALE_MIN, CAMERA_SCALE_MAX)
}

/// Converts a point in the preview window into canvas coordinates (B7, glisser-souris).
///
/// The preview shows the whole canvas shrunk to the fitted area, so one preview pixel is
/// worth `canvas / fitted` canvas pixels — without that factor the camera would trail the
/// cursor at the wrong speed. Each axis scales independently: the fitted area keeps the
/// canvas aspect in practice, but nothing here depends on it.
///
/// A zero-sized preview really happens while a window is being minimized; it is treated as
/// one pixel so the result stays finite instead of becoming infinity or NaN.
pub fn window_to_canvas(
    cursor_x: f32,
    cursor_y: f32,
    fitted_w: u32,
    fitted_h: u32,
    canvas_w: u32,
    canvas_h: u32,
) -> (f32, f32) {
    let fitted_w = fitted_w.max(1) as f32;
    let fitted_h = fitted_h.max(1) as f32;
    (
        cursor_x * (canvas_w as f32) / fitted_w,
        cursor_y * (canvas_h as f32) / fitted_h,
    )
}

/// Whether `(px, py)` falls within the rectangle at `(x, y)` of size `w × h`. Edges count as
/// inside: grabbing the camera exactly on its border must work, otherwise the gesture
/// misses by one pixel for no visible reason. An empty rectangle contains nothing.
pub fn is_inside(px: f32, py: f32, x: f32, y: f32, w: f32, h: f32) -> bool {
    w > 0.0 && h > 0.0 && px >= x && px <= x + w && py >= y && py <= y + h
}

/// Which corner of the camera the cursor is over (B7, redimensionnement à la souris).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Corner {
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
}

impl Corner {
    /// Whether the corner OPPOSITE this one — the one that stays put while resizing — is on
    /// the left, and on the top. Those two flags are all `resize_box` needs to place the
    /// rectangle without a second match.
    pub fn anchor_side(self) -> (bool, bool) {
        match self {
            Corner::TopLeft => (false, false),
            Corner::TopRight => (true, false),
            Corner::BottomLeft => (false, true),
            Corner::BottomRight => (true, true),
        }
    }
}

/// How close to a corner the cursor must be to grab it, in canvas pixels. Big enough to hit
/// comfortably, small enough that the middle of a small camera still means "move me".
pub const CORNER_GRAB_MARGIN: f32 = 32.0;

/// The corner under `(px, py)`, or `None` if the cursor is not near one — in which case the
/// caller treats the gesture as a move.
///
/// A corner wins over the body on purpose: on a small camera the four margins can cover most
/// of the surface, and resizing is the more precise intent. The rectangle must be at least
/// twice the margin on both axes for corners to be offered at all, otherwise a tiny camera
/// could never be moved again.
pub fn corner_at(px: f32, py: f32, x: f32, y: f32, w: f32, h: f32, margin: f32) -> Option<Corner> {
    if w < margin * 2.0 || h < margin * 2.0 || !is_inside(px, py, x, y, w, h) {
        return None;
    }
    let left = px <= x + margin;
    let right = px >= x + w - margin;
    let top = py <= y + margin;
    let bottom = py >= y + h - margin;
    match (left, right, top, bottom) {
        (true, _, true, _) => Some(Corner::TopLeft),
        (_, true, true, _) => Some(Corner::TopRight),
        (true, _, _, true) => Some(Corner::BottomLeft),
        (_, true, _, true) => Some(Corner::BottomRight),
        _ => None,
    }
}

/// The scale a resize gesture asks for: the cursor's horizontal distance from the anchor,
/// divided by the camera's native width. Width drives it alone so the aspect ratio is kept —
/// a webcam squashed on one axis is never what the user meant.
///
/// A zero base width yields `0.0` rather than infinity; the caller clamps the result anyway
/// (`clamp_camera_scale`), so a degenerate source can't produce an absurd size.
pub fn resize_scale(anchor_x: f32, cursor_x: f32, base_w: u32) -> f32 {
    if base_w == 0 {
        return 0.0;
    }
    (cursor_x - anchor_x).abs() / base_w as f32
}

/// Where the resized rectangle starts, given the anchor corner that must stay put. The
/// anchor is the corner OPPOSITE the one being dragged: grabbing bottom-right pins top-left,
/// so the camera grows away from a fixed point instead of sliding while it resizes.
pub fn resize_box(
    anchor_x: f32,
    anchor_y: f32,
    anchor_is_left: bool,
    anchor_is_top: bool,
    new_w: f32,
    new_h: f32,
) -> (f32, f32) {
    (
        if anchor_is_left { anchor_x } else { anchor_x - new_w },
        if anchor_is_top { anchor_y } else { anchor_y - new_h },
    )
}
