// Level-bar maths (B6) — pure, so the meter's behaviour is proven without a running engine.
//
// The engine already sends decibels; this module turns them into what the eye reads. It
// deliberately mirrors the Rust `db_to_meter_fraction`: the same floor, the same scale. Two
// implementations of one rule is a divergence waiting to happen, so any change here must
// change `hikari-protocol` too — the Rust tests pin the same numbers.

/** The quietest level the meter shows. Below this the bar is empty: a bar that stretched to
 * -Infinity would spend its whole length on silence nobody can hear. */
export const METER_FLOOR_DB = -60;

/** Above this level the signal is close to clipping — the bar turns red to say so before it
 * distorts, rather than after. */
export const METER_DANGER_DB = -3;

/** Above this the signal is comfortably loud: the useful working range. */
export const METER_GOOD_DB = -20;

/** Bar length, `0..1`, linear in decibels — which is how loudness is actually perceived. A
 * bar linear in amplitude would sit near zero for every normal speaking level.
 * Non-finite input (silence arrives as -Infinity) reads as empty, never as NaN. */
export function meterFraction(db: number): number {
  if (!Number.isFinite(db)) return db === Infinity ? 1 : 0;
  return Math.min(1, Math.max(0, 1 - db / METER_FLOOR_DB));
}

/** Which of the three zones a level falls in. Colour is decided from this, never from the
 * raw number scattered through the markup. */
export type MeterZone = "quiet" | "good" | "danger";

export function meterZone(db: number): MeterZone {
  if (!Number.isFinite(db)) return db === Infinity ? "danger" : "quiet";
  if (db >= METER_DANGER_DB) return "danger";
  if (db >= METER_GOOD_DB) return "good";
  return "quiet";
}

/** A readable label for a level. Silence says so in words rather than showing "-Infinity dB",
 * which reads like a bug to anyone who is not an audio engineer. */
export function formatLevel(db: number): string {
  if (!Number.isFinite(db) || db <= METER_FLOOR_DB) return "silence";
  return `${db.toFixed(0)} dB`;
}
