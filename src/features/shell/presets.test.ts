import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRESET,
  isKnownPreset,
  PRESETS,
  resolvePreset,
  showsPanel,
} from "./presets";

describe("presets", () => {
  it("should_switch_preset_when_selected", () => {
    expect(resolvePreset("live")).toBe("live");
    expect(resolvePreset("focus")).toBe("focus");
    expect(resolvePreset("preparation")).toBe("preparation");
  });

  it("should_fall_back_to_default_when_saved_value_is_unknown", () => {
    // A stale/foreign value (e.g. a future Hikari version's new preset id read by an older
    // build) must never propagate as-is — silently falling back is the safe behavior.
    expect(resolvePreset("some-future-preset")).toBe(DEFAULT_PRESET);
  });

  it("should_fall_back_to_default_when_nothing_was_ever_saved", () => {
    expect(resolvePreset(null)).toBe(DEFAULT_PRESET);
  });

  it("should_recognize_exactly_the_declared_presets", () => {
    for (const preset of PRESETS) {
      expect(isKnownPreset(preset.id)).toBe(true);
    }
    expect(isKnownPreset("not-a-real-preset")).toBe(false);
  });
});

describe("showsPanel", () => {
  it("should_hide_the_chat_while_preparing", () => {
    // La maquette le dit : « Préparation : sources, kit de marque et checklist en avant —
    // le chat s'efface ». Personne ne regarde encore.
    expect(showsPanel("preparation", "chat")).toBe(false);
    expect(showsPanel("live", "chat")).toBe(true);
  });

  it("should_keep_the_preview_in_every_disposition", () => {
    // L'aperçu porte le moteur : le cacher partout reviendrait à éteindre l'application.
    for (const preset of PRESETS) {
      expect(showsPanel(preset.id, "preview"), preset.id).toBe(true);
    }
  });

  it("should_keep_scene_switching_even_in_focus", () => {
    // Basculer de scène d'un clic est la promesse du produit, et c'est le seul geste
    // qu'on fait encore quand on est pris par le jeu.
    expect(showsPanel("focus", "scenes")).toBe(true);
  });

  it("should_strip_focus_down_to_the_essentials", () => {
    expect(showsPanel("focus", "chat")).toBe(false);
    expect(showsPanel("focus", "deck")).toBe(false);
    expect(showsPanel("focus", "audio")).toBe(false);
  });

  it("should_never_hide_a_panel_it_has_never_heard_of", () => {
    // Une disposition ne doit pas faire disparaître un panneau ajouté après elle :
    // l'oubli se verrait, l'effacement non.
    for (const preset of PRESETS) {
      expect(showsPanel(preset.id, "un-panneau-futur"), preset.id).toBe(true);
    }
  });
});
