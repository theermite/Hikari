import type { TextSettings } from "./textSettings";
// Scenes Tauri bridge (multi-scene, tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { SourceKind, SourceOrder } from "./types";

/** Creates a new, empty scene named `name` (`create_scene`, `engine_lifecycle.rs`).
 * Requires the engine running (the Aperçu panel open). */
export function createScene(name: string): Promise<void> {
  return invoke("create_scene", { name });
}

/** Switches the live scene to `name` — an instant cut, never a transition
 * (`switch_scene`, `engine_lifecycle.rs`). Requires the engine running. */
export function switchScene(name: string): Promise<void> {
  return invoke("switch_scene", { name });
}

/** Deletes the scene `name` and everything scene-local it carried, its camera placement and
 * its own filter preferences included (`delete_scene`, `engine_lifecycle.rs`). The shared
 * webcam survives as long as another scene shows it. The engine refuses to delete the last
 * scene, or an unknown one, and answers with an error rather than obeying. */
export function deleteScene(name: string): Promise<void> {
  return invoke("delete_scene", { name });
}

/** Asks the engine what the machine can capture right now — games running, windows open,
 * screens plugged in. Re-asked every time the list is shown: a game launched a minute ago
 * must appear without restarting anything. */
export function listCaptureTargets(): Promise<void> {
  return invoke("list_capture_targets");
}

/** Adds a game, window or screen capture into `scene`, named `name`. `targetId` comes from
 * the engine's own list, never guessed. */
export function addCaptureSource(
  scene: string,
  kind: SourceKind,
  targetId: string,
  name: string,
): Promise<void> {
  return invoke("add_capture_source", { scene, kind, targetId, name });
}

/** Removes a capture from one scene. Other scenes keep theirs. */
export function removeSource(scene: string, name: string): Promise<void> {
  return invoke("remove_source", { scene, name });
}

/** Places a source exactly, without the mouse — ce qui rend une session rejouable au
 * lancement suivant. */
export function setSourceTransform(
  scene: string,
  name: string,
  x: number,
  y: number,
  scalePercent: number,
): Promise<void> {
  return invoke("set_source_transform", { scene, name, x, y, scalePercent });
}

/** Fige une source à la souris dans cette scène, ou la libère. Le moteur cesse alors de la
 * voir au test de clic : ni déplacement, ni redimensionnement. Elle reste visible,
 * réordonnable et supprimable. */
export function setSourceLocked(
  scene: string,
  name: string,
  locked: boolean,
): Promise<void> {
  return invoke("set_source_locked", { scene, name, locked });
}

/** Montre ou cache `name` dans `scene`, sans la retirer.
 *
 * Le geste du direct, celui de la maquette : masquer une source le temps d'une
 * manipulation puis la remontrer. Elle garde son cadrage, ses filtres et sa place dans la
 * pile — c'est ce qui le distingue du retrait, qui est une décision. */
export function setSourceVisible(
  scene: string,
  name: string,
  visible: boolean,
): Promise<void> {
  return invoke("set_source_visible", { scene, name, visible });
}

/** Moves a source one step in front of, or behind, the others in its scene — which source
 * hides which is a composition decision, so it belongs to the scene. */
export function reorderSource(
  scene: string,
  name: string,
  direction: SourceOrder,
): Promise<void> {
  return invoke("reorder_source", { scene, name, direction });
}

/** Pose l'apparence d'une source texte : police, taille, couleur, contour, alignement.
 *
 * Ne dit rien du TEXTE lui-même — le moteur fusionne ce qu'on lui nomme avec ce qu'il a
 * déjà, donc le contenu reste intact. */
export function setTextSettings(
  scene: string,
  name: string,
  settings: TextSettings,
): Promise<void> {
  return invoke("set_text_settings", { scene, name, settings });
}

/** Ouvre les réglages d'une source dans une vraie fenêtre séparée — déplaçable, comme dans
 * OBS (Jay, 2026-09-07 : « c'est absolument contre-intuitif [...] c'est une fenêtre qui
 * apparaît pour que l'on puisse régler »). Ramène au premier plan celle qui existe déjà
 * pour cette source plutôt que d'en ouvrir une deuxième — voir `settings_window.rs`.
 *
 * `initial` porte l'état de départ pour ce que le moteur ne rapporte pas lui-même
 * (l'apparence d'un texte) ; absent pour une caméra, dont l'état vient entièrement du
 * moteur. */
export function openSettingsWindow(
  kind: "text" | "camera",
  scene: string,
  name: string,
  initial?: { text: string; settings: TextSettings },
): Promise<void> {
  return invoke("open_settings_window", {
    kind,
    scene,
    name,
    initial: initial ? JSON.stringify(initial) : null,
  });
}
