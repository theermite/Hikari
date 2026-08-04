//! Camera drag geometry (B7, glisser-souris) — pure math contract tests. The real mouse
//! events and libobs transform live in the engine's winit loop (integration regime, proven
//! by running the app); everything decidable without libobs is proven here.

use hikari_protocol::{is_inside, window_to_canvas};
use proptest::prelude::*;

#[test]
fn should_map_the_preview_origin_to_the_canvas_origin() {
    assert_eq!(window_to_canvas(0.0, 0.0, 960, 540, 1920, 1080), (0.0, 0.0));
}

#[test]
fn should_scale_a_preview_point_up_to_canvas_pixels() {
    // Aperçu deux fois plus petit que le canevas : un pixel d'aperçu vaut deux pixels de
    // canevas. Sans ce facteur, la caméra suivrait la souris à moitié vitesse.
    assert_eq!(window_to_canvas(480.0, 270.0, 960, 540, 1920, 1080), (960.0, 540.0));
}

#[test]
fn should_map_the_preview_corner_to_the_canvas_corner() {
    assert_eq!(window_to_canvas(960.0, 540.0, 960, 540, 1920, 1080), (1920.0, 1080.0));
}

#[test]
fn should_scale_each_axis_independently_when_the_preview_is_not_proportional() {
    let (x, y) = window_to_canvas(100.0, 100.0, 200, 400, 1000, 800);
    assert_eq!((x, y), (500.0, 200.0));
}

#[test]
fn should_treat_a_zero_sized_preview_as_one_pixel_rather_than_dividing_by_zero() {
    // Une fenêtre de largeur 0 arrive réellement pendant une réduction de fenêtre. Le
    // résultat n'a pas de sens visuel, mais il ne doit être ni infini ni NaN.
    let (x, y) = window_to_canvas(5.0, 5.0, 0, 0, 1920, 1080);
    assert!(x.is_finite() && y.is_finite());
}

#[test]
fn should_report_a_point_inside_the_rectangle() {
    assert!(is_inside(50.0, 50.0, 0.0, 0.0, 100.0, 100.0));
}

#[test]
fn should_report_a_point_outside_on_each_side() {
    assert!(!is_inside(-1.0, 50.0, 0.0, 0.0, 100.0, 100.0));
    assert!(!is_inside(101.0, 50.0, 0.0, 0.0, 100.0, 100.0));
    assert!(!is_inside(50.0, -1.0, 0.0, 0.0, 100.0, 100.0));
    assert!(!is_inside(50.0, 101.0, 0.0, 0.0, 100.0, 100.0));
}

#[test]
fn should_count_the_edges_as_inside() {
    // Les bords comptent : attraper la caméra pile sur son bord doit fonctionner, sinon le
    // geste rate d'un pixel sans raison visible.
    assert!(is_inside(0.0, 0.0, 0.0, 0.0, 100.0, 100.0));
    assert!(is_inside(100.0, 100.0, 0.0, 0.0, 100.0, 100.0));
}

#[test]
fn should_report_nothing_inside_an_empty_rectangle() {
    assert!(!is_inside(0.0, 0.0, 0.0, 0.0, 0.0, 0.0));
}

proptest! {
    #[test]
    fn should_never_produce_a_non_finite_canvas_point(
        cursor_x in -5000.0f32..5000.0,
        cursor_y in -5000.0f32..5000.0,
        fitted_w in 0u32..4000,
        fitted_h in 0u32..4000,
        canvas_w in 1u32..8000,
        canvas_h in 1u32..8000,
    ) {
        let (x, y) = window_to_canvas(cursor_x, cursor_y, fitted_w, fitted_h, canvas_w, canvas_h);
        prop_assert!(x.is_finite(), "x non fini pour {cursor_x} / {fitted_w}");
        prop_assert!(y.is_finite(), "y non fini pour {cursor_y} / {fitted_h}");
    }

    #[test]
    fn should_always_find_the_centre_of_a_rectangle_inside_it(
        x in -2000.0f32..2000.0,
        y in -2000.0f32..2000.0,
        w in 1.0f32..2000.0,
        h in 1.0f32..2000.0,
    ) {
        prop_assert!(is_inside(x + w / 2.0, y + h / 2.0, x, y, w, h));
    }
}
