//! Le masque à coins arrondis (B-filtres, 2026-09-09) — pure fonction de distance signée,
//! prouvée sans moteur ni fichier.

use hikari_protocol::{generate_rounded_mask_rgba, MASK_RADIUS_MAX, MASK_RADIUS_MIN};

const SIZE: u32 = 64;

fn pixel(buf: &[u8], size: u32, x: u32, y: u32) -> (u8, u8, u8, u8) {
    let idx = ((y * size + x) * 4) as usize;
    (buf[idx], buf[idx + 1], buf[idx + 2], buf[idx + 3])
}

#[test]
fn should_be_a_buffer_of_the_right_size() {
    let buf = generate_rounded_mask_rgba(20, SIZE);
    assert_eq!(buf.len(), (SIZE * SIZE * 4) as usize);
}

#[test]
fn should_be_fully_opaque_at_the_center_whatever_the_radius() {
    for radius in [MASK_RADIUS_MIN, 10, 25, MASK_RADIUS_MAX] {
        let buf = generate_rounded_mask_rgba(radius, SIZE);
        let (r, g, b, a) = pixel(&buf, SIZE, SIZE / 2, SIZE / 2);
        assert_eq!((r, g, b, a), (255, 255, 255, 255), "rayon {radius}");
    }
}

#[test]
fn should_be_transparent_at_the_corner_with_a_small_radius() {
    // Un rayon petit laisse l'angle du carré presque droit — le coin doit rester dehors.
    let buf = generate_rounded_mask_rgba(5, SIZE);
    let (_, _, _, a) = pixel(&buf, SIZE, 0, 0);
    assert_eq!(a, 0);
}

#[test]
fn should_be_transparent_at_the_corner_even_at_max_radius() {
    // A 50%, la forme est un cercle inscrit dans le carre : son coin reste hors du cercle
    // (distance centre->coin = demi-cote * racine(2), superieure au rayon).
    let buf = generate_rounded_mask_rgba(MASK_RADIUS_MAX, SIZE);
    let (_, _, _, a) = pixel(&buf, SIZE, 0, 0);
    assert_eq!(a, 0);
}

#[test]
fn should_cut_more_of_the_corner_as_the_radius_grows() {
    // Arrondir un coin, c'est le TRANCHER — un point fixe tout près de la pointe perd en
    // opacité à mesure que le rayon grandit (l'arc mange davantage vers le centre), jamais
    // l'inverse. Vérifié avant d'écrire ce test : ma première version supposait le
    // contraire et le calcul l'a contredite — la formule avait raison, pas mon intuition.
    let point = (2, 2);
    let small = pixel(&generate_rounded_mask_rgba(5, SIZE), SIZE, point.0, point.1).3;
    let large = pixel(
        &generate_rounded_mask_rgba(30, SIZE),
        SIZE,
        point.0,
        point.1,
    )
    .3;
    assert!(
        large <= small,
        "grand rayon ({large}) > petit rayon ({small})"
    );
}

#[test]
fn should_clamp_a_radius_outside_the_documented_bounds() {
    let too_big = generate_rounded_mask_rgba(999, SIZE);
    let clamped = generate_rounded_mask_rgba(MASK_RADIUS_MAX, SIZE);
    assert_eq!(too_big, clamped);

    let too_small = generate_rounded_mask_rgba(-40, SIZE);
    let floored = generate_rounded_mask_rgba(MASK_RADIUS_MIN, SIZE);
    assert_eq!(too_small, floored);
}

#[test]
fn should_always_carry_white_rgb_only_alpha_varies() {
    // La couleur ne varie jamais, seule l'opacité dessine la forme — sinon le masque
    // teinterait la vidéo au lieu de la découper (alpha NON prémultiplié).
    let buf = generate_rounded_mask_rgba(15, SIZE);
    for chunk in buf.chunks_exact(4) {
        assert_eq!((chunk[0], chunk[1], chunk[2]), (255, 255, 255));
    }
}
