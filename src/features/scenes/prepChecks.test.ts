// Tests écrits AVANT le composant (TDG).
//
// Ce que ces points de contrôle existent pour éviter : démarrer un direct sur une scène
// vide, ou avec une source qu'on avait cachée et oubliée. La maquette montre trois points
// inventés ; ceux-ci sont mesurés sur l'état réel du moteur.

import { describe, expect, it } from "vitest";
import { prepChecks } from "./prepChecks";
import type { SceneInfo, SceneSourceInfo } from "./types";

function source(over: Partial<SceneSourceInfo> = {}): SceneSourceInfo {
  return {
    name: "Capture",
    kind: "monitor_capture",
    source_kind: "monitor",
    target_id: "ecran-1",
    x: 0,
    y: 0,
    scale_percent: 100,
    locked: false,
    background_removal: false,
    circle_mask: false,
    visible: true,
    ...over,
  };
}

function scene(name: string, sources: SceneSourceInfo[]): SceneInfo {
  return { name, has_camera: false, sources };
}

const etat = (checks: ReturnType<typeof prepChecks>, id: string) =>
  checks.find((check) => check.id === id)?.state;

describe("prepChecks", () => {
  it("should_say_it_does_not_know_before_the_engine_answers", () => {
    // « On ne sait pas » n'est pas « c'est bon ». Les confondre fait démarrer un direct
    // sur une scène vide en toute confiance.
    for (const check of prepChecks(null, null)) {
      expect(check.state, check.id).toBe("inconnu");
    }
  });

  it("should_warn_when_the_live_scene_has_nothing_in_it", () => {
    const checks = prepChecks([scene("main", [])], "main");

    expect(etat(checks, "scene")).toBe("attention");
    expect(checks.find((c) => c.id === "scene")?.fix).not.toBe("");
  });

  it("should_be_content_when_the_live_scene_carries_something", () => {
    const checks = prepChecks([scene("main", [source()])], "main");

    expect(etat(checks, "scene")).toBe("ok");
  });

  it("should_count_the_cameras_that_are_really_there", () => {
    const checks = prepChecks(
      [
        scene("main", [
          source({ name: "Krom Kam", source_kind: "camera" }),
          source({ name: "USB Camera", source_kind: "camera" }),
        ]),
      ],
      "main",
    );

    expect(etat(checks, "camera")).toBe("ok");
    expect(checks.find((c) => c.id === "camera")?.label).toContain("2 caméras");
  });

  it("should_not_scold_a_scene_that_has_no_camera_on_purpose", () => {
    // Un écran d'attente ou un partage d'écran n'a pas de caméra, et c'est voulu. Ce
    // point renseigne, il ne réprimande pas.
    const checks = prepChecks([scene("Pause", [source()])], "Pause");

    expect(etat(checks, "camera")).toBe("inconnu");
  });

  it("should_warn_about_a_source_that_was_hidden_and_forgotten", () => {
    // LE piège du direct : une source cachée ne manque à personne jusqu'à ce que les
    // spectateurs la réclament.
    const checks = prepChecks(
      [scene("main", [source({ name: "Overlay", visible: false })])],
      "main",
    );

    expect(etat(checks, "sources")).toBe("attention");
    expect(checks.find((c) => c.id === "sources")?.fix).toContain("Overlay");
  });

  it("should_look_at_the_LIVE_scene_and_no_other", () => {
    // Une autre scène bien remplie ne dit rien de celle qui diffuse.
    const checks = prepChecks(
      [scene("main", []), scene("Jeu", [source(), source()])],
      "main",
    );

    expect(etat(checks, "scene")).toBe("attention");
  });
});
