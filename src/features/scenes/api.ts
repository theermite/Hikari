// Scenes Tauri bridge (multi-scene, tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { CaptureKind } from "./types";

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
  kind: CaptureKind,
  targetId: string,
  name: string,
): Promise<void> {
  return invoke("add_capture_source", { scene, kind, targetId, name });
}

/** Removes a capture from one scene. Other scenes keep theirs. */
export function removeSource(scene: string, name: string): Promise<void> {
  return invoke("remove_source", { scene, name });
}
