#!/usr/bin/env python3
"""Post-compaction brief surface — PostCompact event ONLY.

After a context compaction, surface the handoff brief written by
pre-compact-handoff.py so Takumi knows where to find resume context.

Non-blocking by design (PostCompact cannot block — the compaction has
already happened). Just writes a warning to stderr pointing to the
brief on disk; Takumi reads it on next turn if needed.

Behavior history:
  - 2026-05-17: BLOCKED PreToolUse until CLAUDE.md was re-read. Surfaced
    brief content in the block message.
  - 2026-05-19: simplified. CLAUDE.md is re-injected by the system on
    every turn (it's in the cwd context), and Claude Code v2.0.64+
    auto-compact already preserves identity rules. The hard BLOCK was
    fighting the native behavior instead of cooperating with it. This
    version only points to the brief on disk — Takumi reads it if the
    next task needs the prior context.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from brief_builder import brief_path, read_brief  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input, warn  # noqa: E402


def main() -> None:
    _, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    hook_event = data.get("hook_event_name", "")
    repo = find_repo_root()

    # Only act on PostCompact. Any other event = no-op.
    if hook_event != "PostCompact":
        pass_through()

    handoff_file = brief_path(repo, session_id)
    brief = read_brief(repo, session_id)

    continuity_reminder = (
        "Post-Compact Continuity Rule (Workflows.md): DO NOT propose "
        "/session-end, write a session report, or suggest closing the "
        "session unless Jay has explicitly asked for it in the post-compact "
        "turn. The resumption is a continuation, not a wrap-up. If unclear "
        "what to do next, ASK Jay an open question."
    )

    if brief:
        warn(
            f"Context compaction completed. Handoff brief on disk: "
            f"{handoff_file.as_posix()}. Read it on next turn if you need "
            "explicit recall of files modified, decisions, and in-progress work. "
            f"{continuity_reminder}"
        )
    else:
        # No brief on disk, but the continuity rule still applies.
        warn(continuity_reminder)
    pass_through()


if __name__ == "__main__":
    main()
