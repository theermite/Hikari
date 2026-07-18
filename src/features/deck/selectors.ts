// Deck key ordering (B4) — pure, testable, Tauri-free.

import type { DeckKey } from "./types";

/** Rust's `HashMap` (`AutomationEngine`'s storage) has an UNSPECIFIED iteration order —
 * without this, the deck's key layout would reshuffle between two identical loads (a
 * palette that visually jumps around breaks the "grab the right key by muscle memory"
 * promise a deck exists for). Sorts by id: stable, deterministic, no locale dependency. */
export function sortDeckKeysById(keys: readonly DeckKey[]): DeckKey[] {
  return [...keys].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}
