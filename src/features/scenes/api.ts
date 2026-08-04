// Scenes Tauri bridge (multi-scene, tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";

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
