import { describe, expect, it } from "vitest";

import { ALERTS_HISTORY_CAP, describeAlert, pushAlert } from "./alerts";
import type { ChatAlert, DisplayedChatAlert } from "./types";

describe("chat alerts", () => {
  it("should_append_alerts_in_order", () => {
    let history: DisplayedChatAlert[] = [];
    history = pushAlert(history, { kind: "follow", username: "Ange" }, 1);
    history = pushAlert(
      history,
      { kind: "raid", from_username: "Jay", viewers: 12 },
      2,
    );

    expect(history).toEqual([
      { id: 1, alert: { kind: "follow", username: "Ange" } },
      { id: 2, alert: { kind: "raid", from_username: "Jay", viewers: 12 } },
    ]);
  });

  it("should_cap_alert_history_at_the_limit", () => {
    let history: DisplayedChatAlert[] = [];
    for (let i = 0; i < ALERTS_HISTORY_CAP + 3; i++) {
      history = pushAlert(history, { kind: "follow", username: String(i) }, i);
    }

    expect(history).toHaveLength(ALERTS_HISTORY_CAP);
    expect((history[0].alert as { username: string }).username).toBe("3");
  });

  it("should_describe_a_follow", () => {
    const alert: ChatAlert = { kind: "follow", username: "Ange" };
    expect(describeAlert(alert)).toBe("Ange vient de suivre la chaîne");
  });

  it("should_describe_a_subscribe", () => {
    const alert: ChatAlert = {
      kind: "subscribe",
      username: "Jay",
      tier: "1000",
    };
    expect(describeAlert(alert)).toBe("Jay s'est abonné (palier 1000)");
  });

  it("should_describe_a_named_gift", () => {
    const alert: ChatAlert = {
      kind: "subscription_gift",
      username: "Jay",
      total: 5,
      tier: "1000",
    };
    expect(describeAlert(alert)).toBe(
      "Jay a offert 5 abonnements (palier 1000)",
    );
  });

  it("should_describe_an_anonymous_gift", () => {
    const alert: ChatAlert = {
      kind: "subscription_gift",
      username: null,
      total: 1,
      tier: "1000",
    };
    expect(describeAlert(alert)).toBe(
      "Quelqu'un a offert 1 abonnement (palier 1000)",
    );
  });

  it("should_describe_a_resub_with_a_message", () => {
    const alert: ChatAlert = {
      kind: "resub",
      username: "Ange",
      tier: "2000",
      cumulative_months: 8,
      message: "toujours là !",
    };
    expect(describeAlert(alert)).toBe(
      "Ange a resigné pour 8 mois : « toujours là ! »",
    );
  });

  it("should_describe_a_resub_without_a_message", () => {
    const alert: ChatAlert = {
      kind: "resub",
      username: "Ange",
      tier: "2000",
      cumulative_months: 8,
      message: "",
    };
    expect(describeAlert(alert)).toBe("Ange a resigné pour 8 mois");
  });

  it("should_describe_a_cheer", () => {
    const alert: ChatAlert = {
      kind: "cheer",
      username: "Jay",
      bits: 500,
      message: "gg",
    };
    expect(describeAlert(alert)).toBe("Jay a envoyé 500 bits : gg");
  });

  it("should_describe_an_anonymous_cheer", () => {
    const alert: ChatAlert = {
      kind: "cheer",
      username: null,
      bits: 100,
      message: "",
    };
    expect(describeAlert(alert)).toBe("Quelqu'un a envoyé 100 bits");
  });

  it("should_describe_a_raid", () => {
    const alert: ChatAlert = {
      kind: "raid",
      from_username: "Ange",
      viewers: 42,
    };
    expect(describeAlert(alert)).toBe("Raid de Ange avec 42 spectateurs");
  });
});
