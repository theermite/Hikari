import { describe, expect, it } from "vitest";
import {
  dedupeTargets,
  FILE_FILTERS,
  fold,
  matchesSearch,
  nameFromPath,
  SOURCE_FAMILIES,
  searchAll,
  targetsFor,
} from "./sourcePicker";

const target = (label: string) => ({ id: "x", label });

describe("matchesSearch", () => {
  it("should_accept_everything_when_the_search_is_empty", () => {
    // Un champ vide ne doit jamais masquer la liste.
    expect(matchesSearch(target("League of Legends"), "")).toBe(true);
    expect(matchesSearch(target("League of Legends"), "   ")).toBe(true);
  });

  it("should_ignore_case", () => {
    expect(matchesSearch(target("League of Legends"), "LEAGUE")).toBe(true);
  });

  it("should_ignore_accents", () => {
    // Sans ça, chercher « ecran » ne trouverait jamais « Écran 1 ».
    expect(matchesSearch(target("Écran 1"), "ecran")).toBe(true);
    expect(matchesSearch(target("Ecran 1"), "écran")).toBe(true);
  });

  it("should_find_words_in_any_order", () => {
    // « chrome doc » trouve « Document — Google Chrome », ce qu'une recherche de la
    // phrase entière raterait.
    expect(
      matchesSearch(target("Document — Google Chrome"), "chrome doc"),
    ).toBe(true);
  });

  it("should_reject_when_one_word_is_absent", () => {
    expect(matchesSearch(target("Google Chrome"), "chrome firefox")).toBe(
      false,
    );
  });

  it("should_match_a_fragment_inside_a_word", () => {
    expect(matchesSearch(target("Bloc-notes"), "note")).toBe(true);
  });
});

describe("fold", () => {
  it("should_never_empty_a_non_empty_text", () => {
    // LE test qui manquait le 2026-08-05. L'ancien nettoyage d'accents vidait la chaîne
    // dans le navigateur de l'app : la recherche devenait vide, donc tout passait, et la
    // liste semblait ne pas réagir. Aucun test ne regardait ce que le nettoyage RENDAIT.
    for (const text of ["MNK Terminal", "Spoti", "Écran 1", "MNK Ter"]) {
      expect(fold(text).length).toBeGreaterThan(0);
    }
  });

  it("should_only_remove_the_accent_marks", () => {
    expect(fold("Écran")).toBe("ecran");
    expect(fold("MNK Terminal")).toBe("mnk terminal");
  });
});

describe("searchAll", () => {
  const games = [{ id: "g1", label: "League of Legends" }];
  const windows = [
    { id: "w1", label: "Bloc-notes" },
    { id: "g1", label: "League of Legends" },
  ];
  const monitors = [{ id: "m1", label: "Écran 1" }];
  const cameras = [{ id: "cam1", label: "Logitech StreamCam" }];

  it("should_find_a_window_even_when_the_game_family_is_the_open_one", () => {
    // Le defaut vecu le 2026-08-05 : chercher une fenêtre depuis l'onglet « Un jeu »
    // renvoyait une liste vide, sans rien expliquer.
    const hits = searchAll({ games, windows, monitors, cameras }, "bloc");

    expect(hits).toEqual([{ kind: "window", target: windows[0] }]);
  });

  it("should_find_across_every_family_at_once", () => {
    expect(
      searchAll({ games, windows, monitors, cameras }, "e").length,
    ).toBeGreaterThan(1);
  });

  it("should_show_a_target_present_in_two_families_only_once", () => {
    // Une même fenêtre apparaît souvent dans « jeux » ET dans « fenêtres ». La montrer
    // deux fois ferait douter du résultat.
    const hits = searchAll({ games, windows, monitors, cameras }, "league");

    expect(hits).toHaveLength(1);
    expect(hits[0].kind).toBe("game");
  });

  it("should_return_nothing_when_no_target_matches", () => {
    expect(searchAll({ games, windows, monitors, cameras }, "zzzz")).toEqual(
      [],
    );
  });

  it("should_find_a_camera_like_any_other_source", () => {
    // Une caméra est une source comme les autres depuis le 2026-09-06 : elle se cherche
    // au même endroit, pas dans un panneau à part (Jay).
    const hits = searchAll({ games, windows, monitors, cameras }, "streamcam");

    expect(hits).toEqual([{ kind: "camera", target: cameras[0] }]);
  });

  it("should_return_everything_when_the_search_is_empty", () => {
    // 5 cibles, dont un doublon d'identifiant retiré.
    expect(searchAll({ games, windows, monitors, cameras }, "")).toHaveLength(
      4,
    );
  });
});

