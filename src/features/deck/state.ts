// Per-key press state machine (B4) — pure reducer, no React/Tauri: what the UI shows
// while/after a key is pressed. Tested directly (`state.test.ts`), the transitions the
// mission asks for ("logique de sélection/déclenchement de touche", not a snapshot).

import type { DeckTriggerOutcome } from "./types";

export type KeyPressState =
  | { phase: "idle" }
  | { phase: "pressing" }
  | { phase: "dispatched" }
  | { phase: "refused"; reason: string }
  | { phase: "error"; message: string };

export type KeyPressEvent =
  | { type: "press" }
  | { type: "outcome"; outcome: DeckTriggerOutcome }
  | { type: "failed"; message: string };

export const IDLE_KEY_PRESS_STATE: KeyPressState = { phase: "idle" };

/** Advances one key's press state. A `press` while already `pressing` is a no-op — the
 * button is disabled during that phase (`DeckPanel.tsx`), but the reducer holds the same
 * guarantee on its own so a stray double-invoke (e.g. a fast double click racing the
 * disabled-attribute repaint) can never fire the automation twice. */
export function reduceKeyPress(
  current: KeyPressState,
  event: KeyPressEvent,
): KeyPressState {
  switch (event.type) {
    case "press":
      return current.phase === "pressing" ? current : { phase: "pressing" };
    case "outcome":
      return event.outcome.status === "dispatched"
        ? { phase: "dispatched" }
        : { phase: "refused", reason: event.outcome.reason };
    case "failed":
      return { phase: "error", message: event.message };
    default:
      return current;
  }
}
