import { describe, expect, it } from "vitest";
import {
  DEFAULT_PRESET,
  isKnownPreset,
  PRESETS,
  resolvePreset,
} from "./presets";

describe("presets", () => {
  it("should_switch_preset_when_selected", () => {
    expect(resolvePreset("live")).toBe("live");
    expect(resolvePreset("focus")).toBe("focus");
    expect(resolvePreset("preparation")).toBe("preparation");
  });

  it("should_fall_back_to_default_when_saved_value_is_unknown", () => {
    // A stale/foreign value (e.g. a future Hikari version's new preset id read by an older
    // build) must never propagate as-is — silently falling back is the safe behavior.
    expect(resolvePreset("some-future-preset")).toBe(DEFAULT_PRESET);
  });

  it("should_fall_back_to_default_when_nothing_was_ever_saved", () => {
    expect(resolvePreset(null)).toBe(DEFAULT_PRESET);
  });

  it("should_recognize_exactly_the_declared_presets", () => {
    for (const preset of PRESETS) {
      expect(isKnownPreset(preset.id)).toBe(true);
    }
    expect(isKnownPreset("not-a-real-preset")).toBe(false);
  });
});
