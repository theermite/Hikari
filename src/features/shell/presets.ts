// Cockpit layout presets (B-shell, mono-fenêtre). Préparation/Live/Focus — PET fiche
// F-101. Pure model: WHICH preset is active + how to switch it, no dockview coupling here
// (the actual layout each preset maps to arrives with the real panels in a later brique —
// this is the switching mechanism, tested honestly against what exists today).

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
