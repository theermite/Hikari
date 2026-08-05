import { describe, expect, it } from "vitest";
import {
  FILE_FILTERS,
  matchesSearch,
  nameFromPath,
  SOURCE_FAMILIES,
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
