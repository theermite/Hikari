import { describe, expect, it } from "vitest";
import { alertMediaSourceName, ruleForAlert } from "./alertMedia";
import type { ChatSettings } from "./chatSettings";
import type { ChatAlert } from "./types";

describe("alertMediaSourceName", () => {
  it("should_carry_both_the_alert_kind_and_the_moment_it_fired", () => {
    expect(alertMediaSourceName("cheer", 1_726_400_000_000)).toBe(
      "cheer-pop-up-1726400000000",
    );
  });

  it("should_never_repeat_the_same_name_for_two_alerts_in_a_row", () => {
    // Le moteur refuse un doublon dans une scène tant que le premier n'a pas expiré
    // (`validate_source_name`) — deux alertes qui se suivent doivent obtenir deux noms.
    const first = alertMediaSourceName("cheer", 1);
    const second = alertMediaSourceName("cheer", 2);
    expect(first).not.toBe(second);
  });
});

describe("ruleForAlert", () => {
  const follow: ChatAlert = { kind: "follow", username: "Ange" };
  const cheer: ChatAlert = { kind: "cheer", username: "Ange", bits: 500, message: "" };

  it("should_return_null_when_nothing_is_configured_for_this_alert_kind", () => {
    // Pas de média par défaut : une alerte sans réglage ne doit rien afficher.
    expect(ruleForAlert(follow, {})).toBeNull();
  });

  it("should_return_the_rule_matching_the_alerts_own_kind", () => {
    const mapping: ChatSettings["alertMedia"] = {
      cheer: { scene: "main", kind: "video", path: "C:\\hype.mp4", durationMs: 4_000 },
    };

    expect(ruleForAlert(cheer, mapping)).toEqual({
      scene: "main",
      kind: "video",
      path: "C:\\hype.mp4",
      durationMs: 4_000,
    });
    expect(ruleForAlert(follow, mapping)).toBeNull();
  });
});