describe("recherche sur les libellés RÉELS de la machine de Jay (2026-08-05)", () => {
  // Libellés relevés par sonde dans le moteur, copiés tels quels — un test sur des
  // exemples inventés prouve le filtre contre lui-même, jamais contre le terrain.
  const windows = [
    { id: "w1", label: "MNK Terminal" },
    { id: "w2", label: "Spotify Widget" },
    { id: "w3", label: "@•● Héclyps ●• - Discord" },
    { id: "w4", label: "Kung Fu Panda 2.mkv - VLC media player" },
    { id: "w5", label: "‎Angelique Mejias – (46)" },
  ];
  const games = [{ id: "g1", label: "Ankama Launcher" }];
  const monitors = [{ id: "m1", label: "Écran 1" }];
  const cameras: { id: string; label: string }[] = [];

  for (const typed of ["MNK", "Termin", "MNK T", "mnk terminal"]) {
    it(`should_find_MNK_Terminal_when_typing_${typed.replace(/\s/g, "_")}`, () => {
      const hits = searchAll({ games, windows, monitors, cameras }, typed);

      expect(hits.map((h) => h.target.label)).toContain("MNK Terminal");
    });
  }

  it("should_find_Spotify_when_typing_Spoti", () => {
    const hits = searchAll({ games, windows, monitors, cameras }, "Spoti");

    expect(hits.map((h) => h.target.label)).toContain("Spotify Widget");
  });

  it("should_survive_a_label_carrying_invisible_characters", () => {
    // « ‎Angelique » commence par une marque de direction invisible. Une recherche qui
    // planterait dessus ferait échouer TOUTE la liste, pas seulement cette ligne.
    expect(() =>
      searchAll({ games, windows, monitors, cameras }, "angel"),
    ).not.toThrow();
    expect(
      searchAll({ games, windows, monitors, cameras }, "mejias").map(
        (h) => h.target.label,
      ),
    ).toHaveLength(1);
  });
});

