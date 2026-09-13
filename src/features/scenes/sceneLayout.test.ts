import { describe, expect, it } from "vitest";
import {
  createCollection,
  deleteCollection,
  labelFor,
  moveScene,
  orderScenes,
  renameCollection,
  type SceneLayout,
  toggleSceneInCollection,
  validateCollectionName,
  validateLabel,
} from "./sceneLayout";
import type { SceneInfo } from "./types";

const scene = (name: string): SceneInfo => ({
  name,
  has_camera: false,
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

describe("collections (maquette : onglets basculables en 1 clic)", () => {
  const EMPTY: SceneLayout = { order: [], labels: {} };

  it("should_start_with_no_collections_when_nothing_was_ever_created", () => {
    // Absent, pas un tableau vide : la distinction compte pour l'écran, qui affiche un
    // bouton « Créer une collection » tant qu'AUCUNE n'existe (Jay, 2026-09-13).
    expect(EMPTY.collections).toBeUndefined();
  });

  describe("validateCollectionName", () => {
    const withOne: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: [] }],
    };

    it("should_accept_a_new_distinct_name", () => {
      expect(validateCollectionName("Interview", withOne)).toBe("ok");
    });

    it("should_reject_a_blank_name", () => {
      expect(validateCollectionName("   ", withOne)).toBe("empty");
    });

    it("should_reject_a_name_another_collection_already_uses", () => {
      expect(validateCollectionName("LoL", withOne)).toBe("duplicate");
    });

    it("should_accept_a_collection_keeping_its_own_current_name", () => {
      expect(validateCollectionName("LoL", withOne, "1")).toBe("ok");
    });
  });

  describe("createCollection", () => {
    it("should_add_a_first_collection_to_an_empty_layout", () => {
      const next = createCollection(EMPTY, "LoL");
      expect(next.collections).toMatchObject([{ name: "LoL", sceneNames: [] }]);
    });

    it("should_give_each_collection_a_distinct_id", () => {
      const next = createCollection(createCollection(EMPTY, "LoL"), "Pause");
      const ids = (next.collections ?? []).map((c) => c.id);
      expect(new Set(ids).size).toBe(2);
    });

    it("should_not_mutate_the_layout_it_was_given", () => {
      const before = { ...EMPTY };
      createCollection(EMPTY, "LoL");
      expect(EMPTY).toEqual(before);
    });
  });

  describe("renameCollection", () => {
    it("should_change_only_the_named_collection", () => {
      const layout: SceneLayout = {
        order: [],
        labels: {},
        collections: [
          { id: "1", name: "LoL", sceneNames: [] },
          { id: "2", name: "Pause", sceneNames: [] },
        ],
      };
      const next = renameCollection(layout, "1", "League of Legends");
      expect(next.collections).toMatchObject([
        { id: "1", name: "League of Legends" },
        { id: "2", name: "Pause" },
      ]);
    });
  });

  describe("deleteCollection", () => {
    it("should_remove_only_the_named_collection", () => {
      const layout: SceneLayout = {
        order: [],
        labels: {},
        collections: [
          { id: "1", name: "LoL", sceneNames: [] },
          { id: "2", name: "Pause", sceneNames: [] },
        ],
      };
      const next = deleteCollection(layout, "1");
      expect(next.collections).toMatchObject([{ id: "2", name: "Pause" }]);
    });

    it("should_leave_the_scenes_themselves_untouched", () => {
      // Une collection est un regroupement de PRÉSENTATION — la supprimer ne doit ni
      // toucher les scènes elles-mêmes, ni exiger la moindre commande au moteur.
      const layout: SceneLayout = {
        order: ["a", "b"],
        labels: {},
        collections: [{ id: "1", name: "LoL", sceneNames: ["a"] }],
      };
      const next = deleteCollection(layout, "1");
      expect(next.order).toEqual(["a", "b"]);
    });
  });

  describe("toggleSceneInCollection", () => {
    const layout: SceneLayout = {
      order: [],
      labels: {},
      collections: [{ id: "1", name: "LoL", sceneNames: ["a"] }],
    };

    it("should_add_a_scene_that_is_not_yet_in_the_collection", () => {
      const next = toggleSceneInCollection(layout, "1", "b");
      expect(next.collections?.[0].sceneNames).toEqual(["a", "b"]);
    });

    it("should_remove_a_scene_that_is_already_in_the_collection", () => {
      const next = toggleSceneInCollection(layout, "1", "a");
      expect(next.collections?.[0].sceneNames).toEqual([]);
    });

    it("should_touch_only_the_named_collection", () => {
      const two: SceneLayout = {
        order: [],
        labels: {},
        collections: [
          { id: "1", name: "LoL", sceneNames: ["a"] },
          { id: "2", name: "Pause", sceneNames: ["a"] },
        ],
      };
      const next = toggleSceneInCollection(two, "1", "a");
      expect(next.collections).toMatchObject([
        { id: "1", sceneNames: [] },
        { id: "2", sceneNames: ["a"] },
      ]);
    });
  });
});
