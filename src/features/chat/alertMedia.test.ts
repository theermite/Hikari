import { describe, expect, it } from "vitest";
import { ruleForAlert } from "./alertMedia";
import type { ChatSettings } from "./chatSettings";
import type { ChatAlert } from "./types";

describe("ruleForAlert", () => {
  const follow: ChatAlert = { kind: "follow", username: "Ange" };
  const cheer: ChatAlert = {
    kind: "cheer",
    username: "Ange",
    bits: 500,
    message: "",
  };

  it("should_return_null_when_nothing_is_configured_for_this_alert_kind", () => {
    // Pas de média par défaut : une alerte sans réglage ne doit rien afficher.
    expect(ruleForAlert(follow, {})).toBeNull();
  });

  it("should_return_the_rule_matching_the_alerts_own_kind", () => {
    const mapping: ChatSettings["alertMedia"] = {
      cheer: { durationMs: 4_000 },
    };

    expect(ruleForAlert(cheer, mapping)).toEqual({ durationMs: 4_000 });
    expect(ruleForAlert(follow, mapping)).toBeNull();
  });
});
