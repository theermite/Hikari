// Preflight Tauri bridge (B9) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { PreflightOutcome } from "./types";

/** Runs a real pré-vol check (`run_preflight`, `preflight_bridge.rs`) — spawns the
 * engine in one-shot detection mode, never presumes an encoder (F-003). */
export function runPreflight(): Promise<PreflightOutcome> {
  return invoke("run_preflight");
}
