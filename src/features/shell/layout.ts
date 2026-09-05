// Cockpit layout persistence (B-shell, mono-fenêtre). `dockview`'s own `toJSON`/`fromJSON`
// carry the real layout state — this module is a thin, TESTABLE wrapper around WHERE that
// JSON lives (the OS-persisted Tauri store), never reimplementing dockview's own
// serialization. PET fiche B-shell: "Layouts toJSON/fromJSON → presets (persistés
// plugin-store)".

import { load, type Store } from "@tauri-apps/plugin-store";
import type { DockviewApi, SerializedDockview } from "dockview-react";

const STORE_FILE = "cockpit-layout.json";
const LAYOUT_KEY = "layout";
const VERSION_KEY = "layoutVersion";

/** Numéro de la disposition PAR DÉFAUT. À incrémenter quand on la redessine.
 *
 * Pourquoi ce numéro existe : le glisser-déposer des panneaux est cassé dans ce moteur
 * d'affichage (bug connu du projet). L'utilisateur ne peut donc pas réparer lui-même une
 * répartition devenue mauvaise — c'est à nous de la lui rendre. Sans ce numéro, il faudrait
 * écrire une migration par changement, et une disposition ancienne accumulerait les
 * rustines au lieu d'être simplement rebâtie.
 *
 * 2 : répartition de la maquette — scènes à gauche, aperçu large au centre, chat à droite,
 * mixeur et deck dessous (2026-09-05). */
export const LAYOUT_VERSION = 2;

let storePromise: Promise<Store> | null = null;

/** Lazily opens (or creates) the persisted store — one file, reused across calls. */
function getStore(): Promise<Store> {
  storePromise ??= load(STORE_FILE, { autoSave: true });
  return storePromise;
}

/** Serializes the current dockview layout and persists it. Pure boundary: the shape of
 * what's saved is entirely dockview's own `toJSON()` output, never reconstructed by hand. */
export async function saveLayout(api: DockviewApi): Promise<void> {
  const store = await getStore();
  await store.set(LAYOUT_KEY, api.toJSON());
  await store.set(VERSION_KEY, LAYOUT_VERSION);
}

/** Loads a previously saved layout, if any. `null` means "never saved" — not an error;
 * the caller falls back to a default layout (first launch, or a cleared store). */
export async function loadLayout(): Promise<SerializedDockview | null> {
  const store = await getStore();
  const version = await store.get<number>(VERSION_KEY);
  // Une disposition écrite avant la refonte est ÉCARTÉE, jamais rapiécée : elle ne connaît
  // ni les panneaux nés depuis, ni la répartition que la maquette impose. Un numéro absent
  // vaut « d'avant tout numéro » — le cas de tout utilisateur existant.
  if (version !== LAYOUT_VERSION) return null;
  const saved = await store.get<SerializedDockview>(LAYOUT_KEY);
  return saved ?? null;
}

/** Applies a saved layout to a live dockview instance. Isolated from `loadLayout` so the
 * "deserialize into a real api" step is exactly what `should_restore_layout_when_deserialized`
 * exercises — a fake `DockviewApi`-shaped object is enough to prove the wiring, no real
 * dockview mount (no jsdom) needed. */
export function restoreLayout(
  api: DockviewApi,
  layout: SerializedDockview,
): void {
  api.fromJSON(layout);
}
