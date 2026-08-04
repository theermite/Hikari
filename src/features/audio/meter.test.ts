import { describe, expect, it } from "vitest";
import { formatLevel, METER_FLOOR_DB, meterFraction, meterZone } from "./meter";

describe("meterFraction", () => {
  it("should_fill_the_bar_at_zero_decibels", () => {
    expect(meterFraction(0)).toBe(1);
  });

  it("should_empty_the_bar_at_the_floor", () => {
    expect(meterFraction(METER_FLOOR_DB)).toBe(0);
  });

  it("should_empty_the_bar_on_silence_rather_than_showing_NaN", () => {
    // Le moteur signale le silence par -Infinity : la barre doit rester vide.
    expect(meterFraction(-Infinity)).toBe(0);
    expect(meterFraction(Number.NaN)).toBe(0);
  });

  it("should_half_fill_the_bar_at_half_the_floor", () => {
    expect(meterFraction(METER_FLOOR_DB / 2)).toBe(0.5);
  });

  it("should_cap_the_bar_above_zero_rather_than_overflowing", () => {
    expect(meterFraction(12)).toBe(1);
  });

  it("should_never_leave_the_zero_to_one_range", () => {
    for (const db of [-500, -60.1, -30, -0.1, 0, 3, 200]) {
      const fraction = meterFraction(db);
      expect(fraction).toBeGreaterThanOrEqual(0);
      expect(fraction).toBeLessThanOrEqual(1);
    }
  });

  it("should_never_show_a_louder_signal_as_a_shorter_bar", () => {
    // Monotonie : la barre ne ment jamais sur qui est le plus fort.
    const samples = [-60, -45, -30, -20, -10, -3, 0];
    for (let i = 1; i < samples.length; i++) {
      expect(meterFraction(samples[i])).toBeGreaterThanOrEqual(
        meterFraction(samples[i - 1]),
      );
    }
  });
});

describe("meterZone", () => {
  it("should_call_a_near_clipping_level_dangerous", () => {
    expect(meterZone(-1)).toBe("danger");
    expect(meterZone(0)).toBe("danger");
  });

  it("should_call_a_normal_speaking_level_good", () => {
    expect(meterZone(-12)).toBe("good");
  });

  it("should_call_a_barely_audible_level_quiet", () => {
    expect(meterZone(-45)).toBe("quiet");
  });

  it("should_call_silence_quiet_rather_than_dangerous", () => {
    expect(meterZone(-Infinity)).toBe("quiet");
  });
});

describe("formatLevel", () => {
  it("should_say_silence_in_words_rather_than_minus_infinity", () => {
    // « -Infinity dB » se lit comme un bug pour qui n'est pas ingénieur du son.
    expect(formatLevel(-Infinity)).toBe("silence");
    expect(formatLevel(-90)).toBe("silence");
  });

  it("should_show_a_rounded_decibel_value_when_audible", () => {
    expect(formatLevel(-18.4)).toBe("-18 dB");
  });
});
