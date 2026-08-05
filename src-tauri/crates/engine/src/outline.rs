//! Liseré de sélection — le contour qui dit QUELLE source un clic va saisir.
//!
//! POURQUOI c'est dessiné par le moteur et non par l'écran : l'aperçu est une fenêtre native
//! greffée dans l'app (ADR-013), et une fenêtre native passe toujours au-dessus du contenu
//! web (vécu 2026-08-05 avec la fenêtre de réglages audio). Rien de la page ne peut donc
//! recouvrir l'image. Le seul endroit d'où l'on peut dessiner par-dessus, c'est le rendu de
//! libobs lui-même.
//!
//! POURQUOI des atomiques et non un verrou : la fonction de dessin est appelée par le fil
//! GRAPHIQUE de libobs, à chaque image. Un verrou tenu par le fil de l'interface y ferait
//! sauter des images. Le rectangle voyage donc en quatre nombres atomiques, écrits par le
//! fil des événements et lus par celui du dessin — au pire, une image affiche un rectangle
//! d'une image de retard, ce que personne ne voit.

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

use libobs_wrapper::sys as libobs;

/// Épaisseur du trait, en pixels de canevas. Assez fin pour ne pas masquer l'image, assez
/// épais pour rester visible sur un aperçu réduit.
const THICKNESS: f32 = 3.0;

/// Couleur du liseré, en ARGB — l'ambre de la charte Hikari, opaque.
const COLOR: u32 = 0xFF_F5_A6_23;

/// Le rectangle à entourer, partagé entre le fil des événements et celui du dessin.
static VISIBLE: AtomicBool = AtomicBool::new(false);
static RECT: [AtomicU32; 4] = [
    AtomicU32::new(0),
    AtomicU32::new(0),
    AtomicU32::new(0),
    AtomicU32::new(0),
];
/// La taille du canevas, nécessaire pour dessiner dans le même repère que les sources.
static CANVAS: [AtomicU32; 2] = [AtomicU32::new(0), AtomicU32::new(0)];

/// Branche le liseré sur l'aperçu — à faire une seule fois, juste après sa création.
///
/// La fonction de dessin s'ajoute APRÈS celle du wrapper, donc elle passe par-dessus l'image
/// déjà rendue : c'est exactement ce qu'on veut d'un contour.
pub fn attach(
    runtime: &libobs_wrapper::runtime::ObsRuntime,
    display: &libobs_wrapper::display::ObsDisplayRef,
) -> anyhow::Result<()> {
    use anyhow::Context;
    let ptr = display.as_ptr();
    runtime
        .run_with_obs_result(move || unsafe {
            // Safety: sur le fil OBS, l'aperçu vient d'être créé et vit aussi longtemps que
            // le moteur. Le paramètre est nul : l'état voyage par les atomiques ci-dessus,
            // jamais par un pointeur dont il faudrait garantir la survie.
            libobs::obs_display_add_draw_callback(
                ptr.get_ptr(),
                Some(draw),
                std::ptr::null_mut(),
            );
        })
        .context("branchement du liseré sur l'aperçu")
}

/// Annonce le rectangle à entourer, en pixels de canevas.
pub fn show(x: f32, y: f32, width: f32, height: f32, canvas: (u32, u32)) {
    for (slot, value) in RECT.iter().zip([x, y, width, height]) {
        slot.store(value.to_bits(), Ordering::Relaxed);
    }
    CANVAS[0].store(canvas.0, Ordering::Relaxed);
    CANVAS[1].store(canvas.1, Ordering::Relaxed);
    VISIBLE.store(true, Ordering::Relaxed);
}

/// Efface le liseré — le curseur a quitté toute source.
pub fn hide() {
    VISIBLE.store(false, Ordering::Relaxed);
}

/// La fonction que libobs appelle à chaque image, sur son fil graphique.
///
/// # Safety
/// Appelée par libobs pendant son rendu, donc dans un contexte graphique valide. Elle ne
/// touche que des atomiques et l'API graphique, jamais un objet dont la durée de vie
/// dépendrait de l'appelant.
pub unsafe extern "C" fn draw(_param: *mut std::ffi::c_void, _cx: u32, _cy: u32) {
    if !VISIBLE.load(Ordering::Relaxed) {
        return;
    }
    let [x, y, width, height] =
        std::array::from_fn(|i| f32::from_bits(RECT[i].load(Ordering::Relaxed)));
    let (canvas_w, canvas_h) =
        (CANVAS[0].load(Ordering::Relaxed), CANVAS[1].load(Ordering::Relaxed));
    if canvas_w == 0 || canvas_h == 0 || width <= 0.0 || height <= 0.0 {
        return;
    }

    unsafe {
        let effect = libobs::obs_get_base_effect(libobs::obs_base_effect_OBS_EFFECT_SOLID);
        if effect.is_null() {
            return;
        }
        let color_name = c"color";
        let color = libobs::gs_effect_get_param_by_name(effect, color_name.as_ptr());
        if !color.is_null() {
            libobs::gs_effect_set_color(color, COLOR);
        }

        // Même repère que les sources : le canevas entier, origine en haut à gauche. Sans
        // cette projection, le trait se dessinerait dans les coordonnées de la fenêtre et
        // ne collerait pas à la source.
        libobs::gs_projection_push();
        libobs::gs_ortho(0.0, canvas_w as f32, 0.0, canvas_h as f32, -100.0, 100.0);

        let technique = c"Solid";
        while libobs::gs_effect_loop(effect, technique.as_ptr()) {
            // Quatre traits pleins plutôt qu'un rectangle vide : l'API graphique ne dessine
            // que des rectangles pleins, le contour se compose donc de ses quatre côtés.
            for (bar_x, bar_y, bar_w, bar_h) in [
                (x, y, width, THICKNESS),                            // haut
                (x, y + height - THICKNESS, width, THICKNESS),       // bas
                (x, y, THICKNESS, height),                           // gauche
                (x + width - THICKNESS, y, THICKNESS, height),       // droite
            ] {
                libobs::gs_matrix_push();
                libobs::gs_matrix_translate3f(bar_x, bar_y, 0.0);
                libobs::gs_draw_sprite(
                    std::ptr::null_mut(),
                    0,
                    bar_w.max(1.0) as u32,
                    bar_h.max(1.0) as u32,
                );
                libobs::gs_matrix_pop();
            }
        }

        libobs::gs_projection_pop();
    }
}
