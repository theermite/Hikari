//! Mouse-driven camera placement (B7): the rectangle cache, hit testing, cursor shape, and
//! the move/resize gestures themselves — the drag group of `App`'s command handlers.

use anyhow::Result;
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use winit::window::CursorIcon;

use crate::{camera, emit, outline, scenes, sources, App, DragState, ItemKey, ItemRect};
use hikari_protocol::EngineMessage;

/// L'empilement que voit l'utilisateur, du plus en avant au plus en arrière : d'abord les
/// médias de la scène de recouvrement (dessinée au-dessus, `scenes::OVERLAY_CHANNEL`),
/// puis ceux de la scène active. Chaque liste arrive déjà triée du plus en avant au plus
/// en arrière.
fn stack_front_first(overlay: Vec<ItemRect>, scene: Vec<ItemRect>) -> Vec<ItemRect> {
    overlay.into_iter().chain(scene).collect()
}

/// Le premier rectangle touché par `(cx, cy)` en descendant la pile, et le coin visé s'il y
/// en a un : l'utilisateur vise ce qu'il VOIT, jamais ce qui est caché derrière.
fn first_hit(
    rects: &[ItemRect],
    cx: f32,
    cy: f32,
) -> Option<(&ItemRect, Option<hikari_protocol::Corner>)> {
    rects.iter().find_map(|rect| {
        let (x, y, w, h) = (rect.x, rect.y, rect.width, rect.height);
        let corner =
            hikari_protocol::corner_at(cx, cy, x, y, w, h, hikari_protocol::CORNER_GRAB_MARGIN);
        (corner.is_some() || hikari_protocol::is_inside(cx, cy, x, y, w, h))
            .then_some((rect, corner))
    })
}

/// Mesure chaque source de `scene` et rend ses rectangles, du plus en avant au plus en
/// arrière selon la pile RÉELLE du moteur, jamais notre ordre d'insertion : ce que
/// l'utilisateur voit décide quelle source un clic désigne.
fn measure_items(
    runtime: &libobs_wrapper::runtime::ObsRuntime,
    scene: &str,
    items: Vec<(String, &ObsSceneItemRef<ObsSourceRef>)>,
) -> Vec<ItemRect> {
    let mut measured: Vec<(i32, ItemRect)> = items
        .into_iter()
        .filter_map(|(name, item)| {
            let (base_w, base_h) = sources::item_base_size(runtime, item).ok()?;
            if base_w == 0 || base_h == 0 {
                // Source pas encore prête : rien à attraper, plutôt qu'un rectangle
                // inventé sur une taille supposée.
                return None;
            }
            let position = item.get_source_position().ok()?;
            let scale = item.get_source_scale().ok()?;
            let order = sources::order_position(runtime, item).ok()?;
            Some((
                order,
                ItemRect {
                    key: ItemKey {
                        scene: scene.to_string(),
                        name,
                    },
                    x: *position.x(),
                    y: *position.y(),
                    width: base_w as f32 * scale.x(),
                    height: base_h as f32 * scale.y(),
                },
            ))
        })
        .collect();
    // Décroissant, donc le plus en avant vient en premier.
    measured.sort_by_key(|(order, _)| std::cmp::Reverse(*order));
    measured.into_iter().map(|(_, rect)| rect).collect()
}

impl App {
    /// Forgets the cached rectangles. Called by every path that moves, resizes, adds,
    /// removes or reorders a source, and by every scene switch — the cache is only exact as
    /// long as no writer forgets this.
    pub(crate) fn scene_layout_changed(&mut self) {
        if let Some(obs) = &mut self.obs {
            obs.item_rects = None;
        }
    }

