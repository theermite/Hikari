import { describe, expect, it } from "vitest";
import {
  hasLevel,
  levelToStrength,
  NOISE_LEVEL_MIN_DB,
  strengthToLevel,
} from "./noiseSettings";

describe("hasLevel", () => {
  it("should_offer_a_strength_on_the_light_method_only", () => {
    // Contre-intuitif : c'est la méthode ancienne qui est réglable, pas celle par
    // apprentissage. Vérifié dans la source obs-filters.
    expect(hasLevel("speex")).toBe(true);
    expect(hasLevel("rnnoise")).toBe(false);
  });
});

describe("levelToStrength / strengthToLevel", () => {
  it("should_show_the_strongest_suppression_as_full_strength", () => {
    // L'échelle du moteur est inversée : -60 dB est le PLUS fort.
    expect(levelToStrength(NOISE_LEVEL_MIN_DB)).toBe(100);
  });

  it("should_show_no_suppression_as_zero_strength", () => {
    expect(levelToStrength(0)).toBe(0);
  });

  it("should_show_the_obs_default_as_half_strength", () => {
    expect(levelToStrength(-30)).toBe(50);
  });

  it("should_be_the_exact_reciprocal", () => {
    for (const strength of [0, 25, 50, 75, 100]) {
      expect(levelToStrength(strengthToLevel(strength))).toBe(strength);
    }
  });

  it("should_clamp_a_level_beyond_the_engine_range", () => {
    expect(levelToStrength(-200)).toBe(100);
    expect(levelToStrength(50)).toBe(0);
  });

  it("should_read_a_broken_level_as_zero_rather_than_NaN", () => {
    expect(levelToStrength(Number.NaN)).toBe(0);
    expect(levelToStrength(-Infinity)).toBe(0);
  });

  it("should_never_send_a_level_outside_the_engine_range", () => {
    for (const strength of [-50, 0, 50, 100, 500]) {
      const level = strengthToLevel(strength);
      expect(level).toBeGreaterThanOrEqual(NOISE_LEVEL_MIN_DB);
      expect(level).toBeLessThanOrEqual(0);
    }
  });
});
