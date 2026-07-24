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
