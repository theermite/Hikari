import { afterEach, describe, expect, it, vi } from "vitest";
import { setSourceTransform, showMediaFor } from "../scenes/api";
import { requestScreen } from "../shell/panelActions";
import {
  DEFAULT_MEDIA_SCALE_PERCENT,
  placeNewAlertMedia,
  previewAlertMedia,
  ruleForAlert,
  TEST_SHOW_DELAY_MS,
} from "./alertMedia";
import type { ChatSettings } from "./chatSettings";
import type { ChatAlert } from "./types";

vi.mock("../scenes/api", () => ({
  showMediaFor: vi.fn(() => Promise.resolve()),
  setSourceTransform: vi.fn(() => Promise.resolve()),
}));
vi.mock("../shell/panelActions", () => ({ requestScreen: vi.fn() }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn() }));

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

describe("previewAlertMedia", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("should_show_the_cockpit_first_and_the_media_only_after_a_delay", () => {
    // Le chrono du média court dès qu'il s'allume : le lancer avant que l'aperçu soit
    // revenu à l'écran le ferait s'éteindre pendant le changement d'écran, sans que
    // personne ne l'ait vu.
    vi.useFakeTimers();

    previewAlertMedia("follow", 3_000);

    expect(requestScreen).toHaveBeenCalledWith("cockpit");
    expect(showMediaFor).not.toHaveBeenCalled();

    vi.advanceTimersByTime(TEST_SHOW_DELAY_MS);

    expect(showMediaFor).toHaveBeenCalledExactlyOnceWith(
      expect.any(String),
      "follow",
      3_000,
    );
  });
});

describe("placeNewAlertMedia", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should_shrink_a_new_media_instead_of_leaving_it_at_its_native_size", async () => {
    // Une image d'emote fait couramment 1592 px : à 100 % elle recouvre tout l'aperçu
    // (Jay, 2026-10-13 : « la taille est beaucoup trop grosse »).
    await placeNewAlertMedia("follow");

    expect(setSourceTransform).toHaveBeenCalledExactlyOnceWith(
      expect.any(String),
      "follow",
      expect.any(Number),
      expect.any(Number),
      DEFAULT_MEDIA_SCALE_PERCENT,
    );
    expect(DEFAULT_MEDIA_SCALE_PERCENT).toBeLessThan(100);
  });
});
