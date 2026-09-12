import { describe, expect, it } from "vitest";
import { buildReplay, camerasOf, toSession } from "./session";
import { NO_MASK, type SceneInfo, type SceneSourceInfo } from "./types";

const source = (over: Partial<SceneSourceInfo> = {}): SceneSourceInfo => ({
  name: "Jeu",
  kind: "game_capture",
  source_kind: "game",
  target_id: "LoL",
  x: 10,
  y: 20,
  scale_percent: 100,
  locked: false,
  background_removal: false,
  mask_shape: NO_MASK,
  visible: true,
  ...over,
});

const scene = (name: string, sources: SceneSourceInfo[] = []): SceneInfo => ({
  name,
  has_camera: sources.some((s) => s.source_kind === "camera"),
  sources,
});

describe("camerasOf", () => {
  it("should_read_a_session_saved_before_several_cameras_existed", () => {
    // Une session déjà sur le disque de Jay porte UNE caméra, sous l'ancien champ. La lire
    // comme une liste vide lui ferait perdre son cadrage au lancement — sans erreur, sans
    // que rien ne l'explique.
    const old = {
      name: "Bureau",
      sources: [],
      camera: {
        deviceId: "cam:1",
        name: "Webcam",
        backgroundRemoval: true,
        circleMask: false,
        x: 10,
        y: 20,
        scalePercent: 55,
      },
    };

    expect(camerasOf(old)).toMatchObject([{ deviceId: "cam:1", x: 10 }]);
  });

  it("should_prefer_the_new_list_when_a_session_carries_both", () => {
    const both = {
      name: "Bureau",
      sources: [],
      cameras: [
        {
          deviceId: "cam:2",
          backgroundRemoval: false,
          circleMask: false,
          x: 0,
          y: 0,
          scalePercent: 100,
        },
      ],
      camera: {
        deviceId: "cam:1",
        backgroundRemoval: false,
        circleMask: false,
        x: 0,
        y: 0,
        scalePercent: 100,
      },
    };

    expect(camerasOf(both).map((c) => c.deviceId)).toEqual(["cam:2"]);
  });
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
      order: 0,
      text: undefined,
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
    expect(doc.scenes[0].cameras?.[0]).toMatchObject({
      deviceId: "cam:1",
      x: 50,
      y: 60,
      scalePercent: 40,
    });
  });

  it("should_remember_each_cameras_own_filters", () => {
    // Les filtres appartiennent à la caméra : deux caméras d'une scène peuvent différer.
    const withCameras = scene("Jeu", [
      source({
        name: "StreamCam",
        source_kind: "camera",
        target_id: "cam:1",
        background_removal: true,
      }),
      source({
        name: "Brio",
        source_kind: "camera",
        target_id: "cam:2",
        mask_shape: { kind: "circle" },
      }),
    ]);

    const doc = toSession([withCameras], "Jeu");

    expect(doc.scenes[0].cameras).toMatchObject([
      { deviceId: "cam:1", backgroundRemoval: true, maskShape: NO_MASK },
      {
        deviceId: "cam:2",
        backgroundRemoval: false,
        maskShape: { kind: "circle" },
      },
    ]);
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

    expect(doc.scenes[0].cameras?.[0].name).toBe("Webcam");
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

  /** L'ordre en direct se sauvegardait déjà (le moteur relit sa vraie pile et l'annonce),
   * mais le rejeu ne le restaurait jamais : seul l'ordre d'AJOUT décidait de la pile
   * reconstruite (Jay, 2026-09-12 : « l'ordre des sources ne se sauvegarde pas »). Une
   * source déjà présente au démarrage (la capture d'écran par défaut de « main ») n'était
   * même jamais candidate à un replacement, faute d'étape dédiée. */
  const stacked = () => {
    // Deux captures ET une caméra dans la MÊME scène, comme la pile réelle du moteur —
    // index 0 = la plus devant, à l'image de ce que `emit_scene_list` envoie déjà.
    const bureau = scene("Bureau", [
      source({ name: "Devant", target_id: "A" }),
      source({
        name: "Webcam",
        source_kind: "camera",
        target_id: "cam:1",
      }),
      source({ name: "Derriere", target_id: "B" }),
    ]);
    return toSession([bureau], "Bureau");
  };

  it("should_remember_each_sources_position_in_the_stack", () => {
    const doc = stacked();

    // 3 éléments au total : la plus devant (index 0) porte la plus GRANDE valeur, la même
    // convention que `order_position` côté moteur (0 = le plus derrière).
    expect(doc.scenes[0].sources.map((s) => [s.name, s.order])).toEqual([
      ["Devant", 2],
      ["Derriere", 0],
    ]);
    expect(doc.scenes[0].cameras?.[0]).toMatchObject({
      deviceId: "cam:1",
      order: 1,
    });
  });

  it("should_restore_the_saved_stack_order_of_every_source_and_camera", () => {
    const steps = buildReplay(stacked(), [scene("main")]);

    expect(steps).toContainEqual({
      do: "setOrder",
      scene: "Bureau",
      name: "Devant",
      position: 2,
    });
    expect(steps).toContainEqual({
      do: "setOrder",
      scene: "Bureau",
      name: "Webcam",
      position: 1,
    });
    expect(steps).toContainEqual({
      do: "setOrder",
      scene: "Bureau",
      name: "Derriere",
      position: 0,
    });
  });

  it("should_reorder_only_after_every_source_exists", () => {
    // Réordonner une source que le moteur n'a pas encore reçue viserait un objet absent.
    const steps = buildReplay(stacked(), [scene("main")]);
    const addedCapture = steps.findIndex(
      (s) => s.do === "addSource" && s.name === "Derriere",
    );
    const addedCamera = steps.findIndex((s) => s.do === "addCamera");
    const reorderedCapture = steps.findIndex(
      (s) => s.do === "setOrder" && s.name === "Derriere",
    );
    const reorderedCamera = steps.findIndex(
      (s) => s.do === "setOrder" && s.name === "Webcam",
    );

    expect(reorderedCapture).toBeGreaterThan(addedCapture);
    expect(reorderedCamera).toBeGreaterThan(addedCamera);
  });

  it("should_shift_the_saved_order_past_a_live_source_the_session_never_recorded", () => {
    // Relecture indépendante (2026-09-12) : le moteur pose lui-même une capture d'écran
    // dans "main" à CHAQUE démarrage (`lifecycle_ops.rs`), même si l'utilisateur l'avait
    // retirée avant d'enregistrer sa session (possible depuis le 2026-08-05) — elle
    // n'apparaît alors dans AUCUNE session sauvegardée. Sans décalage, une position 0 émise
    // ici viserait la même place que cette capture jamais rejouée, et la pousserait ailleurs
    // dans la pile au lieu de la laisser au fond, intacte.
    const saved = toSession([scene("main", [source({ name: "Jeu" })])], "main");
    // Le moteur, avant tout rejeu : la capture d'écran existe déjà, "Jeu" n'existe pas
    // encore — exactement l'état réel au démarrage.
    const current = [
      scene("main", [source({ name: "Écran", target_id: "M" })]),
    ];

    const steps = buildReplay(saved, current);

    expect(steps).toContainEqual({
      do: "setOrder",
      scene: "main",
      name: "Jeu",
      position: 1, // 0 (seule position enregistrée) + 1 (la capture vivante, non listée)
    });
  });

  it("should_ask_for_no_reorder_when_the_session_predates_ordering", () => {
    // Une session écrite avant ce correctif ne porte pas `order` : imposer un ordre inventé
    // vaudrait moins qu'aucun ordre — l'ancien comportement (ordre d'ajout) reste inchangé.
    const doc = stacked();
    for (const s of doc.scenes[0].sources)
      delete (s as { order?: number }).order;
    for (const c of doc.scenes[0].cameras ?? [])
      delete (c as { order?: number }).order;

    const steps = buildReplay(doc, [scene("main")]);

    expect(steps.filter((s) => s.do === "setOrder")).toHaveLength(0);
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