    /// Every grabbable source of the ACTIVE scene with its rectangle, front-first.
    fn active_item_rects(&mut self) -> &[ItemRect] {
        if self
            .obs
            .as_ref()
            .is_some_and(|obs| obs.item_rects.is_some())
        {
            return self
                .obs
                .as_ref()
                .map_or(&[], |obs| obs.item_rects.as_deref().unwrap_or(&[]));
        }
        // Les caméras de la scène sont relevées AVANT l'emprunt mutable ci-dessous : leur
        // lecture passe par `self`, et les deux emprunts ne peuvent pas coexister.
        let scene = self
            .obs
            .as_ref()
            .map(|obs| obs.active_scene.clone())
            .unwrap_or_default();
        let cameras = self.camera_names_in_scene(&scene);
        let Some(obs) = &mut self.obs else { return &[] };
        let runtime = obs.context.runtime().clone();

        // Camera + captures gathered together: the user sees one stack, not two families.
        //
        // Une source VERROUILLÉE n'entre pas dans cette liste (brique Sources). C'est le seul
        // endroit où le verrou peut vraiment tenir : tout geste souris — saisir, déplacer,
        // redimensionner, et jusqu'au curseur qui change de forme — part de ce test de clic.
        // Le désactiver côté écran laisserait la source attrapable, donc pas verrouillée.
        let mut items: Vec<(String, &ObsSceneItemRef<ObsSourceRef>)> = obs
            .scene_sources
            .get(&scene)
            .map(|list| {
                list.iter()
                    .filter(|source| !obs.locked.contains(&(scene.clone(), source.name.clone())))
                    .map(|source| (source.name.clone(), &source.item))
                    .collect()
            })
            .unwrap_or_default();
        // Chaque caméra de la scène entre dans la pile sous son propre nom, avec son propre
        // verrou : verrouiller l'une ne fige pas les autres.
        for (name, device_id) in cameras {
            if obs.locked.contains(&(scene.clone(), name.clone())) {
                continue;
            }
            if let Some(item) = obs.camera_items.get(&(scene.clone(), device_id)) {
                items.push((name, item));
            }
        }

        // Les médias de la scène de recouvrement, quand ils SE VOIENT : un média caché ne se
        // saisit pas (rien à l'écran à viser), un média verrouillé non plus. Dessinée
        // au-dessus de la scène active, cette scène passe devant dans la pile.
        let overlay_items: Vec<(String, &ObsSceneItemRef<ObsSourceRef>)> =
            if scene == scenes::OVERLAY_SCENE_NAME {
                Vec::new()
            } else {
                let overlay = scenes::OVERLAY_SCENE_NAME.to_string();
                obs.scene_sources
                    .get(&overlay)
                    .map(|list| {
                        list.iter()
                            .filter(|source| {
                                let pair = (overlay.clone(), source.name.clone());
                                !obs.locked.contains(&pair) && !obs.hidden.contains(&pair)
                            })
                            .map(|source| (source.name.clone(), &source.item))
                            .collect()
                    })
                    .unwrap_or_default()
            };

        let wanted = items.len() + overlay_items.len();
        let rects = stack_front_first(
            measure_items(&runtime, scenes::OVERLAY_SCENE_NAME, overlay_items),
            measure_items(&runtime, &scene, items),
        );
        // Une source vient d'être posée et n'a pas encore produit d'image : elle mesure
        // 0×0, donc elle est tombée du calcul ci-dessus. Retenir cette carte incomplète la
        // rendrait inattrapable jusqu'à ce qu'un AUTRE geste vide le cache — vécu par Jay
        // le 2026-09-06 : il devait d'abord déplacer la caméra de derrière pour pouvoir
        // saisir celle qu'il venait d'ajouter.
        //
        // Une carte incomplète est donc utilisée pour ce clic-ci et jetée aussitôt. Le
        // prochain geste remesure, et la source répond dès sa première image.
        if rects.len() == wanted {
            obs.item_rects = Some(rects);
            return obs.item_rects.as_deref().unwrap_or(&[]);
        }
        obs.pending_item_rects = rects;
        &obs.pending_item_rects
    }

    /// The scene item behind a source, in ITS scene — the active one or the overlay.
    fn item_of(&self, key: &ItemKey) -> Option<&ObsSceneItemRef<ObsSourceRef>> {
        let obs = self.obs.as_ref()?;
        if let Some(item) = self.camera_item_by_name(&key.scene, &key.name) {
            return Some(item);
        }
        obs.scene_sources
            .get(&key.scene)?
            .iter()
            .find(|source| source.name == key.name)
            .map(|source| &source.item)
    }

    /// Sets the mouse pointer to match what a click would do right here (B7) — the only
    /// visual clue that a corner is grabbable, since the handles themselves are not drawn.
    /// Left untouched during a gesture: the shape must not flicker while dragging.
    pub(crate) fn update_cursor_icon(&mut self) {
        if self.drag.is_some() {
            return;
        }
        let icon = self.hover_icon();
        if let Some(window) = &self.window {
            window.0.set_cursor(icon);
        }
    }

    /// The front-most source under the cursor, and the corner it is on if any.
    ///
    /// Walks the stack from the top down and stops at the first hit: the user aims at what
    /// they SEE, so a source hidden behind another must never be the one that answers.
    fn hit_test(
        &mut self,
    ) -> Option<(ItemKey, f32, f32, f32, f32, Option<hikari_protocol::Corner>)> {
        let cursor = self.cursor?;
        let (cx, cy) = self.cursor_in_canvas(cursor)?;
        let (rect, corner) = first_hit(self.active_item_rects(), cx, cy)?;
        Some((
            rect.key.clone(),
            rect.x,
            rect.y,
            rect.width,
            rect.height,
            corner,
        ))
    }

