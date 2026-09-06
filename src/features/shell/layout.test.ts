// Tests écrits AVANT le code (TDG).
//
// Ce que ces fonctions existent pour régler, vécu par Jay le 2026-09-06 : il a fermé
// l'onglet Aperçu et n'a plus eu aucun moyen de le rouvrir. La barre latérale n'y menait
// pas, et le glisser-déposer des panneaux est cassé dans ce moteur d'affichage — un
// panneau fermé était perdu jusqu'à la remise à zéro de la disposition.

import { describe, expect, it } from "vitest";
import { COCKPIT_PANELS, missingCockpitPanels } from "./layout";

describe("missingCockpitPanels", () => {
  it("should_name_the_preview_when_it_has_been_closed", () => {
    const present = COCKPIT_PANELS.map((p) => p.id).filter(
      (id) => id !== "preview",
    );

    expect(missingCockpitPanels(present)).toEqual([
      { id: "preview", title: "Aperçu" },
    ]);
  });

  it("should_name_nothing_when_the_cockpit_is_whole", () => {
    expect(missingCockpitPanels(COCKPIT_PANELS.map((p) => p.id))).toEqual([]);
  });

  it("should_name_every_panel_when_the_cockpit_is_empty", () => {
    expect(missingCockpitPanels([])).toEqual(COCKPIT_PANELS);
  });

  it("should_ignore_panels_that_are_not_part_of_the_cockpit", () => {
    // Paramètres s'ouvre depuis la barre latérale et n'appartient pas à la disposition
    // du direct : le rendre « manquant » le rouvrirait sans qu'on l'ait demandé.
    expect(missingCockpitPanels(["settings"]).map((p) => p.id)).not.toContain(
      "settings",
    );
  });

  it("should_carry_the_preview_that_starts_the_engine", () => {
    // L'Aperçu démarre le moteur : le laisser hors de cette liste rendrait sa fermeture
    // silencieusement fatale à tout le reste du cockpit.
    expect(COCKPIT_PANELS.map((p) => p.id)).toContain("preview");
  });
});
