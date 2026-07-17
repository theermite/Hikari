#!/usr/bin/env python3
"""Simple Language inject — UserPromptSubmit companion hook.

Companion of .claude/hooks/quality/simple-language-check.py (Stop hook).

Pipeline (Option A — Jay 2026-06-01):

  1. Stop hook (simple-language-check) detects Simple Language violations
     in Takumi's response. WARNs on stderr (Jay's console) AND persists
     the violations to .claude/state/simple-language-violations-<session>.json
     with `pending: true`.

  2. THIS hook runs at the next UserPromptSubmit (Jay's next turn). If
     `pending: true`, it injects the violations into Takumi's context
     via stdout (UserPromptSubmit hooks' stdout becomes additional
     context for the model). Then it marks `pending: false` so the
     same violations are not re-injected in subsequent turns.

Why this exists:
  Stop hook cannot rewrite an already-emitted response. WARN on stderr
  is invisible to Takumi (he sees the conversation, not Jay's console).
  Without next-turn injection, Takumi receives no observable cost for
  violating Simple Language — the rule decays into ignored prose.
  This hook is the functional equivalent of BLOCKING for a Stop hook:
  Takumi reads his own violations in the next turn and self-corrects.

Output format on stdout (becomes additional context for the model):
    [SIMPLE LANGUAGE — REPONSE PRECEDENTE VIOLAIT Honesty.md]
    - <violation 1>
    - <violation 2>
    ...
    Honesty.md contraintes 1-8: phrase <= 25 mots, paragraphe <= 3
    phrases, max 1 acronyme/phrase, max 6 paragraphes prose, tableau si
    comparaison, analogie si concept abstrait, POURQUOI obligatoire.
    Reformuler MAINTENANT, pas "la prochaine fois".

Non-blocking: any error -> exit 0 silent (never break the prompt).
Idempotent: once injected, marks `pending: false` so subsequent prompts
don't re-inject the same violations.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402


STATE_NAME = "simple-language-violations"
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
        "[SIMPLE LANGUAGE — REPONSE PRECEDENTE VIOLAIT Honesty.md]\n"
    )
    for v in violations[:MAX_VIOLATIONS_INJECTED]:
        sys.stdout.write(f"  - {v}\n")
    if len(violations) > MAX_VIOLATIONS_INJECTED:
        sys.stdout.write(
            f"  (+{len(violations) - MAX_VIOLATIONS_INJECTED} autres)\n"
        )
    sys.stdout.write(
        "Honesty.md langue claire (client <-> maitre expert): conclusion "
        "d'abord (BLUF), phrase <= 25 mots, paragraphe <= 3 phrases, max 1 "
        "jargon/phrase glose, <= 3 paragraphes prose, zero condescendance, "
        "tableau si comparaison, POURQUOI obligatoire. Reformuler MAINTENANT.\n"
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
