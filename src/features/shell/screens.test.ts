// Tests écrits AVANT le code de la coque (TDG).
//
// Ce que ces tests fixent, et que j'avais mal compris : la barre latérale change
// l'INTERFACE ENTIÈRE, elle n'ouvre pas un panneau dans le cockpit (Jay, 2026-09-07).

import { describe, expect, it } from "vitest";
import { DEFAULT_SCREEN, SCREENS, screenFor } from "./screens";

describe("screenFor", () => {
  it("should_open_the_cockpit_when_nothing_has_been_chosen", () => {
    expect(screenFor(null).id).toBe(DEFAULT_SCREEN);
  });

  it("should_open_the_screen_that_was_asked_for", () => {
    expect(screenFor("preflight").label).toBe("Pré-vol");
  });

  it("should_never_leave_the_main_area_empty", () => {
    // Une zone principale vide serait le seul état dont l'utilisateur ne pourrait pas
    // sortir : la barre latérale resterait là, mais il ne saurait pas ce qu'il regarde.
    expect(screenFor("un-ecran-qui-n-existe-pas").id).toBe(DEFAULT_SCREEN);
  });
});

describe("SCREENS", () => {
  it("should_treat_the_cockpit_as_one_screen_among_others", () => {
    // LE point que j'avais faux : le cockpit n'est pas l'application, il en est une pièce.
    expect(SCREENS.filter((screen) => screen.id === "cockpit")).toHaveLength(1);
    expect(SCREENS.length).toBeGreaterThan(1);
  });

  it("should_name_the_three_screens_that_really_exist", () => {
    const construits = SCREENS.filter((screen) => screen.built).map(
      (s) => s.id,
    );

    expect(construits).toEqual(["preflight", "cockpit", "settings"]);
  });

  it("should_say_what_each_unbuilt_screen_will_do", () => {
    // La phrase sert à l'annonce « à venir ». Une annonce vide ne renseigne personne.
    for (const screen of SCREENS.filter((s) => !s.built)) {
      expect(screen.what.length, screen.id).toBeGreaterThan(10);
    }
  });

  it("should_give_every_screen_its_own_identifier", () => {
    const ids = SCREENS.map((screen) => screen.id);

    expect(new Set(ids).size).toBe(ids.length);
  });
});
