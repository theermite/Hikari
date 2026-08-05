import { describe, expect, it } from "vitest";
import {
  labelFor,
  moveScene,
  orderScenes,
  type SceneLayout,
  validateLabel,
} from "./sceneLayout";
import type { SceneInfo } from "./types";

const scene = (name: string): SceneInfo => ({
  name,
  has_camera: false,
  background_removal: false,
  circle_mask: false,
  sources: [],
});

const EMPTY: SceneLayout = { order: [], labels: {} };

describe("moveScene", () => {
  it("should_move_a_scene_up_when_it_has_a_neighbour_above", () => {
    expect(moveScene(["a", "b", "c"], "b", "up")).toEqual(["b", "a", "c"]);
  });

  it("should_move_a_scene_down_when_it_has_a_neighbour_below", () => {
    expect(moveScene(["a", "b", "c"], "b", "down")).toEqual(["a", "c", "b"]);
  });

  it("should_keep_the_order_unchanged_when_the_scene_is_already_first", () => {
    // Pas d'enroulement : remonter la première scène ne doit pas l'envoyer en bas,
    // sinon un clic de trop réorganise tout dans le dos de l'utilisateur.
    expect(moveScene(["a", "b"], "a", "up")).toEqual(["a", "b"]);
  });

  it("should_keep_the_order_unchanged_when_the_scene_is_already_last", () => {
    expect(moveScene(["a", "b"], "b", "down")).toEqual(["a", "b"]);
  });

  it("should_keep_the_order_unchanged_when_the_scene_is_unknown", () => {
    expect(moveScene(["a", "b"], "absente", "up")).toEqual(["a", "b"]);
  });

  it("should_not_mutate_the_order_it_was_given", () => {
    const original = ["a", "b", "c"];
    moveScene(original, "c", "up");
    expect(original).toEqual(["a", "b", "c"]);
  });
});

describe("orderScenes", () => {
  it("should_follow_the_saved_order_when_every_scene_is_known", () => {
    const scenes = [scene("a"), scene("b"), scene("c")];
    const ordered = orderScenes(scenes, { order: ["c", "a", "b"], labels: {} });
    expect(ordered.map((s) => s.name)).toEqual(["c", "a", "b"]);
  });

  it("should_append_scenes_the_saved_order_never_heard_of", () => {
    // Une scène créée depuis le deck ou une autre session n'est dans aucun ordre
    // sauvegardé — elle doit apparaître quand même, jamais disparaître de la liste.
    const scenes = [scene("a"), scene("nouvelle")];
    const ordered = orderScenes(scenes, { order: ["a"], labels: {} });
    expect(ordered.map((s) => s.name)).toEqual(["a", "nouvelle"]);
  });

  it("should_ignore_saved_order_entries_whose_scene_no_longer_exists", () => {
    const scenes = [scene("a")];
    const ordered = orderScenes(scenes, {
      order: ["supprimee", "a"],
      labels: {},
    });
    expect(ordered.map((s) => s.name)).toEqual(["a"]);
  });

  it("should_keep_the_engine_order_when_nothing_was_ever_saved", () => {
    const scenes = [scene("a"), scene("b")];
    expect(orderScenes(scenes, EMPTY).map((s) => s.name)).toEqual(["a", "b"]);
  });
});

describe("labelFor", () => {
  it("should_show_the_chosen_label_when_the_scene_was_renamed", () => {
    expect(labelFor("main", { order: [], labels: { main: "Départ" } })).toBe(
      "Départ",
    );
  });

  it("should_fall_back_to_the_engine_name_when_never_renamed", () => {
    // Le moteur garde un identifiant fixe : sans étiquette choisie, on montre cet
    // identifiant plutôt qu'un vide inexplicable.
    expect(labelFor("main", EMPTY)).toBe("main");
  });
});

describe("validateLabel", () => {
  const layout: SceneLayout = { order: [], labels: { a: "Jeu" } };

  it("should_accept_a_new_distinct_label", () => {
    expect(validateLabel("Discussion", "b", ["a", "b"], layout)).toBe("ok");
  });

  it("should_reject_a_blank_label", () => {
    expect(validateLabel("   ", "b", ["a", "b"], layout)).toBe("empty");
  });

  it("should_reject_a_label_another_scene_already_shows", () => {
    expect(validateLabel("Jeu", "b", ["a", "b"], layout)).toBe("duplicate");
  });

  it("should_accept_a_scene_keeping_its_own_current_label", () => {
    // Renommer "Jeu" en "Jeu" n'est pas un doublon avec soi-même.
    expect(validateLabel("Jeu", "a", ["a", "b"], layout)).toBe("ok");
  });

  it("should_reject_a_label_that_collides_with_another_scenes_engine_name", () => {
    // "b" n'a pas d'étiquette : son nom affiché EST son identifiant moteur, donc
    // l'étiquette "b" pour une autre scène créerait deux lignes identiques à l'écran.
    expect(validateLabel("b", "a", ["a", "b"], layout)).toBe("duplicate");
  });
});
