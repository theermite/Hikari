// Engine lifecycle Tauri bridge (B1 debt payoff, tranche 1) — thin `invoke` wrappers.

import { invoke } from "@tauri-apps/api/core";

/** Starts the continuous engine process (`start_engine`, `engine_lifecycle.rs`) —
 * idempotent, safe to call even if already running. */
export function startEngine(): Promise<void> {
  return invoke("start_engine");
}

/** Stops the engine cleanly (`stop_engine`) — idempotent, safe to call even if not
 * running. */
export function stopEngine(): Promise<void> {
  return invoke("stop_engine");
}

/** Reports the Aperçu panel's real screen rect (`position_preview`) — the engine grafts
 * (or repositions) its preview window there, never the whole app window (option B). */
export function positionPreview(
  x: number,
  y: number,
  width: number,
  height: number,
): Promise<void> {
  return invoke("position_preview", { x, y, width, height });
}

/** Hides the grafted preview without stopping the engine (`hide_preview`) — called when
 * the Aperçu panel's tab becomes inactive (another tab in the same group is shown). */
export function hidePreview(): Promise<void> {
  return invoke("hide_preview");
}
