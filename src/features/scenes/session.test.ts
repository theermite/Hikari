import { describe, expect, it } from "vitest";
import { buildReplay, toSession } from "./session";
import type { SceneInfo, SceneSourceInfo } from "./types";

const source = (over: Partial<SceneSourceInfo> = {}): SceneSourceInfo => ({
  name: "Jeu",
  kind: "game_capture",
  source_kind: "game",
  target_id: "LoL",
  x: 10,
  y: 20,
  scale_percent: 100,
  ...over,
});

const scene = (name: string, sources: SceneSourceInfo[] = []): SceneInfo => ({
  name,
  has_camera: false,
  background_removal: false,
  circle_mask: false,
  sources,
});

describe("toSession", () => {
  it("should_keep_everything_needed_to_rebuild_a_source", () => {
    const doc = toSession([scene("main", [source()])], "main");

    expect(doc.scenes[0].sources[0]).toEqual({
      name: "Jeu",
      kind: "game",
      targetId: "LoL",
      x: 10,
      y: 20,
      scalePercent: 100,
    });
  });

  it("should_not_remember_the_camera", () => {
    // La caméra est UNE source physique partagée entre scènes, recréée par sa propre
    // commande. La retenir ici la ferait recréer en double.
    const doc = toSession(
      [
        scene("main", [
          source(),
          source({ name: "Webcam", kind: "dshow_input" }),
        ]),
      ],
      "main",
    );

    expect(doc.scenes[0].sources.map((s) => s.name)).toEqual(["Jeu"]);
  });

  it("should_remember_which_scene_was_live", () => {
    expect(toSession([scene("main"), scene("Jeu")], "Jeu").active).toBe("Jeu");
  });
});

describe("buildReplay", () => {
  const saved = toSession(
    [
      scene("main", [
        source({ name: "Monitor Capture", source_kind: "monitor" }),
      ]),
      scene("Jeu", [source()]),
    ],
    "Jeu",
  );

  it("should_create_only_the_scenes_the_engine_does_not_have", () => {
    // Au démarrage le moteur a déjà « main » : la recréer se ferait refuser.
    const steps = buildReplay(saved, [scene("main")]);

    expect(steps.filter((s) => s.do === "createScene")).toEqual([
      { do: "createScene", scene: "Jeu" },
    ]);
  });

  it("should_add_only_the_sources_the_scene_does_not_have", () => {
    const current = [
      scene("main", [source({ name: "Monitor Capture" })]),
      scene("Jeu"),
    ];

    const added = buildReplay(saved, current).filter(
      (s) => s.do === "addSource",
    );

    expect(added).toHaveLength(1);
    expect(added[0]).toMatchObject({ scene: "Jeu", name: "Jeu" });
  });

  it("should_replace_every_source_even_one_already_present", () => {
    // La capture d'écran que le moteur pose lui-même arrive au cadre par défaut, pas là
    // où l'utilisateur l'avait mise.
    const steps = buildReplay(saved, [
      scene("main", [source({ name: "Monitor Capture" })]),
    ]);

    expect(steps.filter((s) => s.do === "transform")).toHaveLength(2);
  });

  it("should_switch_to_the_live_scene_LAST", () => {
    // Basculer en premier diffuserait une scène à moitié construite.
    const steps = buildReplay(saved, [scene("main")]);

    expect(steps[steps.length - 1]).toEqual({
      do: "switchScene",
      scene: "Jeu",
    });
  });

  it("should_create_scenes_before_filling_them", () => {
    const steps = buildReplay(saved, [scene("main")]);
    const creates = steps
      .map((step, index) => ({ step, index }))
      .filter(({ step }) => step.do === "createScene");
    const lastCreate = creates[creates.length - 1].index;
    const firstAdd = steps.findIndex((s) => s.do === "addSource");

    expect(lastCreate).toBeLessThan(firstAdd);
  });

  it("should_do_nothing_beyond_switching_when_everything_is_already_there", () => {
    const current = [
      scene("main", [source({ name: "Monitor Capture" })]),
      scene("Jeu", [source()]),
    ];

    const steps = buildReplay(saved, current);

    expect(steps.filter((s) => s.do === "createScene")).toHaveLength(0);
    expect(steps.filter((s) => s.do === "addSource")).toHaveLength(0);
  });

  it("should_produce_no_step_from_an_empty_session", () => {
    const steps = buildReplay({ scenes: [], active: "" }, [scene("main")]);

    expect(steps).toEqual([]);
  });
});
