// Mirrors `PreflightOutcome` (preflight_bridge.rs) — one real check result, never a
// presumed default (F-003): either an encoder was actually detected, or Go Live is
// blocked with the reason shown (F-012).

export interface PreflightOutcome {
  ok: boolean;
  encoder_name: string | null;
  hardware: boolean | null;
  reason: string | null;
}