describe("dedupeTargets", () => {
  it("should_collapse_the_twelve_identical_entries_windows_really_reports", () => {
    // Cas réel du 2026-08-05 : Windows expose douze « Spotify Widget » avec le MÊME
    // identifiant. Douze lignes identiques n'aident personne, et leurs clés en double
    // figeaient l'affichage.
    const targets = Array.from({ length: 12 }, () => ({
      id: "spotify",
      label: "Spotify Widget",
    }));

    expect(dedupeTargets(targets)).toHaveLength(1);
  });

  it("should_keep_two_entries_that_differ_by_identifier", () => {
    const targets = [
      { id: "a", label: "Bloc-notes" },
      { id: "b", label: "Bloc-notes" },
    ];

    expect(dedupeTargets(targets)).toHaveLength(2);
  });

  it("should_keep_the_first_occurrence_order", () => {
    const targets = [
      { id: "a", label: "Premier" },
      { id: "b", label: "Second" },
      { id: "a", label: "Premier" },
    ];

    expect(dedupeTargets(targets).map((t) => t.label)).toEqual([
      "Premier",
      "Second",
    ]);
  });

  it("should_produce_a_list_whose_identifiers_are_all_unique", () => {
    // La propriété qui protège l'affichage : un identifiant en double casse le rendu.
    const targets = [
      { id: "a", label: "X" },
      { id: "a", label: "X" },
      { id: "b", label: "Y" },
    ];
    const ids = dedupeTargets(targets).map((t) => t.id);

    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("nameFromPath", () => {
  it("should_keep_only_the_file_name_without_its_extension", () => {
    expect(nameFromPath("D:\\images\\logo.png")).toBe("logo");
    expect(nameFromPath("/home/jay/videos/intro.mp4")).toBe("intro");
  });

  it("should_keep_a_name_that_has_no_extension", () => {
    expect(nameFromPath("D:\\images\\logo")).toBe("logo");
  });

  it("should_keep_a_hidden_file_name_whole", () => {
    // Un nom commençant par un point n'a pas d'extension à retirer.
    expect(nameFromPath(".gitignore")).toBe(".gitignore");
  });

  it("should_keep_every_dot_but_the_last", () => {
    expect(nameFromPath("mon.logo.v2.png")).toBe("mon.logo.v2");
  });
});

describe("SOURCE_FAMILIES", () => {
  it("should_mark_exactly_the_two_file_families", () => {
    // Une image ou une vidéo se choisit sur le disque ; le reste se choisit dans une liste.
    const files = SOURCE_FAMILIES.filter((f) => f.isFile).map((f) => f.kind);
    expect(files).toEqual(["image", "video"]);
  });

  it("should_offer_a_file_filter_for_every_file_family", () => {
    for (const family of SOURCE_FAMILIES.filter((f) => f.isFile)) {
      expect(FILE_FILTERS[family.kind]?.length).toBeGreaterThan(0);
    }
  });
});

describe("SOURCE_FAMILIES", () => {
  it("should_offer_the_camera_next_to_the_other_families", () => {
    // Décision de Jay, 2026-09-06 : « la caméra doit devenir une source ordinaire ».
    // Une seule porte d'entrée pour tout ce qu'une scène peut montrer.
    expect(SOURCE_FAMILIES.map((f) => f.kind)).toContain("camera");
  });

  it("should_choose_a_camera_in_a_list_never_on_the_disk", () => {
    const camera = SOURCE_FAMILIES.find((f) => f.kind === "camera");

    expect(camera?.isFile).toBe(false);
  });
});

describe("targetsFor", () => {
  const targets = {
    games: [{ id: "g1", label: "Un jeu" }],
    windows: [{ id: "w1", label: "Une fenêtre" }],
    monitors: [{ id: "m1", label: "Un écran" }],
    cameras: [{ id: "cam1", label: "Logitech StreamCam" }],
  };

  it("should_serve_the_cameras_when_the_camera_family_is_open", () => {
    expect(targetsFor("camera", targets)).toEqual(targets.cameras);
  });

  it("should_serve_each_live_family_its_own_targets", () => {
    expect(targetsFor("game", targets)).toEqual(targets.games);
    expect(targetsFor("window", targets)).toEqual(targets.windows);
    expect(targetsFor("monitor", targets)).toEqual(targets.monitors);
  });

  it("should_serve_nothing_for_a_family_chosen_on_the_disk", () => {
    // Une image ou une vidéo n'a pas de liste : le sélecteur du système prend le relais.
    expect(targetsFor("image", targets)).toEqual([]);
    expect(targetsFor("video", targets)).toEqual([]);
  });
});

describe("la famille TEXTE", () => {
  it("should_offer_text_next_to_the_other_families", () => {
    expect(SOURCE_FAMILIES.map((f) => f.kind)).toContain("text");
  });

  it("should_not_ask_for_a_file_nor_a_list", () => {
    // Le contenu d'une source texte vient de l'utilisateur, pas de la machine : ni
    // sélecteur de fichier, ni liste de cibles à parcourir. On l'écrit.
    const texte = SOURCE_FAMILIES.find((f) => f.kind === "text");

    expect(texte?.isFile).toBe(false);
    expect(
      targetsFor("text", {
        games: [],
        windows: [],
        monitors: [],
        cameras: [],
      }),
    ).toEqual([]);
  });

  it("should_say_what_it_is_for_in_plain_words", () => {
    const texte = SOURCE_FAMILIES.find((f) => f.kind === "text");

    expect(texte?.hint.length).toBeGreaterThan(10);
  });
});
