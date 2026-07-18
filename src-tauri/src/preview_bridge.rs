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
    GWL_STYLE, MoveWindow, SET_WINDOW_POS_FLAGS, SWP_NOACTIVATE, SWP_NOZORDER, SetParent,
    SetWindowLongPtrW, SetWindowPos, WS_CHILD, WS_VISIBLE,
};

const TARGET_ASPECT: f32 = 16.0 / 9.0;

/// Aspect-fit math for the grafted preview: keeps 16:9 inside the given host client area.
/// Transcribed unchanged from the B1b spike (`fit_display`), proven GO — same formula
/// duplicated (not shared) in the engine crate, which handles its OWN local resize events
/// on the same window; see `engine/src/main.rs` for why the two sides can't share a crate.
pub fn fit_size(host_w: u32, host_h: u32) -> (u32, u32) {
    // Clamp BOTH dimensions before any arithmetic — a transient 0 during a resize must
    // never reach a multiplication/division (would return a degenerate 0×0 display size).
    let host_w = host_w.max(1);
    let host_h = host_h.max(1);
    // The truncating f32->u32 cast can itself round a tiny computed dimension down to 0
    // (e.g. width=1 -> height 0.56 -> 0) — clamp the COMPUTED side too, not just the input.
    if host_w as f32 / host_h as f32 > TARGET_ASPECT {
        ((((host_h as f32) * TARGET_ASPECT) as u32).max(1), host_h)
    } else {
        (host_w, (((host_w as f32) / TARGET_ASPECT) as u32).max(1))
    }
}

/// The exact style bits a grafted window must carry: `WS_CHILD` (it becomes a child of the
/// host) composed WITH `WS_VISIBLE` (a real, DISTINCT bit — `SetWindowLongPtrW` REPLACES
/// the whole style, so omitting it leaves the window invisible even though positioned and
/// parented correctly; this exact bug was hit and fixed at the spike, 2026-07-18).
pub fn child_style_bits() -> u32 {
    WS_CHILD.0 | WS_VISIBLE.0
}

/// Grafts the engine's preview window into the host (app) window: sets the child+visible
/// style, reparents cross-process, and sizes it to fit `host_w`×`host_h` (16:9 inside).
///
/// SAFETY: both HWNDs must be valid, live windows at call time — `engine_hwnd` comes
/// straight off `EngineMessage::PreviewReady` (the engine just created it) and `host_hwnd`
/// off `WebviewWindow::hwnd()` (the app's own window, always valid while the app runs).
pub fn graft_preview_window(engine_hwnd: i64, host_hwnd: i64, host_w: u32, host_h: u32) -> Result<()> {
    let engine = HWND(engine_hwnd as *mut _);
    let host = HWND(host_hwnd as *mut _);
    let (w, h) = fit_size(host_w, host_h);
    unsafe {
        SetWindowLongPtrW(engine, GWL_STYLE, child_style_bits() as isize);
        SetParent(engine, Some(host)).context("SetParent (reparent cross-process)")?;
        if SetWindowPos(
            engine,
            None,
            0,
            0,
            w as i32,
            h as i32,
            SET_WINDOW_POS_FLAGS(SWP_NOZORDER.0 | SWP_NOACTIVATE.0),
        )
        .is_err()
        {
            eprintln!("[preview_bridge] SetWindowPos a échoué au greffage initial (HWND {engine_hwnd})");
        }
    }
    Ok(())
}

/// Re-fits the already-grafted preview window when the host resizes. Called from the app's
/// window-resize handler with the engine HWND kept in Tauri-managed state.
///
/// SAFETY: `engine_hwnd` must be a valid, live window at call time — it comes from the
/// Tauri-managed state populated by a prior successful `graft_preview_window`, so it is
/// always a real, still-grafted engine window while the app runs (same guarantee as
/// `graft_preview_window`'s own SAFETY note above).
pub fn resize_preview_window(engine_hwnd: i64, host_w: u32, host_h: u32) {
    let engine = HWND(engine_hwnd as *mut _);
    let (w, h) = fit_size(host_w, host_h);
    unsafe {
        if MoveWindow(engine, 0, 0, w as i32, h as i32, true).is_err() {
            eprintln!("[preview_bridge] MoveWindow a échoué au redimensionnement (HWND {engine_hwnd})");
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
}
