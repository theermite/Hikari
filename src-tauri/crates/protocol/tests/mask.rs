//! Le masque à coins arrondis et le masque cercle (B-filtres, 2026-09-09) — pure fonction
//! de distance signée, prouvée sans moteur ni fichier.

use hikari_protocol::{
    generate_circle_mask_rgba, generate_rounded_mask_rgba, scaled_mask_size, MASK_MAX_DIMENSION,
    MASK_RADIUS_MAX, MASK_RADIUS_MIN,
};

const SIZE: u32 = 64;

fn pixel(buf: &[u8], width: u32, x: u32, y: u32) -> (u8, u8, u8, u8) {
    let idx = ((y * width + x) * 4) as usize;
    (buf[idx], buf[idx + 1], buf[idx + 2], buf[idx + 3])
}

#[test]
fn should_be_a_buffer_of_the_right_size() {
    let buf = generate_rounded_mask_rgba(20, SIZE, SIZE);
    assert_eq!(buf.len(), (SIZE * SIZE * 4) as usize);
}

#[test]
fn should_be_fully_opaque_at_the_center_whatever_the_radius() {
    for radius in [MASK_RADIUS_MIN, 10, 25, MASK_RADIUS_MAX] {
        let buf = generate_rounded_mask_rgba(radius, SIZE, SIZE);
        let (r, g, b, a) = pixel(&buf, SIZE, SIZE / 2, SIZE / 2);
        assert_eq!((r, g, b, a), (255, 255, 255, 255), "rayon {radius}");
    }
}

#[test]
fn should_be_transparent_at_the_corner_with_a_small_radius() {
    // Un rayon petit laisse l'angle du carré presque droit — le coin doit rester dehors.
    let buf = generate_rounded_mask_rgba(5, SIZE, SIZE);
    let (_, _, _, a) = pixel(&buf, SIZE, 0, 0);
    assert_eq!(a, 0);
}

