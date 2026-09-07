// Les trois dispositions du cockpit — Préparation, Live, Focus.
//
// Ce que Jay en dit (2026-09-07), et qui fixe leur contenu :
//   — Préparation : « constituer son stream, le mettre en place, créer ses scènes » ;
//   — Live : « une interface lorsque nous sommes en live » ;
//   — Focus : « rester focus sur le live, sur le jeu que nous sommes en train de faire ».
//
// Elles n'agençaient RIEN jusqu'ici : cliquer changeait l'état affiché et rien d'autre.
// Chaque disposition dit désormais quels panneaux du cockpit se montrent.
//
// La maquette tranche le seul cas ambigu : en préparation le chat s'efface, en direct il
// revient (« Préparation : sources, kit de marque et checklist en avant — le chat
// s'efface »).
//
// Modèle PUR : il dit QUOI montrer, jamais COMMENT. Le comment appartient à la coque, qui
// seule possède le système de panneaux.

export type PresetId = "preparation" | "live" | "focus";

export const PRESETS: readonly { id: PresetId; label: string }[] = [
  { id: "preparation", label: "Préparation" },
  { id: "live", label: "Live" },
  { id: "focus", label: "Focus" },
];

/** The default preset a fresh install (or a corrupted/missing saved choice) falls back to. */
export const DEFAULT_PRESET: PresetId = "preparation";

/** Whether `id` is one of the presets Hikari actually knows — guards against a stale/foreign
 * value read back from the persisted store (e.g. an older Hikari version's preset id). */
export function isKnownPreset(id: string): id is PresetId {
  return PRESETS.some((preset) => preset.id === id);
}

/** Resolves the preset to activate from a possibly-stale/missing saved value. Never throws,
 * never returns an unknown id — the one guarantee `should_switch_preset_when_selected` and
 * callers both rely on. */
export function resolvePreset(saved: string | null): PresetId {
  if (saved !== null && isKnownPreset(saved)) {
    return saved;
  }
  return DEFAULT_PRESET;
}

/** Les panneaux que chaque disposition montre. Ce qui n'y est pas se cache — jamais ne se
 * ferme : un panneau fermé perd sa place, et le rouvrir le remonterait. Remonter l'Aperçu
 * relancerait le moteur et couperait la diffusion. */
const SHOWN: Record<PresetId, readonly string[]> = {
  // Tout ce qui sert à MONTER le direct : la carte Préparation apparaît, le chat
  // s'efface — personne ne regarde encore.
  preparation: ["scenes", "preview", "audio", "deck", "prep"],
  // Le direct : le chat revient, la carte Préparation s'efface, et tout reste sous la main.
  live: ["scenes", "preview", "audio", "deck", "chat"],
  // Le strict nécessaire. Les scènes restent — basculer d'un clic est la promesse du
  // produit, et c'est le seul geste qu'on fait encore quand on est pris par le jeu.
  focus: ["scenes", "preview"],
};

/** Si `panelId` se montre dans la disposition `preset`.
 *
 * Un panneau inconnu de la liste se montre : une disposition ne doit jamais faire
 * disparaître un panneau ajouté après elle. L'oubli se verrait, l'effacement non. */
export function showsPanel(preset: PresetId, panelId: string): boolean {
  const shown = SHOWN[preset];
  const connus = new Set(Object.values(SHOWN).flat());
  return connus.has(panelId) ? shown.includes(panelId) : true;
}
