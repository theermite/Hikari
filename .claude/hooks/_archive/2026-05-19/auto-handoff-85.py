#!/usr/bin/env python3
"""Auto-handoff at ~85% context — PreToolUse(any tool).

When context is critically loaded, AUTO-WRITE the handoff brief and WARN
(do NOT block) the next tool. Jay can then run /compact at will, knowing
the brief is on disk and will be surfaced on resume by post-compact-recheck.

  1. Brief is built from the transcript (files modified, last user messages,
     recent tool calls, last assistant text) and written to
     `<repo>/.claude/state/handoff-<session_id>.md`.
  2. Warning message recommends `/compact` — which triggers PreCompact +
     PostCompact events, themselves wired to write a fresh snapshot
     (pre-compact-handoff.py) and surface it on resume
     (post-compact-recheck.py).

Heuristic for ~85%:
  - 70+ total turns, OR
  - 45+ Read tool calls, OR
  - 90+ total tool calls

Cap: fires only once per session-id (mark_once). After the first fire, the
brief is on disk and the user has been warned; subsequent passes pass
through silently.

Behavior history:
  - Original (pre 2026-05-17): block-and-force-manual-brief.
  - 2026-05-17: auto-write brief + block once with /compact recommendation.
  - 2026-05-19 (Jay request): WARN instead of BLOCK — write brief, surface
    recommendation, let the next tool run. Avoids the hard freeze when the
    cycle handoff -> /compact -> resume can be a smooth user choice.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from brief_builder import build_brief, brief_path, write_brief  # noqa: E402
from common import (  # noqa: E402
    find_repo_root,
    format_warn,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import count_tool_calls, count_turns  # noqa: E402


THRESH_85_TURNS = 70
THRESH_85_READS = 45
THRESH_85_TOOL_CALLS = 90


def main() -> None:
    _, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")
    repo = find_repo_root()

    user_turns, asst_turns = count_turns(transcript_path)
    total_turns = user_turns + asst_turns
    reads = count_tool_calls(transcript_path, tool_name="Read")
    tools = count_tool_calls(transcript_path)

    over = (
        total_turns >= THRESH_85_TURNS
        or reads >= THRESH_85_READS
        or tools >= THRESH_85_TOOL_CALLS
    )
    if not over:
        pass_through()

    # Fire only once per session — after the first fire the brief is on disk
    # and Jay is aware; further passes should not re-block.
    if not mark_once("auto-handoff-85", "fired", session_id=session_id):
        pass_through()

    # Auto-write the brief BEFORE blocking — never lose state, even if Jay
    # ignores the block and forces continue. If brief write fails for any
    # reason, still block with a clear message.
    handoff_file = brief_path(repo, session_id)
    try:
        content = build_brief(transcript_path, session_id, trigger="auto-85")
        write_brief(content, repo, session_id)
        brief_written = True
    except (OSError, ValueError, KeyError, TypeError):
        brief_written = False

    if brief_written:
        msg = (
            f"Context at ~85% (turns={total_turns}, reads={reads}, tools={tools}). "
            f"Handoff brief AUTO-WRITTEN to {handoff_file.as_posix()}"
        )
        action = (
            "Run `/compact` now. The PreCompact hook will refresh this brief; "
            "PostCompact + post-compact-recheck will surface it on resume so the "
            "session continues with explicit memory. If you prefer a fresh start, "
            "run `/clear` then re-read the brief manually"
        )
    else:
        msg = (
            f"Context at ~85% (turns={total_turns}, reads={reads}, tools={tools}). "
            f"Auto-brief WRITE FAILED — write {handoff_file.as_posix()} manually"
        )
        action = (
            "Write the handoff brief by hand with sections [Done] / [In Progress] / "
            "[Next] / [Decisions] / [Open Questions]. Then run `/compact` or `/clear`"
        )

    warn(format_warn(
        msg,
        action,
        reference="rules/Workflows.md Context Awareness Protocol",
    ))
    pass_through()


if __name__ == "__main__":
    main()
