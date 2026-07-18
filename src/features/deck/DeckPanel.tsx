// Deck panel (B4, PET §7ter) — the local deck as a real dockview panel. Fetches
// button-triggered automations from the engine (`deck_list_keys`) and dispatches a
// press locally (`deck_trigger_key`), both sub-100ms, both offline (`deck_bridge.rs`).
//
// Honest scope: only the "automation key" kind is wired end to end today (see
// `deck_bridge.rs` module doc) — no fake state-toggle/value/board-switch keys are
// rendered here (Dignity.md). An empty deck at first launch is shown as what it is:
// nothing assigned yet, not an error.

import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useState } from "react";
import { listDeckKeys, triggerDeckKey } from "./api";
import { sortDeckKeysById } from "./selectors";
import {
  IDLE_KEY_PRESS_STATE,
  type KeyPressState,
  reduceKeyPress,
} from "./state";
import type { DeckKey } from "./types";

const KEY_STYLE_BY_PHASE: Record<KeyPressState["phase"], string> = {
  idle: "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt",
  pressing: "border-hikari-accent text-hikari-accent",
  dispatched: "border-hikari-green text-hikari-green",
  refused: "border-hikari-red text-hikari-red",
  error: "border-hikari-red text-hikari-red",
};

export function DeckPanel(_props: IDockviewPanelProps) {
  const [keys, setKeys] = useState<DeckKey[] | null>(null);
  const [pressStates, setPressStates] = useState<Record<string, KeyPressState>>(
    {},
  );

  useEffect(() => {
    let cancelled = false;
    listDeckKeys()
      .then((fetched) => {
        if (!cancelled) setKeys(sortDeckKeysById(fetched));
      })
      .catch(() => {
        // Engine unreachable at boot — an empty deck is the honest fallback, never a
        // silent retry loop or a fake key (Dignity.md).
        if (!cancelled) setKeys([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const press = useCallback((id: string) => {
    setPressStates((prev) => {
      const current = prev[id] ?? IDLE_KEY_PRESS_STATE;
      // Bails out (both the state update AND the call below) while already pressing —
      // the reducer's own guard (`state.ts`) prevents a double-press from firing the
      // automation twice even if this callback somehow re-entered.
      if (current.phase === "pressing") return prev;
      return { ...prev, [id]: reduceKeyPress(current, { type: "press" }) };
    });

    triggerDeckKey(id)
      .then((outcome) => {
        setPressStates((prev) => ({
          ...prev,
          [id]: reduceKeyPress(prev[id] ?? IDLE_KEY_PRESS_STATE, {
            type: "outcome",
            outcome,
          }),
        }));
      })
      .catch((error: unknown) => {
        setPressStates((prev) => ({
          ...prev,
          [id]: reduceKeyPress(prev[id] ?? IDLE_KEY_PRESS_STATE, {
            type: "failed",
            message: String(error),
          }),
        }));
      });
  }, []);

  if (keys === null) {
    return (
      <div className="flex h-full items-center justify-center bg-hikari-bg-3 p-6 text-hikari-txt-faint">
        <p className="text-sm">Chargement du deck…</p>
      </div>
    );
  }

  if (keys.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 bg-hikari-bg-3 p-6 text-center text-hikari-txt-faint">
        <p className="text-sm">Aucune touche assignée pour l'instant.</p>
        <p className="text-xs">
          Crée une automation à déclencheur bouton (écran Automations, bientôt)
          pour la voir apparaître ici.
        </p>
      </div>
    );
  }

  return (
    <div className="grid h-full auto-rows-min grid-cols-3 gap-2 overflow-y-auto bg-hikari-bg-3 p-3">
      {keys.map((key) => {
        const state = pressStates[key.id] ?? IDLE_KEY_PRESS_STATE;
        return (
          <button
            key={key.id}
            type="button"
            onClick={() => press(key.id)}
            disabled={state.phase === "pressing"}
            className={`flex aspect-[1.35] flex-col items-center justify-center gap-1 rounded-hikari-s border p-1 text-center text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${KEY_STYLE_BY_PHASE[state.phase]}`}
          >
            <span>{key.label}</span>
            {state.phase === "refused" && (
              <span className="text-[9px] font-semibold uppercase tracking-wide">
                {state.reason}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
