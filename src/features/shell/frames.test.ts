// Tests écrits AVANT le code (TDG).
//
// Ce que ça règle, demandé par Jay le 2026-09-07 : la barre affichait « 378 images
// perdues ». Son seuil à lui est un TAUX (2 %), pas un compte — il ne pouvait donc pas
// juger seul, en direct, s'il était dans le vert. C'est moi qui ai fait la division après
// coup, ce qui est exactement ce qu'un cockpit doit éviter de lui laisser faire.

import { describe, expect, it } from "vitest";
import { dropRate, dropVerdict } from "./frames";

describe("dropRate", () => {
  it("should_return_the_share_of_frames_lost", () => {
    // Le cas réel de Jay : 15 minutes à 60 images par seconde.
    expect(dropRate(378, 54_000)).toBeCloseTo(0.7, 1);
  });

  it("should_return_null_when_nothing_has_been_sent_yet", () => {
    // Zéro image envoyée n'est pas zéro pour cent de perte : c'est une absence de mesure.
    // Afficher « 0 % » au démarrage donnerait une assurance que rien ne soutient.
    expect(dropRate(0, 0)).toBeNull();
  });

  it("should_return_null_when_the_total_is_absurd", () => {
    // Un total négatif ne vient d'aucun moteur sain. On se tait plutôt que de rendre un
    // taux négatif que l'écran afficherait sans broncher.
    expect(dropRate(5, -1)).toBeNull();
  });

  it("should_stay_at_zero_when_nothing_is_lost", () => {
    expect(dropRate(0, 10_000)).toBe(0);
  });
});

describe("dropVerdict", () => {
  it("should_say_ok_below_half_the_users_threshold", () => {
    expect(dropVerdict(0.7)).toBe("ok");
    expect(dropVerdict(0.99)).toBe("ok");
  });

  it("should_warn_between_half_the_threshold_and_the_threshold", () => {
    expect(dropVerdict(1)).toBe("attention");
    expect(dropVerdict(1.9)).toBe("attention");
  });

  it("should_alert_at_and_above_the_users_own_threshold", () => {
    // 2 % est le chiffre de Jay, pas un chiffre trouvé ailleurs. À 2 % pile on alerte :
    // un seuil atteint est un seuil dépassé, et hésiter ici coûte un direct.
    expect(dropVerdict(2)).toBe("critique");
    expect(dropVerdict(12)).toBe("critique");
  });

  it("should_say_nothing_when_there_is_no_measure", () => {
    expect(dropVerdict(null)).toBeNull();
  });
});
