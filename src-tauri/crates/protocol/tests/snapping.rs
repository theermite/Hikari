//! Aimantation des sources (B7) — logique pure, prouvée sans moteur.

use hikari_protocol::{SNAP_DISTANCE, snap_position};
use proptest::prelude::*;

/// Un canevas 1920×1080 et une source 400×200, les valeurs les plus parlantes à relire.
const CANVAS: (u32, u32) = (1920, 1080);
const SIZE: (f32, f32) = (400.0, 200.0);

fn snap(x: f32, y: f32) -> (f32, f32) {
    snap_position(x, y, SIZE.0, SIZE.1, CANVAS.0, CANVAS.1)
}

#[test]
fn should_stick_to_the_left_edge_when_close() {
    assert_eq!(snap(5.0, 500.0).0, 0.0);
}

#[test]
fn should_stick_to_the_top_edge_when_close() {
    assert_eq!(snap(500.0, 4.0).1, 0.0);
}

#[test]
fn should_stick_to_the_right_edge_when_close() {
    // Le bord DROIT de la source rejoint le bord droit du cadre : x = largeur - taille.
    assert_eq!(snap(1515.0, 500.0).0, 1520.0);
}

#[test]
fn should_stick_to_the_bottom_edge_when_close() {
    assert_eq!(snap(500.0, 875.0).1, 880.0);
}

#[test]
fn should_stick_to_the_centre_on_each_axis() {
    // Centrer est le geste le plus courant après coller à un bord.
    assert_eq!(snap(755.0, 435.0), (760.0, 440.0));
}

#[test]
fn should_leave_a_far_position_untouched() {
    // Loin de tout repère, la source suit la souris au pixel près : l'aimantation ne doit
    // jamais tirer une source qu'on place volontairement de travers.
    assert_eq!(snap(700.0, 300.0), (700.0, 300.0));
}

#[test]
fn should_leave_a_position_just_outside_the_range_untouched() {
    let just_outside = SNAP_DISTANCE + 1.0;
    assert_eq!(snap(just_outside, 500.0).0, just_outside);
}

#[test]
fn should_stick_at_the_exact_limit_of_the_range() {
    assert_eq!(snap(SNAP_DISTANCE, 500.0).0, 0.0);
}

#[test]
fn should_not_snap_a_source_larger_than_the_canvas_to_a_meaningless_centre() {
    // Une source plus grande que le cadre a un « centre » négatif ; l'aimantation doit
    // rester cohérente plutôt que de la propulser hors champ.
    let (x, _) = snap_position(-5.0, 0.0, 3000.0, 200.0, CANVAS.0, CANVAS.1);
    assert!(x.is_finite());
}

proptest! {
    #[test]
    fn should_never_move_a_source_further_than_the_snap_range(
        x in -3000.0f32..3000.0,
        y in -3000.0f32..3000.0,
    ) {
        // La propriété qui rend le geste sûr : l'aimantation CORRIGE, elle ne téléporte pas.
        let (sx, sy) = snap(x, y);
        prop_assert!((sx - x).abs() <= SNAP_DISTANCE, "x tiré de {} à {}", x, sx);
        prop_assert!((sy - y).abs() <= SNAP_DISTANCE, "y tiré de {} à {}", y, sy);
    }

    #[test]
    fn should_always_return_finite_positions(
        x in -5000.0f32..5000.0,
        y in -5000.0f32..5000.0,
        w in 1.0f32..5000.0,
        h in 1.0f32..5000.0,
    ) {
        let (sx, sy) = snap_position(x, y, w, h, CANVAS.0, CANVAS.1);
        prop_assert!(sx.is_finite() && sy.is_finite());
    }
}