    /// Which pointer shape the current cursor position calls for, and — même geste — le
    /// liseré qui entoure la source visée. Les deux répondent à la même question : « laquelle
    /// vais-je saisir ». Les séparer les ferait fatalement diverger.
    fn hover_icon(&mut self) -> CursorIcon {
        let hit = self.hit_test();
        match &hit {
            Some((_, x, y, w, h, _)) => {
                let canvas = self
                    .obs
                    .as_ref()
                    .and_then(|obs| camera::canvas_size(obs.context.runtime()).ok());
                match canvas {
                    Some(canvas) => outline::show(*x, *y, *w, *h, canvas),
                    None => outline::hide(),
                }
            }
            None => outline::hide(),
        }
        let Some((_, _, _, _, _, corner)) = hit else {
            return CursorIcon::Default;
        };
        match corner {
            // The double-headed diagonal arrows Windows itself uses for a corner resize:
            // "↘↖" on the two corners of one diagonal, "↙↗" on the other.
            Some(hikari_protocol::Corner::TopLeft | hikari_protocol::Corner::BottomRight) => {
                CursorIcon::NwseResize
            }
            Some(hikari_protocol::Corner::TopRight | hikari_protocol::Corner::BottomLeft) => {
                CursorIcon::NeswResize
            }
            None => CursorIcon::Move,
        }
    }

    /// Turns a cursor position in the preview into canvas coordinates. `None` while libobs
    /// video is not initialized — no guessed canvas size, ever.
    fn cursor_in_canvas(&mut self, cursor: (f32, f32)) -> Option<(f32, f32)> {
        let obs = self.obs.as_mut()?;
        let (canvas_w, canvas_h) = camera::canvas_size(obs.context.runtime()).ok()?;
        Some(hikari_protocol::window_to_canvas(
            cursor.0,
            cursor.1,
            self.fitted.0,
            self.fitted.1,
            canvas_w,
            canvas_h,
        ))
    }

