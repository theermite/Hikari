// Deck data shapes (B4, PET §7ter) — mirrors `src-tauri/src/deck_bridge.rs` verbatim
// (`DeckKey`, `DeckTriggerOutcome`); the frontend never invents its own shape for what
// the backend already defines (ADR-011: the deck is a CLIENT, not a second model).

/** One assignable deck key — today, always a button-triggered automation
 * (`deck_eligible_automations()`, ADR-012). */
export interface DeckKey {
  id: string;
  label: string;
}

/** What happened when a key was pressed — a closed union, matching the Rust
 * `#[serde(tag = "status")]` enum so a caller can never mistake "refused" for "ran". */
export type DeckTriggerOutcome =
  | { status: "dispatched" }
  | { status: "refused"; reason: string };
