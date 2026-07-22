//! Preview bridge — grafts the engine's preview window (its own process, ADR-013) into
//! the app's window: cross-process `SetParent` (Win32), proven at the B1b spike
//! (`spikes/b1b-preview`, 2 jalons GO 2026-07-18). The risk documented before coding
//! (Microsoft/Raymond Chen: cross-process parent/child attaches input queues) did NOT
//! materialize in that spike — resize and move stayed fluid, no orphaned process.
//!
//! Pure math (`fit_size`, `child_style_bits`) is unit-tested here (this crate links no
//! libobs, unlike `engine`, so its test harness runs headless). The unsafe Win32 calls are
//! a thin shell around that pure logic, transcribed from the spike — not invented here.

use anyhow::{Context, Result};
use windows::Win32::Foundation::HWND;
use windows::Win32::UI::WindowsAndMessaging::{
    GWL_STYLE, SET_WINDOW_POS_FLAGS, SWP_HIDEWINDOW, SWP_NOACTIVATE, SWP_NOZORDER,
    SWP_SHOWWINDOW, SetParent, SetWindowLongPtrW, SetWindowPos, WS_CHILD, WS_VISIBLE,
};

const TARGET_ASPECT: f32 = 16.0 / 9.0;

/// Aspect-fit math for the grafted preview: keeps 16:9 inside the given area. Transcribed
/// unchanged from the B1b spike (`fit_display`), proven GO — same formula duplicated (not
/// shared) in the engine crate, which handles its OWN local resize events on the same
/// window; see `engine/src/main.rs` for why the two sides can't share a crate.
pub fn fit_size(area_w: u32, area_h: u32) -> (u32, u32) {
    // Clamp BOTH dimensions before any arithmetic — a transient 0 during a resize must
    // never reach a multiplication/division (would return a degenerate 0×0 display size).
    let area_w = area_w.max(1);
    let area_h = area_h.max(1);
    // The truncating f32->u32 cast can itself round a tiny computed dimension down to 0
    // (e.g. width=1 -> height 0.56 -> 0) — clamp the COMPUTED side too, not just the input.
    if area_w as f32 / area_h as f32 > TARGET_ASPECT {
        ((((area_h as f32) * TARGET_ASPECT) as u32).max(1), area_h)
    } else {
        (area_w, (((area_w as f32) / TARGET_ASPECT) as u32).max(1))
    }
}

/// Where and at what size the preview should actually be drawn inside a target area
/// (the Aperçu panel's real screen rect, option B): 16:9-fit, then CENTERED in the area
/// rather than anchored at its top-left — an aspect-fit smaller than the area would
/// otherwise hug one corner instead of sitting centered like a normal video letterbox.
fn fit_and_center(x: i32, y: i32, area_w: u32, area_h: u32) -> (i32, i32, u32, u32) {
    let (w, h) = fit_size(area_w, area_h);
    let off_x = x + ((area_w.max(1) - w) / 2) as i32;
    let off_y = y + ((area_h.max(1) - h) / 2) as i32;
    (off_x, off_y, w, h)
}

/// The exact style bits a grafted window must carry: `WS_CHILD` (it becomes a child of the
/// host) composed WITH `WS_VISIBLE` (a real, DISTINCT bit — `SetWindowLongPtrW` REPLACES
/// the whole style, so omitting it leaves the window invisible even though positioned and
/// parented correctly; this exact bug was hit and fixed at the spike, 2026-07-18).
pub fn child_style_bits() -> u32 {
    WS_CHILD.0 | WS_VISIBLE.0
}

/// Grafts the engine's preview window into the host (app) window ONCE: sets the
/// child+visible style, reparents cross-process, and positions it inside `(x, y,
/// area_w, area_h)` — the Aperçu panel's real screen rect (option B, never the whole
/// window, superseded 2026-07-23). Reparenting is a one-time operation; subsequent moves
/// go through `position_preview_window`.
///
/// SAFETY: both HWNDs must be valid, live windows at call time — `engine_hwnd` comes
/// straight off `EngineMessage::PreviewReady` (the engine just created it) and `host_hwnd`
/// off `WebviewWindow::hwnd()` (the app's own window, always valid while the app runs).
pub fn graft_preview_window(
    engine_hwnd: i64,
    host_hwnd: i64,
    x: i32,
    y: i32,
    area_w: u32,
    area_h: u32,
) -> Result<()> {
    let engine = HWND(engine_hwnd as *mut _);
    let host = HWND(host_hwnd as *mut _);
    unsafe {
        SetWindowLongPtrW(engine, GWL_STYLE, child_style_bits() as isize);
        SetParent(engine, Some(host)).context("SetParent (reparent cross-process)")?;
    }
    position_preview_window(engine_hwnd, x, y, area_w, area_h);
    Ok(())
}

