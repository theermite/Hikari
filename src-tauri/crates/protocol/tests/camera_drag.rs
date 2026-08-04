//! Camera drag geometry (B7, glisser-souris) — pure math contract tests. The real mouse
//! events and libobs transform live in the engine's winit loop (integration regime, proven
//! by running the app); everything decidable without libobs is proven here.

use hikari_protocol::{
    CORNER_GRAB_MARGIN, Corner, corner_at, is_inside, resize_box, resize_scale, window_to_canvas,
};
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

#[test]
fn should_find_each_corner_under_the_cursor() {
    // Rectangle 0,0 → 400×400, marge 32.
    assert_eq!(corner_at(5.0, 5.0, 0.0, 0.0, 400.0, 400.0, 32.0), Some(Corner::TopLeft));
    assert_eq!(corner_at(395.0, 5.0, 0.0, 0.0, 400.0, 400.0, 32.0), Some(Corner::TopRight));
    assert_eq!(corner_at(5.0, 395.0, 0.0, 0.0, 400.0, 400.0, 32.0), Some(Corner::BottomLeft));
    assert_eq!(corner_at(395.0, 395.0, 0.0, 0.0, 400.0, 400.0, 32.0), Some(Corner::BottomRight));
}

#[test]
fn should_find_no_corner_in_the_middle() {
    // Le centre veut dire « déplace-moi », jamais « redimensionne-moi ».
    assert_eq!(corner_at(200.0, 200.0, 0.0, 0.0, 400.0, 400.0, 32.0), None);
}

#[test]
fn should_find_no_corner_outside_the_rectangle() {
    assert_eq!(corner_at(-10.0, -10.0, 0.0, 0.0, 400.0, 400.0, 32.0), None);
    assert_eq!(corner_at(500.0, 200.0, 0.0, 0.0, 400.0, 400.0, 32.0), None);
}

#[test]
fn should_offer_no_corner_on_a_camera_too_small_to_have_a_middle() {
    // Sinon une petite caméra n'aurait plus aucune zone « déplacer » et deviendrait
    // impossible à bouger.
    assert_eq!(corner_at(10.0, 10.0, 0.0, 0.0, 40.0, 40.0, 32.0), None);
}

#[test]
fn should_pin_the_opposite_corner_when_resizing() {
    assert_eq!(Corner::BottomRight.anchor_side(), (true, true));
    assert_eq!(Corner::TopLeft.anchor_side(), (false, false));
    // Tirer en haut à droite épingle le bas à GAUCHE : ancrage à gauche, pas en haut.
    assert_eq!(Corner::TopRight.anchor_side(), (true, false));
    // Tirer en bas à gauche épingle le haut à DROITE : ancrage en haut, pas à gauche.
    assert_eq!(Corner::BottomLeft.anchor_side(), (false, true));
}

#[test]
fn should_derive_the_scale_from_the_distance_to_the_anchor() {
    // Curseur à 640 px d'un ancrage en 0, caméra native de 1280 : moitié de taille.
    assert_eq!(resize_scale(0.0, 640.0, 1280), 0.5);
    assert_eq!(resize_scale(0.0, 1280.0, 1280), 1.0);
}

#[test]
fn should_derive_the_same_scale_whichever_side_the_cursor_is_on() {
    // Tirer à gauche de l'ancrage donne la même taille que tirer à droite : c'est la
    // distance qui compte, pas le sens.
    assert_eq!(resize_scale(500.0, 1140.0, 1280), resize_scale(500.0, -140.0, 1280));
}

#[test]
fn should_return_zero_scale_rather_than_infinity_on_a_zero_width_source() {
    assert_eq!(resize_scale(0.0, 640.0, 0), 0.0);
}

#[test]
fn should_grow_away_from_the_pinned_corner() {
    // Ancrage en haut à gauche (100,100) : la boîte part de l'ancrage.
    assert_eq!(resize_box(100.0, 100.0, true, true, 200.0, 150.0), (100.0, 100.0));
    // Ancrage en bas à droite : la boîte finit sur l'ancrage.
    assert_eq!(resize_box(100.0, 100.0, false, false, 200.0, 150.0), (-100.0, -50.0));
}

proptest! {
    #[test]
    fn should_keep_the_anchor_corner_exactly_in_place(
        anchor_x in -1000.0f32..1000.0,
        anchor_y in -1000.0f32..1000.0,
        new_w in 1.0f32..2000.0,
        new_h in 1.0f32..2000.0,
        anchor_is_left in any::<bool>(),
        anchor_is_top in any::<bool>(),
    ) {
        // La propriété qui rend le geste prévisible : le coin opposé ne bouge JAMAIS,
        // quelle que soit la taille demandée.
        let (x, y) = resize_box(anchor_x, anchor_y, anchor_is_left, anchor_is_top, new_w, new_h);
        let pinned_x = if anchor_is_left { x } else { x + new_w };
        let pinned_y = if anchor_is_top { y } else { y + new_h };
        prop_assert!((pinned_x - anchor_x).abs() < 0.01, "ancrage x deplace");
        prop_assert!((pinned_y - anchor_y).abs() < 0.01, "ancrage y deplace");
    }

    #[test]
    fn should_never_report_a_corner_outside_the_rectangle(
        px in -500.0f32..900.0,
        py in -500.0f32..900.0,
    ) {
        if corner_at(px, py, 0.0, 0.0, 400.0, 400.0, CORNER_GRAB_MARGIN).is_some() {
            prop_assert!(is_inside(px, py, 0.0, 0.0, 400.0, 400.0));
        }
    }

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
