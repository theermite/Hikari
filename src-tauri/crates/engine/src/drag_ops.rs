//! Mouse-driven camera placement (B7): the rectangle cache, hit testing, cursor shape, and
//! the move/resize gestures themselves — the drag group of `App`'s command handlers.

use anyhow::Result;
use libobs_wrapper::scenes::{ObsSceneItemRef, SceneItemTrait};
use libobs_wrapper::sources::ObsSourceRef;
use winit::window::CursorIcon;

use crate::{App, DragState, ItemRect, camera, emit, outline, sources};
use hikari_protocol::EngineMessage;

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
        if self.obs.as_ref().is_some_and(|obs| obs.item_rects.is_some()) {
            return self.obs.as_ref().map_or(&[], |obs| {
                obs.item_rects.as_deref().unwrap_or(&[])
            });
        }
        let Some(obs) = &mut self.obs else { return &[] };
        let runtime = obs.context.runtime().clone();
        let scene = obs.active_scene.clone();

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
                    .filter(|source| {
                        !obs.locked.contains(&(scene.clone(), source.name.clone()))
                    })
                    .map(|source| (source.name.clone(), &source.item))
                    .collect()
            })
            .unwrap_or_default();
        let camera_locked = obs
            .locked
            .contains(&(scene.clone(), camera::CAMERA_SOURCE_NAME.to_string()));
        if let Some(item) = obs.camera_items.get(&scene).filter(|_| !camera_locked) {
            items.push((camera::CAMERA_SOURCE_NAME.to_string(), item));
        }

        let mut measured: Vec<(i32, ItemRect)> = items
            .into_iter()
            .filter_map(|(name, item)| {
                let (base_w, base_h) = sources::item_base_size(&runtime, item).ok()?;
                if base_w == 0 || base_h == 0 {
                    // Source pas encore prête : rien à attraper, plutôt qu'un rectangle
                    // inventé sur une taille supposée.
                    return None;
                }
                let position = item.get_source_position().ok()?;
                let scale = item.get_source_scale().ok()?;
                let order = sources::order_position(&runtime, item).ok()?;
                Some((
                    order,
                    ItemRect {
                        name,
                        x: *position.x(),
                        y: *position.y(),
                        width: base_w as f32 * scale.x(),
                        height: base_h as f32 * scale.y(),
                    },
                ))
            })
            .collect();
        // Trié par la pile RÉELLE du moteur, jamais par notre ordre d'insertion : c'est ce
        // que l'utilisateur voit qui décide quelle source un clic désigne. Décroissant, donc
        // le plus en avant vient en premier.
        measured.sort_by_key(|(order, _)| std::cmp::Reverse(*order));

        obs.item_rects = Some(measured.into_iter().map(|(_, rect)| rect).collect());
        obs.item_rects.as_deref().unwrap_or(&[])
    }

    /// The scene item behind a name, in the active scene.
    fn active_item(&self, name: &str) -> Option<&ObsSceneItemRef<ObsSourceRef>> {
        let obs = self.obs.as_ref()?;
        if name == camera::CAMERA_SOURCE_NAME {
            return obs.camera_items.get(&obs.active_scene);
        }
        obs.scene_sources
            .get(&obs.active_scene)?
            .iter()
            .find(|source| source.name == name)
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
    fn hit_test(&mut self) -> Option<(String, f32, f32, f32, f32, Option<hikari_protocol::Corner>)> {
        let cursor = self.cursor?;
        let (cx, cy) = self.cursor_in_canvas(cursor)?;
        for rect in self.active_item_rects() {
            let (x, y, w, h) = (rect.x, rect.y, rect.width, rect.height);
            let corner =
                hikari_protocol::corner_at(cx, cy, x, y, w, h, hikari_protocol::CORNER_GRAB_MARGIN);
            if corner.is_some() || hikari_protocol::is_inside(cx, cy, x, y, w, h) {
                return Some((rect.name.clone(), x, y, w, h, corner));
            }
        }
        None
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
        let Some((_, _, _, _, _, corner)) = hit else { return CursorIcon::Default };
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
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return };
        let Some((name, x, y, w, h, corner)) = self.hit_test() else { return };
        self.drag = Some(match corner {
            Some(corner) => {
                let (anchor_is_left, anchor_is_top) = corner.anchor_side();
                DragState::Resize {
                    name,
                    anchor_x: if anchor_is_left { x } else { x + w },
                    anchor_y: if anchor_is_top { y } else { y + h },
                    anchor_is_left,
                    anchor_is_top,
                }
            }
            None => DragState::Move { name, grab_offset_x: cx - x, grab_offset_y: cy - y },
        });
    }

    /// Cursor moved during a gesture — applies whichever one is in progress.
    pub(crate) fn continue_drag(&mut self) {
        let Some(cursor) = self.cursor else { return };
        let Some((cx, cy)) = self.cursor_in_canvas(cursor) else { return };
        // Cloné plutôt qu'emprunté : le geste appelle ensuite des méthodes qui empruntent
        // `self` en entier.
        let drag = match &self.drag {
            Some(DragState::Move { name, grab_offset_x, grab_offset_y }) => {
                Some((name.clone(), None, (*grab_offset_x, *grab_offset_y)))
            }
            Some(DragState::Resize { name, anchor_x, anchor_y, anchor_is_left, anchor_is_top }) => {
                Some((
                    name.clone(),
                    Some((*anchor_x, *anchor_y, *anchor_is_left, *anchor_is_top)),
                    (0.0, 0.0),
                ))
            }
            None => None,
        };
        let Some((name, resize, (grab_x, grab_y))) = drag else { return };
        match resize {
            Some((anchor_x, anchor_y, anchor_is_left, anchor_is_top)) => {
                self.apply_resize(&name, cx, anchor_x, anchor_y, anchor_is_left, anchor_is_top)
            }
            None => self.apply_move(&name, cx - grab_x, cy - grab_y),
        }
    }

    /// Puts one source's top-left at `(x, y)` canvas pixels and reports the real result.
    ///
    /// La position passe par l'aimantation : approcher un bord ou un axe central y colle la
    /// source. C'est ce qui rend un cadrage propre atteignable à la souris, sans viser au
    /// pixel — et ça ne coûte rien quand on place volontairement de travers, l'aimantation
    /// ne corrigeant jamais au-delà de sa portée.
    fn apply_move(&mut self, name: &str, x: f32, y: f32) {
        let (x, y) = self.snapped(name, x, y);
        let Some(item) = self.active_item(name) else { return };
        let result = camera::set_camera_position(item, x as i32, y as i32);
        self.report_transform(result);
    }

    /// La position aimantée d'une source, ou la position brute si le cadre ou la taille de
    /// la source sont inconnus — jamais une aimantation devinée sur des dimensions supposées.
    fn snapped(&mut self, name: &str, x: f32, y: f32) -> (f32, f32) {
        let Some((width, height)) = self
            .active_item_rects()
            .iter()
            .find(|rect| rect.name == name)
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
        name: &str,
        cursor_x: f32,
        anchor_x: f32,
        anchor_y: f32,
        anchor_is_left: bool,
        anchor_is_top: bool,
    ) {
        let Some(obs) = &self.obs else { return };
        let runtime = obs.context.runtime().clone();
        let Some(item) = self.active_item(name) else { return };
        let Ok((base_w, base_h)) = sources::item_base_size(&runtime, item) else { return };
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
        let Some(item) = self.active_item(name) else { return };
        let result = camera::set_camera_transform(item, new_x as i32, new_y as i32, scale);
        self.report_transform(result);
    }

    /// Shared tail of both gestures: forget the cached rectangles and report what really
    /// happened (the clamped values, never the requested ones).
    fn report_transform(&mut self, result: Result<(i32, i32, i32)>) {
        let scene = self.obs.as_ref().map(|obs| obs.active_scene.clone()).unwrap_or_default();
        match result {
            Ok((x, y, scale_percent)) => {
                self.scene_layout_changed();
                emit(&EngineMessage::CameraTransform { scene, x, y, scale_percent })
            }
            Err(err) => emit(&EngineMessage::Error { message: err.to_string() }),
        }
    }
}
