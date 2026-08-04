// Scene presentation state (multi-scène, étape 3) — the display order and the display
// labels, both owned by the APP, never by the engine.
//
// WHY here and not in the engine: `libobs-wrapper` 9.0.4 caches each scene's name inside
// its own handle and looks scenes up BY that name (`get_scene`). Renaming the underlying
// libobs source would desync the wrapper's own lookup — the scene would still exist but
// become unfindable. Verified by reading the crate source (2026-08-04). So the engine keeps
// one fixed identifier per scene for its whole life, and what the user reads on screen is
// this layer's business. Same reasoning for the order: OBS itself treats scene order as a
// UI concern, so there is nothing to ask the engine for.

import { load, type Store } from "@tauri-apps/plugin-store";
import type { SceneInfo } from "./types";

const STORE_FILE = "scene-layout.json";
const LAYOUT_KEY = "sceneLayout";

/** How the scenes are presented: `order` lists engine names top-to-bottom, `labels` maps an
 * engine name to the name the user chose to read instead. Both are sparse on purpose — a
 * scene missing from either one simply falls back to the engine's own name and position. */
export interface SceneLayout {
  order: string[];
  labels: Record<string, string>;
}

export const EMPTY_LAYOUT: SceneLayout = { order: [], labels: {} };

/** Why a chosen label was refused, or `"ok"`. */
export type LabelVerdict = "ok" | "empty" | "duplicate";

/** Moves `name` one step up or down. Returns a NEW array — never mutates the input, so a
 * React state update is a plain assignment. A scene already at the edge, or absent, yields
 * the order unchanged (no wrap-around: one extra click must never reshuffle the list). */
export function moveScene(
  order: string[],
  name: string,
  direction: "up" | "down",
): string[] {
  const index = order.indexOf(name);
  if (index === -1) return [...order];
  const target = direction === "up" ? index - 1 : index + 1;
  if (target < 0 || target >= order.length) return [...order];
  const next = [...order];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Sorts the engine's scenes by the saved order. Scenes the saved order never heard of
 * (created from a deck, or in another session) keep the engine's own order and land at the
 * end — a scene is never hidden just because the layout file is behind. */
export function orderScenes(
  scenes: SceneInfo[],
  layout: SceneLayout,
): SceneInfo[] {
  const byName = new Map(scenes.map((scene) => [scene.name, scene]));
  const known = layout.order
    .map((name) => byName.get(name))
    .filter((scene): scene is SceneInfo => scene !== undefined);
  const knownNames = new Set(known.map((scene) => scene.name));
  const rest = scenes.filter((scene) => !knownNames.has(scene.name));
  return [...known, ...rest];
}

/** What the user should read for this scene: the label they chose, or the engine's own
 * name if they never renamed it. */
export function labelFor(name: string, layout: SceneLayout): string {
  return layout.labels[name] ?? name;
}

/** Checks a candidate label for `name` against every OTHER scene's displayed name — the
 * comparison is on what is READ on screen, so a label may not collide with another scene's
 * label NOR with another scene's engine name (both appear identically in the list).
 * Renaming a scene to the label it already carries is not a duplicate with itself. */
export function validateLabel(
  candidate: string,
  name: string,
  sceneNames: string[],
  layout: SceneLayout,
): LabelVerdict {
  const trimmed = candidate.trim();
  if (!trimmed) return "empty";
  const taken = sceneNames
    .filter((other) => other !== name)
    .map((other) => labelFor(other, layout));
  return taken.includes(trimmed) ? "duplicate" : "ok";
}

let storePromise: Promise<Store> | null = null;

function getStore(): Promise<Store> {
  storePromise ??= load(STORE_FILE, { autoSave: true });
  return storePromise;
}

/** Loads the saved presentation state. A missing file is not an error — it means "first
 * launch", and the caller falls back to the engine's own order and names. */
export async function loadSceneLayout(): Promise<SceneLayout> {
  const store = await getStore();
  const saved = await store.get<SceneLayout>(LAYOUT_KEY);
  return saved ?? EMPTY_LAYOUT;
}

/** Persists the presentation state. */
export async function saveSceneLayout(layout: SceneLayout): Promise<void> {
  const store = await getStore();
  await store.set(LAYOUT_KEY, layout);
}
