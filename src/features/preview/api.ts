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