    /// Left button pressed: start a resize if the cursor is on a corner of the camera, a
    /// move if it is anywhere else on it (B7, souris). A press off the camera starts
    /// nothing — the rest of the canvas is not interactive yet.
    pub(crate) fn begin_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else {
            return;
        };
        let Some((key, x, y, w, h, corner)) = self.hit_test() else {
            return;
        };
        self.drag = Some(match corner {
            Some(corner) => {
                let (anchor_is_left, anchor_is_top) = corner.anchor_side();
                DragState::Resize {
                    key,
                    anchor_x: if anchor_is_left { x } else { x + w },
                    anchor_y: if anchor_is_top { y } else { y + h },
                    anchor_is_left,
                    anchor_is_top,
                }
            }
            None => DragState::Move {
                key,
                grab_offset_x: cx - x,
                grab_offset_y: cy - y,
            },
        });
    }

    /// Cursor moved during a gesture — applies whichever one is in progress.
    pub(crate) fn continue_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else {
            return;
        };
        // Cloné plutôt qu'emprunté : le geste appelle ensuite des méthodes qui empruntent
        // `self` en entier.
        let drag = match &self.drag {
            Some(DragState::Move {
                key,
                grab_offset_x,
                grab_offset_y,
            }) => Some((key.clone(), None, (*grab_offset_x, *grab_offset_y))),
            Some(DragState::Resize {
                key,
                anchor_x,
                anchor_y,
                anchor_is_left,
                anchor_is_top,
            }) => Some((
                key.clone(),
                Some((*anchor_x, *anchor_y, *anchor_is_left, *anchor_is_top)),
                (0.0, 0.0),
            )),
            None => None,
        };
        let Some((key, resize, (grab_x, grab_y))) = drag else {
            return;
        };
        match resize {
            Some((anchor_x, anchor_y, anchor_is_left, anchor_is_top)) => {
                self.apply_resize(&key, cx, anchor_x, anchor_y, anchor_is_left, anchor_is_top)
            }
            None => self.apply_move(&key, cx - grab_x, cy - grab_y),
        }
    }

    /// Puts one source's top-left at `(x, y)` canvas pixels and reports the real result.
    ///
    /// La position passe par l'aimantation : approcher un bord ou un axe central y colle la
    /// source. C'est ce qui rend un cadrage propre atteignable à la souris, sans viser au
    /// pixel — et ça ne coûte rien quand on place volontairement de travers, l'aimantation
    /// ne corrigeant jamais au-delà de sa portée.
    fn apply_move(&mut self, key: &ItemKey, x: f32, y: f32) {
        let (x, y) = self.snapped(key, x, y);
        let Some(item) = self.item_of(key) else {
            return;
        };
        let result = camera::set_camera_position(item, x as i32, y as i32);
        self.report_transform(key, result);
    }

    /// La position aimantée d'une source, ou la position brute si le cadre ou la taille de
    /// la source sont inconnus — jamais une aimantation devinée sur des dimensions supposées.
    fn snapped(&mut self, key: &ItemKey, x: f32, y: f32) -> (f32, f32) {
        let Some((width, height)) = self
            .active_item_rects()
            .iter()
            .find(|rect| rect.key == *key)
            .map(|rect| (rect.width, rect.height))
        else {
            return (x, y);
        };
        let Some(obs) = &self.obs else { return (x, y) };
        let Ok((canvas_w, canvas_h)) = camera::canvas_size(obs.context.runtime()) else {
            return (x, y);
        };
        hikari_protocol::snap_position(x, y, width, height, canvas_w, canvas_h)
    }

    /// Resizes one source so the dragged corner follows the cursor while the anchor corner
    /// stays pinned. The scale comes from the horizontal distance alone, so the source's
    /// aspect ratio is kept — a squashed image is never what the user meant.
    fn apply_resize(
        &mut self,
        key: &ItemKey,
        cursor_x: f32,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    ) {
        let Some(obs) = &self.obs else { return };
        let runtime = obs.context.runtime().clone();
        let Some(item) = self.item_of(key) else {
            return;
        };
        let Ok((base_w, base_h)) = sources::item_base_size(&runtime, item) else {
            return;
        };
        if base_w == 0 || base_h == 0 {
            return;
        }
        let scale = hikari_protocol::clamp_camera_scale(hikari_protocol::resize_scale(
            anchor_x, cursor_x, base_w,
        ));
        let (new_x, new_y) = hikari_protocol::resize_box(
            anchor_x,
            anchor_y,
            anchor_is_left,
            anchor_is_top,
            base_w as f32 * scale,
            base_h as f32 * scale,
        );
        let Some(item) = self.item_of(key) else {
            return;
        };
        let result = camera::set_camera_transform(item, new_x as i32, new_y as i32, scale);
        self.report_transform(key, result);
    }

    /// Shared tail of both gestures: forget the cached rectangles and report what really
    /// happened (the clamped values, never the requested ones).
    ///
    /// Appelé à CHAQUE mouvement de souris pendant un glissement — donc des dizaines de fois
    /// par seconde, sur n'importe quelle source. Chercher un identifiant de caméra pour un
    /// texte ou une capture d'écran ne pouvait que rater, et ratait bruyamment : la trace de
    /// diagnostic prévue pour un vrai refus de retrait (2026-09-06) s'est mise à tourner en
    /// boucle sur une source texte qu'on déplaçait, 431 fois en une session (Jay, 2026-09-07).
    ///
    /// La question « est-ce une caméra ? » se pose donc AVANT de demander son identifiant,
    /// avec la même fonction qui répond déjà oui/non ailleurs dans ce fichier.
    fn report_transform(&mut self, key: &ItemKey, result: Result<(i32, i32, i32)>) {
        let scene = key.scene.clone();
        let device_id = if self.camera_item_by_name(&scene, &key.name).is_some() {
            self.camera_device_id_by_name(&scene, &key.name)
        } else {
            String::new()
        };
        match result {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform {
                    device_id,
                    scene,
                    x,
                    y,
                    scale_percent,
                })
            }
            Err(err) => emit(&EngineMessage::Error {
                message: err.to_string(),
            }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rect(scene: &str, name: &str, x: f32) -> ItemRect {
        ItemRect {
            key: ItemKey {
                scene: scene.into(),
                name: name.into(),
            },
            x,
            y: 0.0,
            width: 100.0,
            height: 100.0,
        }
    }

    #[test]
    fn should_answer_with_the_overlay_media_when_it_covers_a_scene_source() {
        // DSK est dessinée au-dessus de la scène active : ce que l'utilisateur VOIT devant
        // est ce qu'un clic désigne, même si une source de la scène est dessous.
        let stack = stack_front_first(
            vec![rect("DSK", "follow", 0.0)],
            vec![rect("main", "Krom Kam", 0.0)],
        );

        let (hit, _) = first_hit(&stack, 50.0, 50.0).expect("un clic sur les deux touche");

        assert_eq!(hit.key.scene, "DSK");
    }

    #[test]
    fn should_keep_two_sources_with_the_same_name_in_different_scenes_apart() {
        // Un média d'alerte « follow » et une source « follow » de la scène active existent
        // côte à côte : saisir l'un ne doit jamais déplacer l'autre.
        let stack = stack_front_first(
            vec![rect("DSK", "follow", 0.0)],
            vec![rect("main", "follow", 500.0)],
        );

        let (hit, _) = first_hit(&stack, 550.0, 50.0).expect("la source de main est touchée");

        assert_eq!(hit.key.scene, "main");
    }

    #[test]
    fn should_hit_nothing_off_every_source() {
        let stack = stack_front_first(vec![], vec![rect("main", "Krom Kam", 0.0)]);

        assert!(first_hit(&stack, 900.0, 900.0).is_none());
    }
}
