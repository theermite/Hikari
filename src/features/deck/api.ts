// Deck Tauri bridge (B4) — thin `invoke` wrappers, one call each, no logic here (the
// logic worth testing lives in `state.ts`/`selectors.ts`, pure and Tauri-free).

import { invoke } from "@tauri-apps/api/core";
import type { DeckKey, DeckTriggerOutcome } from "./types";

/** Deck-eligible automations, as delivered by `deck_list_keys` (`deck_bridge.rs`). */
export function listDeckKeys(): Promise<DeckKey[]> {
  return invoke("deck_list_keys");
}

/** Presses key `id` — decides + dispatches locally, no network round-trip
 * (`deck_trigger_key`, `deck_bridge.rs`). */
export function triggerDeckKey(id: string): Promise<DeckTriggerOutcome> {
  return invoke("deck_trigger_key", { id });
}
