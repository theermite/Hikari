// Tests écrits AVANT la correction (TDG).
//
// Le défaut vu par Jay le 2026-09-07 : « Je vois bien le bouton d'adaptation morphique,
// mais il n'ouvre absolument rien. Il est juste là, en décoration. »
//
// Le bouton n'était PAS décoratif : c'est le vrai composant du module, et il ouvrait bien
// son panneau. Le panneau s'ouvre sous le bouton — donc hors de la carte de la barre du
// haut — et cette carte coupe tout ce qui dépasse d'elle pour tenir ses coins arrondis.
// Le panneau était donc découpé à 100 %, à chaque ouverture, en silence.
//
// Ce que ces tests fixent : la règle de placement, pas le pixel. Un panneau qui s'ouvre
// vers l'extérieur ne peut jamais vivre dans un conteneur qui découpe.

import { describe, expect, it } from "vitest";
import { clipsItsOverflow, escapesClipping } from "./morphicPlacement";

describe("clipsItsOverflow", () => {
  it("should_detect_a_container_that_cuts_what_sticks_out", () => {
    expect(
      clipsItsOverflow(
        "m-2.5 mb-0 flex-shrink-0 overflow-hidden rounded-hikari border",
      ),
    ).toBe(true);
  });

  it("should_detect_the_other_ways_of_cutting", () => {
    // `overflow-clip` et `overflow-y-hidden` coupent tout autant. N'en connaître qu'une
    // ferait passer la garde à côté du prochain cas.
    expect(clipsItsOverflow("overflow-clip rounded-hikari")).toBe(true);
    expect(clipsItsOverflow("overflow-y-hidden")).toBe(true);
    expect(clipsItsOverflow("overflow-x-hidden")).toBe(true);
  });

  it("should_leave_an_ordinary_container_alone", () => {
    expect(clipsItsOverflow("flex h-12 items-center gap-4 px-4")).toBe(false);
    // Piège : « overflow-visible » contient le mot, et ne coupe rien.
    expect(clipsItsOverflow("overflow-visible rounded-hikari")).toBe(false);
  });
});

describe("escapesClipping", () => {
  it("should_refuse_a_button_placed_inside_a_clipping_ancestor", () => {
    // La chaîne va du plus proche au plus lointain. Un SEUL ancêtre qui coupe suffit.
    expect(
      escapesClipping([
        "flex h-12 items-center",
        "overflow-hidden rounded-hikari",
      ]),
    ).toBe(false);
  });

  it("should_accept_a_button_whose_ancestors_never_cut", () => {
    expect(
      escapesClipping([
        "absolute right-4 z-30",
        "relative m-2.5 flex-shrink-0",
      ]),
    ).toBe(true);
  });

  it("should_accept_a_button_with_no_ancestor_at_all", () => {
    expect(escapesClipping([])).toBe(true);
  });
});
