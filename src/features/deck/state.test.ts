import { describe, expect, it } from "vitest";
import { IDLE_KEY_PRESS_STATE, reduceKeyPress } from "./state";

describe("reduceKeyPress", () => {
  it("should_enter_pressing_when_pressed_from_idle", () => {
    const next = reduceKeyPress(IDLE_KEY_PRESS_STATE, { type: "press" });
    expect(next).toEqual({ phase: "pressing" });
  });

  it("should_ignore_press_when_already_pressing", () => {
    const pressing = reduceKeyPress(IDLE_KEY_PRESS_STATE, { type: "press" });
    const next = reduceKeyPress(pressing, { type: "press" });
    // Same reference, not just equal shape — proves the guard short-circuits instead of
    // producing a fresh (equal-looking) object that would still count as a re-render.
    expect(next).toBe(pressing);
  });

  it("should_show_dispatched_when_outcome_dispatched", () => {
    const pressing = reduceKeyPress(IDLE_KEY_PRESS_STATE, { type: "press" });
    const next = reduceKeyPress(pressing, {
      type: "outcome",
      outcome: { status: "dispatched" },
    });
    expect(next).toEqual({ phase: "dispatched" });
  });

  it("should_show_refusal_reason_when_outcome_refused", () => {
    const pressing = reduceKeyPress(IDLE_KEY_PRESS_STATE, { type: "press" });
    const next = reduceKeyPress(pressing, {
      type: "outcome",
      outcome: { status: "refused", reason: "Inactive" },
    });
    expect(next).toEqual({ phase: "refused", reason: "Inactive" });
  });

  it("should_show_error_message_when_dispatch_fails", () => {
    const pressing = reduceKeyPress(IDLE_KEY_PRESS_STATE, { type: "press" });
    const next = reduceKeyPress(pressing, {
      type: "failed",
      message: "IPC indisponible",
    });
    expect(next).toEqual({ phase: "error", message: "IPC indisponible" });
  });

  it("should_allow_pressing_again_after_a_previous_outcome", () => {
    const dispatched = reduceKeyPress(IDLE_KEY_PRESS_STATE, {
      type: "outcome",
      outcome: { status: "dispatched" },
    });
    const next = reduceKeyPress(dispatched, { type: "press" });
    expect(next).toEqual({ phase: "pressing" });
  });
});
