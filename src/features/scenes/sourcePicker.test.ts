import { describe, expect, it } from "vitest";
import {
  FILE_FILTERS,
  fold,
  matchesSearch,
  nameFromPath,
  SOURCE_FAMILIES,
  searchAll,
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

  it("should_find_a_window_even_when_the_game_family_is_the_open_one", () => {
    // Le defaut vecu le 2026-08-05 : chercher une fenêtre depuis l'onglet « Un jeu »
    // renvoyait une liste vide, sans rien expliquer.
    const hits = searchAll(games, windows, monitors, "bloc");

    expect(hits).toEqual([{ kind: "window", target: windows[0] }]);
  });

  it("should_find_across_every_family_at_once", () => {
    expect(searchAll(games, windows, monitors, "e").length).toBeGreaterThan(1);
  });

  it("should_show_a_target_present_in_two_families_only_once", () => {
    // Une même fenêtre apparaît souvent dans « jeux » ET dans « fenêtres ». La montrer
    // deux fois ferait douter du résultat.
    const hits = searchAll(games, windows, monitors, "league");

    expect(hits).toHaveLength(1);
    expect(hits[0].kind).toBe("game");
  });

  it("should_return_nothing_when_no_target_matches", () => {
    expect(searchAll(games, windows, monitors, "zzzz")).toEqual([]);
  });

  it("should_return_everything_when_the_search_is_empty", () => {
    // 4 cibles, dont un doublon d'identifiant retiré.
    expect(searchAll(games, windows, monitors, "")).toHaveLength(3);
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

  for (const typed of ["MNK", "Termin", "MNK T", "mnk terminal"]) {
    it(`should_find_MNK_Terminal_when_typing_${typed.replace(/\s/g, "_")}`, () => {
      const hits = searchAll(games, windows, monitors, typed);

      expect(hits.map((h) => h.target.label)).toContain("MNK Terminal");
    });
  }

  it("should_find_Spotify_when_typing_Spoti", () => {
    const hits = searchAll(games, windows, monitors, "Spoti");

    expect(hits.map((h) => h.target.label)).toContain("Spotify Widget");
  });

  it("should_survive_a_label_carrying_invisible_characters", () => {
    // « ‎Angelique » commence par une marque de direction invisible. Une recherche qui
    // planterait dessus ferait échouer TOUTE la liste, pas seulement cette ligne.
    expect(() => searchAll(games, windows, monitors, "angel")).not.toThrow();
    expect(
      searchAll(games, windows, monitors, "mejias").map((h) => h.target.label),
    ).toHaveLength(1);
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