/// Repositions/resizes an already-grafted preview to fit (centered, 16:9) inside `(x, y,
/// area_w, area_h)` — called whenever the Aperçu panel's own screen rect changes (moved,
/// resized, sibling panel pushed it). Also ensures the window is shown (a prior
/// `hide_preview_window` call may have hidden it while the panel's tab was inactive).
///
/// SAFETY: `engine_hwnd` must be a valid, live window at call time — it comes from the
/// Tauri-managed state populated by a prior successful `graft_preview_window`, so it is
/// always a real, still-grafted engine window while the app runs.
pub fn position_preview_window(engine_hwnd: i64, x: i32, y: i32, area_w: u32, area_h: u32) {
    let engine = HWND(engine_hwnd as *mut _);
    let (off_x, off_y, w, h) = fit_and_center(x, y, area_w, area_h);
    unsafe {
        if SetWindowPos(
            engine,
            None,
            off_x,
            off_y,
            w as i32,
            h as i32,
            SET_WINDOW_POS_FLAGS(SWP_NOZORDER.0 | SWP_NOACTIVATE.0 | SWP_SHOWWINDOW.0),
        )
        .is_err()
        {
            eprintln!("[preview_bridge] SetWindowPos a échoué au repositionnement (HWND {engine_hwnd})");
        }
    }
}

/// Hides the grafted preview without destroying it — called when the Aperçu panel's tab
/// becomes inactive (dockview only shows one tab per group; a native child window would
/// otherwise keep rendering ON TOP of whichever other tab is now showing).
///
/// SAFETY: same as `position_preview_window`.
pub fn hide_preview_window(engine_hwnd: i64) {
    let engine = HWND(engine_hwnd as *mut _);
    unsafe {
        if SetWindowPos(
            engine,
            None,
            0,
            0,
            0,
            0,
            SET_WINDOW_POS_FLAGS(SWP_NOZORDER.0 | SWP_NOACTIVATE.0 | SWP_HIDEWINDOW.0),
        )
        .is_err()
        {
            eprintln!("[preview_bridge] SetWindowPos a échoué au masquage (HWND {engine_hwnd})");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_fit_wide_host_by_limiting_width() {
        // Host wider than 16:9 (e.g. an ultrawide app window): height is the limiting
        // factor, width shrinks to match the ratio.
        let (w, h) = fit_size(2560, 1000);
        assert_eq!(h, 1000, "height matches the host exactly");
        assert!(w < 2560, "width shrinks to keep 16:9");
        assert!((w as f32 / h as f32 - TARGET_ASPECT).abs() < 0.01, "ratio stays 16:9");
    }

    #[test]
    fn should_fit_tall_host_by_limiting_height() {
        // Host taller than 16:9 (e.g. a portrait-ish panel): width is the limiting factor.
        let (w, h) = fit_size(800, 1200);
        assert_eq!(w, 800, "width matches the host exactly");
        assert!(h < 1200, "height shrinks to keep 16:9");
        assert!((w as f32 / h as f32 - TARGET_ASPECT).abs() < 0.01, "ratio stays 16:9");
    }

    #[test]
    fn should_fit_exact_16_9_host_without_shrinking() {
        let (w, h) = fit_size(1920, 1080);
        assert_eq!((w, h), (1920, 1080), "already 16:9 — no adjustment needed");
    }

    #[test]
    fn should_not_panic_on_degenerate_zero_height() {
        // A host reporting 0 height (transient during a resize) must not divide by zero,
        // and must never return a 0×0 size (a real defect found by this test: clamping
        // only the ratio comparison, not the arithmetic, still let 0 flow through).
        let (w, h) = fit_size(800, 0);
        assert!(w > 0 && h > 0, "both dimensions stay positive on degenerate input");
    }

    #[test]
    fn should_not_panic_on_degenerate_zero_width() {
        let (w, h) = fit_size(0, 600);
        assert!(w > 0 && h > 0, "both dimensions stay positive on degenerate input");
    }

    #[test]
    fn should_compose_child_and_visible_bits() {
        // Regression guard: this exact omission (WS_VISIBLE dropped by a full style
        // replace) made the grafted window invisible at the spike, 2026-07-18.
        let style = child_style_bits();
        assert_eq!(style & WS_CHILD.0, WS_CHILD.0, "WS_CHILD bit is set");
        assert_eq!(style & WS_VISIBLE.0, WS_VISIBLE.0, "WS_VISIBLE bit is set — spike regression");
    }

    #[test]
    fn should_center_fitted_size_inside_squarer_area() {
        // A square area (1:1, narrower than 16:9): the fit shrinks HEIGHT, not width — the
        // fitted rect must be offset DOWN to sit vertically centered, never hugging the
        // area's top edge.
        let (off_x, off_y, w, h) = fit_and_center(100, 50, 1000, 1000);
        assert_eq!(off_x, 100, "width fills the area exactly — no horizontal letterbox");
        assert!(off_y > 50, "fitted height shorter than the area — must be re-centered down");
        assert_eq!(off_y + h as i32, 50 + 1000 - (off_y - 50), "centered: equal margin top/bottom");
        let _ = w;
    }

    #[test]
    fn should_offset_by_area_origin_when_area_is_exact_16_9() {
        // Exact 16:9 area: no letterboxing needed, the fitted rect exactly matches the
        // area — offset must equal the area's own origin, not (0, 0).
        let (off_x, off_y, w, h) = fit_and_center(200, 80, 1920, 1080);
        assert_eq!((off_x, off_y, w, h), (200, 80, 1920, 1080));
    }
}
