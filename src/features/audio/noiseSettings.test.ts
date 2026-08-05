import { describe, expect, it } from "vitest";
import {
  hasLevel,
  levelToStrength,
  NOISE_LEVEL_MIN_DB,
  statusLine,
  strengthToLevel,
} from "./noiseSettings";
import type { AudioSourceInfo } from "./types";

const source = (over: Partial<AudioSourceInfo> = {}): AudioSourceInfo => ({
  name: "Micro",
  kind: "input",
  volume_percent: 100,
  monitor_volume_percent: 100,
  muted: false,
  monitoring: "none",
  noise_suppression: false,
  noise_method: "rnnoise",
  noise_level_db: -30,
  ...over,
});

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

describe("statusLine", () => {
  it("should_say_who_hears_the_source", () => {
    expect(statusLine(source({ monitoring: "none" }))).toBe("Public seul");
    expect(statusLine(source({ monitoring: "monitor_only" }))).toBe("Moi seul");
    expect(statusLine(source({ monitoring: "monitor_and_output" }))).toBe(
      "Public + moi",
    );
  });

  it("should_mention_the_noise_filter_only_when_it_is_on", () => {
    // L'état de routage change ce que le public entend : il reste lisible sans ouvrir
    // les réglages.
    expect(statusLine(source({ noise_suppression: true }))).toBe(
      "Public seul · anti-bruit",
    );
    expect(statusLine(source({ noise_suppression: false }))).toBe(
      "Public seul",
    );
  });
});
