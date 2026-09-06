// Tests écrits AVANT le code (TDG).
//
// Ce que ces fonctions existent pour régler, vécu par Jay le 2026-09-06 : il a fermé
// l'onglet Aperçu et n'a plus eu aucun moyen de le rouvrir. La barre latérale n'y menait
// pas, et le glisser-déposer des panneaux est cassé dans ce moteur d'affichage — un
// panneau fermé était perdu jusqu'à la remise à zéro de la disposition.

import { describe, expect, it } from "vitest";
import { anchorFor, COCKPIT_PANELS, missingCockpitPanels } from "./layout";

describe("missingCockpitPanels", () => {
  it("should_name_the_preview_when_it_has_been_closed", () => {
    const present = COCKPIT_PANELS.map((p) => p.id).filter(
      (id) => id !== "preview",
    );

    expect(missingCockpitPanels(present).map((p) => p.id)).toEqual(["preview"]);
  });

  it("should_name_nothing_when_the_cockpit_is_whole", () => {
    expect(missingCockpitPanels(COCKPIT_PANELS.map((p) => p.id))).toEqual([]);
  });

  it("should_name_every_panel_when_the_cockpit_is_empty", () => {
    expect(missingCockpitPanels([])).toEqual(COCKPIT_PANELS);
  });

  it("should_leave_the_preflight_out_of_the_cockpit", () => {
    // Jay, 2026-09-06 : « il y a déjà un menu de pré-vol dans la barre latérale ». Deux
    // portes pour un même écran, c'est une de trop — et il occupait une place que la
    // maquette ne lui donne pas.
    expect(COCKPIT_PANELS.map((p) => p.id)).not.toContain("preflight");
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

describe("anchorFor", () => {
  const preview = COCKPIT_PANELS.find((p) => p.id === "preview");
  const deck = COCKPIT_PANELS.find((p) => p.id === "deck");

  it("should_put_the_preview_back_beside_the_scenes", () => {
    // Rendu sans consigne de place, l'Aperçu s'est retrouvé en onglet à côté du Deck au
    // lieu de reprendre le centre — et le glisser-déposer étant cassé, Jay était coincé.
    expect(anchorFor(preview as never, ["scenes", "chat"])).toBe("scenes");
  });

  it("should_fall_back_to_the_next_neighbour_when_the_first_is_closed_too", () => {
    expect(anchorFor(deck as never, ["preview"])).toBe("preview");
  });

  it("should_prefer_the_first_neighbour_when_both_are_open", () => {
    expect(anchorFor(deck as never, ["preview", "audio"])).toBe("audio");
  });

  it("should_name_no_neighbour_when_none_is_open", () => {
    // Seul cas où l'on ne peut rien promettre : il n'y a plus aucun repère dans la fenêtre.
    expect(anchorFor(preview as never, [])).toBeUndefined();
  });
});