#[test]
fn should_be_transparent_at_the_corner_even_at_max_radius() {
    // A 50%, la forme est un cercle inscrit dans le carre : son coin reste hors du cercle
    // (distance centre->coin = demi-cote * racine(2), superieure au rayon).
    let buf = generate_rounded_mask_rgba(MASK_RADIUS_MAX, SIZE, SIZE);
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
    let small = pixel(
        &generate_rounded_mask_rgba(5, SIZE, SIZE),
        SIZE,
        point.0,
        point.1,
    )
    .3;
    let large = pixel(
        &generate_rounded_mask_rgba(30, SIZE, SIZE),
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
    let too_big = generate_rounded_mask_rgba(999, SIZE, SIZE);
    let clamped = generate_rounded_mask_rgba(MASK_RADIUS_MAX, SIZE, SIZE);
    assert_eq!(too_big, clamped);

    let too_small = generate_rounded_mask_rgba(-40, SIZE, SIZE);
    let floored = generate_rounded_mask_rgba(MASK_RADIUS_MIN, SIZE, SIZE);
    assert_eq!(too_small, floored);
}

#[test]
fn should_always_carry_white_rgb_only_alpha_varies() {
    // La couleur ne varie jamais, seule l'opacité dessine la forme — sinon le masque
    // teinterait la vidéo au lieu de la découper (alpha NON prémultiplié).
    let buf = generate_rounded_mask_rgba(15, SIZE, SIZE);
    for chunk in buf.chunks_exact(4) {
        assert_eq!((chunk[0], chunk[1], chunk[2]), (255, 255, 255));
    }
}

// --- Cadre NON carré (2026-09-09) : le défaut vu par Jay — « le cercle n'est pas un
// cercle » sur sa caméra 16:9. Ces tests le ferment. ---

#[test]
fn should_keep_the_corner_of_a_rounded_mask_transparent_on_a_wide_frame() {
    // Même preuve que sur cadre carré (plus haut), reportée sur un cadre large : le coin
    // LITTÉRAL du cadre reste toujours hors de la forme, quel que soit le rayon — jamais
    // ambigu, contrairement à un point pris pile sur le bord de la forme.
    let (w, h) = (128, 64);
    let buf = generate_rounded_mask_rgba(MASK_RADIUS_MAX, w, h);
    let (_, _, _, a) = pixel(&buf, w, 0, 0);
    assert_eq!(a, 0);
}

#[test]
fn should_leave_the_long_side_of_a_circle_transparent_beyond_the_diameter() {
    // Le grand côté du cadre n'est PAS étiré pour remplir le cercle : au-delà du rayon
    // (calculé sur le petit côté), le coin du cadre reste transparent.
    let (w, h) = (128, 64);
    let buf = generate_circle_mask_rgba(w, h);
    let (_, _, _, a) = pixel(&buf, w, 0, h / 2);
    assert_eq!(a, 0);
}

#[test]
fn should_be_fully_opaque_at_the_center_of_a_circle_mask() {
    let (w, h) = (128, 64);
    let buf = generate_circle_mask_rgba(w, h);
    assert_eq!(pixel(&buf, w, w / 2, h / 2), (255, 255, 255, 255));
}

#[test]
fn should_leave_all_four_corners_transparent_on_a_square_circle_mask() {
    // Sur un cadre carré, un cercle inscrit laisse ses quatre coins dehors — un carré
    // stretché en cercle (l'ancien défaut) les laisserait dehors aussi, mais un cercle
    // qui aurait dérivé vers une ellipse n'en laisserait plus que deux.
    let buf = generate_circle_mask_rgba(SIZE, SIZE);
    for (x, y) in [(0, 0), (SIZE - 1, 0), (0, SIZE - 1), (SIZE - 1, SIZE - 1)] {
        let (_, _, _, a) = pixel(&buf, SIZE, x, y);
        assert_eq!(a, 0, "coin ({x},{y})");
    }
}

// --- `scaled_mask_size` (2026-09-09, relecture indépendante avant publication : signalé
// comme non testé alors qu'il décide de la forme réellement envoyée à l'utilisateur). ---

#[test]
fn should_keep_the_size_untouched_when_already_under_the_ceiling() {
    assert_eq!(scaled_mask_size(320, 240), (320, 240));
    assert_eq!(
        scaled_mask_size(MASK_MAX_DIMENSION, MASK_MAX_DIMENSION),
        (MASK_MAX_DIMENSION, MASK_MAX_DIMENSION)
    );
}

#[test]
fn should_cap_the_longest_side_at_the_ceiling() {
    let (w, h) = scaled_mask_size(3840, 2160);
    assert_eq!(
        w.max(h),
        MASK_MAX_DIMENSION,
        "le plus grand côté doit toucher le plafond"
    );
}

#[test]
fn should_preserve_the_aspect_ratio_when_scaling_down() {
    // 3840×2160 = 16:9 exact. Une réduction qui déforme le rapport reproduirait, un cran
    // plus tôt dans la chaîne, exactement le défaut que ce module corrige.
    let (w, h) = scaled_mask_size(3840, 2160);
    let original_ratio = 3840.0 / 2160.0;
    let scaled_ratio = w as f32 / h as f32;
    assert!(
        (original_ratio - scaled_ratio).abs() < 0.01,
        "rapport d'origine {original_ratio} vs réduit {scaled_ratio}"
    );
}

#[test]
fn should_scale_down_a_tall_frame_on_its_own_longest_side() {
    // Un cadre PLUS HAUT que large (portrait/vertical) doit être plafonné sur la HAUTEUR,
    // pas systématiquement sur la largeur.
    let (w, h) = scaled_mask_size(1080, 1920);
    assert_eq!(h, MASK_MAX_DIMENSION);
    assert!(w < MASK_MAX_DIMENSION);
}

#[test]
fn should_never_produce_a_zero_dimension() {
    // Une dimension d'entrée nulle (source pas encore prête, lue par erreur) ne doit
    // jamais produire une image de largeur ou hauteur 0 — `image::RgbaImage::from_raw`
    // le refuserait, et la génération échouerait sans qu'aucun masque ne soit jamais posé.
    assert_eq!(scaled_mask_size(0, 0), (1, 1));
    let (w, h) = scaled_mask_size(0, 1080);
    assert!(w >= 1 && h >= 1);
}
