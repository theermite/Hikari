// Tests écrits AVANT le code (TDG).
//
// Jay, 2026-09-07 : « la densité ne change pas non plus ». Le module publie bien son choix,
// mais l'espace entre les cartes du cockpit est une OPTION du composant de panneaux
// (`gap: 10`), pas une règle de style — aucune feuille CSS ne pouvait donc l'atteindre.
//
// Leçon déjà payée le 2026-09-05, et re-appliquée ici : lire la bibliothèque avant
// d'écrire son contournement. Trois correctifs d'espacement avaient été écrits avant de
// découvrir que l'écart était une option du composant.

import { describe, expect, it } from "vitest";
import { BASE_GAP, gapForDensity } from "./density";

describe("gapForDensity", () => {
  it("should_keep_the_validated_spacing_when_no_choice_was_made", () => {
    // Aucun choix n'est PAS « compact ». Tant que Jay n'a rien demandé, on lui rend la
    // mise en page qu'il a validée — jamais une valeur par défaut qui la modifie.
    expect(gapForDensity(null)).toBe(BASE_GAP);
  });

  it("should_keep_the_validated_spacing_on_the_middle_choice", () => {
    expect(gapForDensity("comfortable")).toBe(BASE_GAP);
  });

  it("should_tighten_on_compact", () => {
    expect(gapForDensity("compact")).toBeLessThan(BASE_GAP);
  });

  it("should_breathe_on_spacious", () => {
    expect(gapForDensity("spacious")).toBeGreaterThan(BASE_GAP);
  });

  it("should_never_return_a_gap_that_glues_the_cards_together", () => {
    // Un écart nul recolle les cartes et efface le fond qui les détache — le défaut exact
    // que Jay a signalé le 2026-09-05 (« on a de l'espace ET une différence de couleur »).
    for (const choix of ["compact", "comfortable", "spacious", null] as const) {
      expect(gapForDensity(choix)).toBeGreaterThanOrEqual(4);
    }
  });

  it("should_stay_on_the_validated_spacing_for_a_choice_it_does_not_know", () => {
    // Une valeur inconnue (version future du module) ne doit pas casser la mise en page.
    expect(gapForDensity("inventé" as never)).toBe(BASE_GAP);
  });
});
