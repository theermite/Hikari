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
  locked: false,
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
      locked: false,
    });
  });

  it("should_remember_the_camera_apart_from_the_other_sources", () => {
    // La caméra est UNE source physique partagée entre scènes, recréée par sa propre
    // commande. La ranger avec les captures la ferait recréer comme l'une d'elles, ce qui
    // ouvrirait l'appareil une seconde fois.
    const doc = toSession(
      [
        scene("main", [
          source(),
          source({
            name: "Webcam",
            kind: "dshow_input",
            source_kind: "camera",
            target_id: "cam:1",
            x: 50,
            y: 60,
            scale_percent: 40,
          }),
        ]),
      ],
      "main",
    );

    expect(doc.scenes[0].sources.map((s) => s.name)).toEqual(["Jeu"]);
    expect(doc.scenes[0].camera).toMatchObject({
      deviceId: "cam:1",
      x: 50,
      y: 60,
      scalePercent: 40,
    });
  });

  it("should_remember_each_scenes_own_camera_filters", () => {
    // Le flux que Jay utilise : une seule caméra, des filtres propres à chaque scène.
    const withCamera = scene("Jeu", [
      source({ name: "Webcam", source_kind: "camera", target_id: "cam:1" }),
    ]);
    withCamera.background_removal = true;
    withCamera.circle_mask = false;

    const doc = toSession([withCamera], "Jeu");

    expect(doc.scenes[0].camera).toMatchObject({
      backgroundRemoval: true,
      circleMask: false,
    });
  });

  it("should_remember_a_mixer_entry_with_everything_needed_to_rebuild_it", () => {
    const doc = toSession([scene("main")], "main", [
      {
        name: "Micro",
        kind: "input",
        device_id: "{0.0.1}",
        volume_percent: 80,
        monitor_volume_percent: 65,
        muted: true,
        monitoring: "monitor_and_output",
        noise_suppression: true,
        noise_method: "speex",
        noise_level_db: -24,
      },
    ]);

    expect(doc.audio[0]).toEqual({
      name: "Micro",
      kind: "input",
      deviceId: "{0.0.1}",
      volumePercent: 80,
      monitorVolumePercent: 65,
      muted: true,
      monitoring: "monitor_and_output",
      noiseSuppression: true,
      noiseMethod: "speex",
      noiseLevelDb: -24,
    });
  });

  it("should_remember_which_scene_was_live", () => {
    expect(toSession([scene("main"), scene("Jeu")], "Jeu").active).toBe("Jeu");
  });

  it("should_remember_the_cameras_own_source_name", () => {
    // Sans son nom, le placement retenu n'est adressable par aucune commande au rejeu : il
    // reste sur le disque sans jamais revenir à l'écran (défaut trouvé par Jay, 2026-08-06).
    const doc = toSession(
      [
        scene("Bureau", [
          source({ name: "Webcam", source_kind: "camera", target_id: "cam:1" }),
        ]),
      ],
      "Bureau",
    );

    expect(doc.scenes[0].camera?.name).toBe("Webcam");
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
    const steps = buildReplay({ scenes: [], active: "", audio: [] }, [
      scene("main"),
    ]);

    expect(steps).toEqual([]);
  });

  /** Le cadrage de la caméra était retenu sur le disque et jamais rendu à l'écran (Jay,
   * 2026-08-06 : « la position de la caméra n'a pas été mémorisée »). Une caméra ajoutée
   * revient au cadre par défaut du moteur : sans replacement explicite, chaque lancement
   * défait le cadrage de la veille. */
  const withCamera = () => {
    const bureau = scene("Bureau", [
      source({
        name: "Webcam",
        source_kind: "camera",
        target_id: "cam:1",
        x: 941,
        y: 486,
        scale_percent: 55,
      }),
    ]);
    bureau.background_removal = true;
    return toSession([bureau], "Bureau");
  };

  it("should_put_the_camera_back_where_the_user_left_it", () => {
    const steps = buildReplay(withCamera(), [scene("main")]);

    expect(steps).toContainEqual({
      do: "transform",
      scene: "Bureau",
      name: "Webcam",
      x: 941,
      y: 486,
      scalePercent: 55,
    });
  });

  it("should_place_the_camera_only_after_it_exists", () => {
    // Replacer une caméra que le moteur n'a pas encore reçue viserait un objet absent :
    // le moteur répondrait « Webcam n'est pas dans Bureau » et le cadrage serait perdu.
    const steps = buildReplay(withCamera(), [scene("main")]);
    const added = steps.findIndex((s) => s.do === "addCamera");
    const placed = steps.findIndex(
      (s) => s.do === "transform" && s.name === "Webcam",
    );

    expect(added).toBeGreaterThanOrEqual(0);
    expect(placed).toBeGreaterThan(added);
  });

  it("should_lock_back_a_source_the_user_had_locked", () => {
    // Un verrou qui se rouvre au lancement ne protège de rien : c'est précisément après un
    // redémarrage qu'on redispose l'écran, donc qu'on risque le geste accidentel.
    const saved = toSession(
      [scene("Bureau", [source({ name: "Fond", locked: true })])],
      "Bureau",
    );

    const steps = buildReplay(saved, [scene("main")]);

    expect(steps).toContainEqual({
      do: "lock",
      scene: "Bureau",
      name: "Fond",
    });
  });

  it("should_lock_only_after_the_source_is_placed", () => {
    // Verrouiller avant de replacer figerait la source au cadre par défaut : le moteur
    // refuserait ensuite de la bouger, et le placement retenu serait perdu pour de bon.
    const saved = toSession(
      [scene("Bureau", [source({ name: "Fond", locked: true })])],
      "Bureau",
    );

    const steps = buildReplay(saved, [scene("main")]);
    const placed = steps.findIndex(
      (s) => s.do === "transform" && s.name === "Fond",
    );
    const locked = steps.findIndex((s) => s.do === "lock" && s.name === "Fond");

    expect(placed).toBeGreaterThanOrEqual(0);
    expect(locked).toBeGreaterThan(placed);
  });

  it("should_ask_for_no_lock_when_nothing_is_locked", () => {
    const steps = buildReplay(saved, [scene("main")]);

    expect(steps.filter((s) => s.do === "lock")).toHaveLength(0);
  });

  it("should_lock_back_a_camera_the_user_had_locked", () => {
    // La caméra est celle qu'on bouge le plus par accident : l'exclure du verrou en ferait
    // une exception que rien ne justifie côté utilisateur.
    const bureau = scene("Bureau", [
      source({
        name: "Webcam",
        source_kind: "camera",
        target_id: "cam:1",
        locked: true,
      }),
    ]);

    const steps = buildReplay(toSession([bureau], "Bureau"), [scene("main")]);

    expect(steps).toContainEqual({
      do: "lock",
      scene: "Bureau",
      name: "Webcam",
    });
  });

  it("should_still_place_a_camera_saved_before_its_name_was_kept", () => {
    // Les sessions écrites avant ce correctif n'ont pas de nom de caméra. Le moteur n'en
    // a qu'un seul possible : s'en servir évite de perdre un cadrage au premier lancement
    // qui suit la mise à jour.
    const doc = withCamera();
    const camera = doc.scenes[0].camera;
    if (camera) delete (camera as { name?: string }).name;

    const steps = buildReplay(doc, [scene("main")]);

    expect(steps).toContainEqual({
      do: "transform",
      scene: "Bureau",
      name: "Webcam",
      x: 941,
      y: 486,
      scalePercent: 55,
    });
  });
});
