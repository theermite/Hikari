#!/usr/bin/env python3
"""Clock-is-not-fatigue inject — UserPromptSubmit companion hook.

Companion of .claude/hooks/quality/clock-not-fatigue-check.py (Stop hook).

Pipeline (Option A):
  1. Stop hook detects a clock->brake link in Takumi's response, WARNs on
     stderr and persists it to clock-fatigue-violations-<session>.json
     with pending:true.
  2. THIS hook runs at the next UserPromptSubmit. If pending, it injects the
     violation into Takumi's context via stdout (UserPromptSubmit stdout
     becomes additional context), then marks pending:false (idempotent).

Why: a Stop hook cannot rewrite an already-emitted response; WARN on stderr
is invisible to Takumi. Next-turn injection is the functional equivalent of
BLOCKING — Takumi reads his own violation next turn and self-corrects.

Non-blocking: any error -> exit 0 silent (never break the prompt).
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402


STATE_NAME = "clock-fatigue-violations"
MAX_VIOLATIONS_INJECTED = 8


def _clear(session_id: str) -> None:
    """Mark the violations state consumed so the next turn doesn't re-inject."""
    write_state(
        STATE_NAME,
        {"pending": False, "violations": []},
        session_id=session_id or None,
    )


def _inject(violations: list[str]) -> None:
    """Write the pending violations into Takumi's next context (stdout)."""
    sys.stdout.write(
        "[HORLOGE ≠ FATIGUE — REPONSE PRECEDENTE VIOLAIT Identity.md]\n"
    )
    for v in violations[:MAX_VIOLATIONS_INJECTED]:
        sys.stdout.write(f"  - {v}\n")
    if len(violations) > MAX_VIOLATIONS_INJECTED:
        sys.stdout.write(
            f"  (+{len(violations) - MAX_VIOLATIONS_INJECTED} autres)\n"
        )
    sys.stdout.write(
        "Identity.md « The Clock Is Not a Fatigue Signal » (BLOCKING): "
        "l'heure injectée sert UNIQUEMENT aux salutations. Jamais pour "
        "refuser, différer, raccourcir le travail, réduire le périmètre, "
        "suggérer d'arrêter, ni inférer que Jay est fatigué. L'état de Jay se "
        "lit SEULEMENT dans ses signaux explicites en conversation. "
        "Reformuler MAINTENANT sans le frein lié à l'heure.\n"
    )
    sys.stdout.flush()


def main() -> None:
    try:
        _, data = read_hook_input()
        session_id = data.get("session_id") or ""

        state = read_state(STATE_NAME, session_id=session_id or None)
        if not state.get("pending"):
            sys.exit(0)

        violations = state.get("violations") or []
        if violations:
            _inject(violations)
        _clear(session_id)
        sys.exit(0)
    except Exception:
        # Never break the user's prompt
        sys.exit(0)


if __name__ == "__main__":
    main()
