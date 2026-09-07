// Tests écrits AVANT le code (TDG).
//
// Jay, 2026-09-07 : « mettre une source de texte sans réglage, sans personnalisation, je
// trouve ça très inutile ». Le greffon `text_gdiplus` porte police, taille, couleur,
// contour et alignement depuis toujours — rien ne les atteignait.

import { describe, expect, it } from "vitest";
import {
  clampFontSize,
  clampOutlineSize,
  DEFAULT_TEXT_SETTINGS,
  withDefaults,
} from "./textSettings";

describe("DEFAULT_TEXT_SETTINGS", () => {
  it("should_be_readable_on_any_scene_out_of_the_box", () => {
    // Un texte blanc sur une scène claire disparaît. Le contour est donc actif par défaut :
    // c'est la seule valeur qui rend le texte lisible sans rien régler, quel que soit le
    // fond — et un premier essai qui montre un texte invisible ne donne pas envie du second.
    expect(DEFAULT_TEXT_SETTINGS.outline).toBe(true);
    expect(DEFAULT_TEXT_SETTINGS.outline_color).toEqual({ r: 0, g: 0, b: 0 });
    expect(DEFAULT_TEXT_SETTINGS.color).toEqual({ r: 255, g: 255, b: 255 });
  });

  it("should_start_big_enough_to_be_seen_on_a_stream", () => {
    // Une taille de texte de traitement de texte se perd sur une image de diffusion
    // réduite chez le spectateur.
    expect(DEFAULT_TEXT_SETTINGS.size).toBeGreaterThanOrEqual(32);
  });
});

describe("withDefaults", () => {
  it("should_fill_a_source_that_was_never_configured", () => {
    // Une source texte posée AVANT ce jour n'a aucun réglage enregistré. Sans valeurs de
    // repli, l'écran afficherait des champs vides et poserait une police nommée « » —
    // même famille que le champ ajouté à une donnée persistée sans défaut de lecture.
    expect(withDefaults(undefined)).toEqual(DEFAULT_TEXT_SETTINGS);
  });

  it("should_keep_every_value_that_was_configured", () => {
    const choisi = { ...DEFAULT_TEXT_SETTINGS, size: 96, italic: true };
    expect(withDefaults(choisi)).toEqual(choisi);
  });

  it("should_complete_a_half_written_record", () => {
    // Une session écrite par une version plus ancienne peut porter une moitié des champs.
    const partiel = { size: 64 } as Partial<typeof DEFAULT_TEXT_SETTINGS>;
    const complet = withDefaults(partiel);
    expect(complet.size).toBe(64);
    expect(complet.face).toBe(DEFAULT_TEXT_SETTINGS.face);
    expect(complet.outline).toBe(DEFAULT_TEXT_SETTINGS.outline);
  });
});

describe("clampFontSize", () => {
  it("should_refuse_a_size_that_would_make_the_text_vanish", () => {
    // Zéro ou négatif donne un texte invisible que l'utilisateur chercherait dans sa scène
    // — exactement le défaut que le refus du texte vide évite déjà à l'ajout.
    expect(clampFontSize(0)).toBeGreaterThan(0);
    expect(clampFontSize(-40)).toBeGreaterThan(0);
  });

  it("should_refuse_a_size_that_would_swallow_the_scene", () => {
    expect(clampFontSize(100000)).toBeLessThanOrEqual(500);
  });

  it("should_keep_a_reasonable_size_untouched", () => {
    expect(clampFontSize(48)).toBe(48);
  });

  it("should_fall_back_when_the_value_is_not_a_number", () => {
    expect(clampFontSize(Number.NaN)).toBe(DEFAULT_TEXT_SETTINGS.size);
  });
});

describe("clampOutlineSize", () => {
  it("should_allow_no_outline_at_all", () => {
    // Zéro est légitime ici, au contraire de la taille du texte : un contour nul est un
    // choix, un texte de taille nulle est une disparition.
    expect(clampOutlineSize(0)).toBe(0);
  });

  it("should_refuse_an_outline_thicker_than_the_text", () => {
    expect(clampOutlineSize(9999)).toBeLessThanOrEqual(50);
  });
});
