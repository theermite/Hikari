#!/usr/bin/env python3
"""Context awareness warning — PreToolUse(any tool).

Workflows.md "Context Awareness Protocol" requires Takumi to announce when
context is at ~60% and STOP at ~80%. The model frequently forgets without a
forcing function. This hook emits a stderr WARNING at thresholds, throttled
to one fire per threshold per session.

Heuristic estimate (the hook does not see the real token budget):
  - Count user + assistant turns in transcript.
  - Count Read tool calls (the heaviest context contributors).
  - Map to rough % bands:
      60% threshold: 40+ turns OR 25+ Reads
      80% threshold: 60+ turns OR 40+ Reads

These are deliberate underestimates — better to warn early than late.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import format_warn, pass_through, read_hook_input, warn  # noqa: E402
from session_state import mark_once  # noqa: E402
from transcript_reader import count_tool_calls, count_turns  # noqa: E402


THRESH_60_TURNS = 40
THRESH_60_READS = 25
THRESH_80_TURNS = 60
THRESH_80_READS = 40


def main() -> None:
    _, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")

    user_turns, asst_turns = count_turns(transcript_path)
    total_turns = user_turns + asst_turns
    reads = count_tool_calls(transcript_path, tool_name="Read")

    hit_80 = total_turns >= THRESH_80_TURNS or reads >= THRESH_80_READS
    hit_60 = total_turns >= THRESH_60_TURNS or reads >= THRESH_60_READS

    if hit_80 and mark_once("context-awareness", "80", session_id=session_id):
        warn(format_warn(
            f"Context at ~80% (turns={total_turns}, reads={reads})",
            "STOP soon. Write handoff brief (done/next/decisions), then suggest /clear",
            reference="rules/Workflows.md Context Awareness Protocol",
        ))
    elif hit_60 and mark_once("context-awareness", "60", session_id=session_id):
        warn(format_warn(
            f"Context at ~60% (turns={total_turns}, reads={reads})",
            "Prioritize remaining tasks. Avoid new exploratory reads",
            reference="rules/Workflows.md Context Awareness Protocol",
        ))

    pass_through()


if __name__ == "__main__":
    main()
