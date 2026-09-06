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
 * mixeur et deck dessous (2026-09-05).
 *
 * 3 : le Pré-vol et la Caméra quittent le cockpit (2026-09-06). Le premier s'ouvre depuis
 * la barre latérale ; la seconde est devenue une source parmi les autres. Une disposition
 * du 5 septembre les porte encore, et l'Aperçu de Jay s'y était retrouvé en onglet à côté
 * du Deck — la rebâtir lui rend la répartition de la maquette d'un coup. */
export const LAYOUT_VERSION = 3;

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

/** Un panneau du cockpit : son titre, et OÙ il se replace s'il a été fermé.
 *
 * `anchor` nomme les voisins acceptables, du meilleur au moins bon. Le premier encore
 * ouvert gagne — sans cette liste, un panneau rendu à côté d'un panneau lui-même fermé
 * atterrirait n'importe où. */
interface CockpitPanel {
  id: string;
  title: string;
  anchor: string[];
  direction: "left" | "right" | "above" | "below" | "within";
}

/** La disposition du direct, telle que la maquette la dessine : scènes à gauche, aperçu
 * large au centre, chat à droite, mixeur et deck sous l'aperçu.
 *
 * Le Pré-vol n'en fait PAS partie (Jay, 2026-09-06) : il s'ouvre depuis la barre latérale,
 * qui a son entrée. Deux portes pour un même écran, c'est une de trop — et il occupait une
 * place que la maquette ne lui donne pas.
 *
 * Une seule liste : la disposition par défaut la pose, et la barre latérale la répare. */
export const COCKPIT_PANELS: CockpitPanel[] = [
  { id: "scenes", title: "Scènes", anchor: ["preview"], direction: "left" },
  {
    id: "preview",
    title: "Aperçu",
    anchor: ["scenes"],
    direction: "right",
  },
  { id: "chat", title: "Chat", anchor: ["preview"], direction: "right" },
  {
    id: "audio",
    title: "Audio",
    anchor: ["preview"],
    direction: "below",
  },
  {
    id: "deck",
    title: "Deck",
    anchor: ["audio", "preview"],
    direction: "right",
  },
];

/** Ceux du cockpit qui MANQUENT parmi `present`.
 *
 * POURQUOI cette fonction existe (Jay, 2026-09-06) : il a fermé l'onglet Aperçu et n'a plus
 * eu aucun moyen de le rouvrir — la barre latérale n'y menait pas, et le glisser-déposer
 * des panneaux est cassé dans ce moteur d'affichage. Un panneau fermé était donc perdu
 * jusqu'à la remise à zéro de la disposition. Pire pour l'Aperçu : c'est lui qui démarre le
 * moteur, donc le fermer éteignait tout le reste sans le dire. */
export function missingCockpitPanels(present: string[]): CockpitPanel[] {
  return COCKPIT_PANELS.filter((panel) => !present.includes(panel.id));
}

/** Le voisin contre lequel replacer `panel`, parmi ceux réellement ouverts.
 *
 * Vide quand aucun ne l'est : le panneau est alors posé sans consigne, et c'est le seul
 * cas où on ne peut rien promettre — il n'y a plus de repère dans la fenêtre.
 *
 * POURQUOI (Jay, 2026-09-06) : rendu sans consigne de place, l'Aperçu s'est retrouvé en
 * onglet à côté du Deck au lieu de reprendre le centre. Et comme le glisser-déposer des
 * panneaux est cassé dans ce moteur d'affichage, il n'avait aucun moyen de le remettre. */
export function anchorFor(
  panel: CockpitPanel,
  present: string[],
): string | undefined {
  return panel.anchor.find((candidate) => present.includes(candidate));
}
