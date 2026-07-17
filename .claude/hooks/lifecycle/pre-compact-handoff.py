#!/usr/bin/env python3
"""Pre-compact handoff snapshot — PreCompact event.

Just before Claude Code compresses the conversation context, snapshot a
handoff brief to `<repo>/.claude/state/handoff-<session_id>.md`. After
compaction, post-compact-recheck.py surfaces the brief to Takumi so the
session resumes with explicit memory of files modified, last user intent,
and recent tool calls.

This hook is non-blocking (PreCompact is informational; the compaction
runs regardless). If the brief cannot be written (transcript empty, disk
error), we pass through silently — compaction must not be blocked by a
diagnostic hook.

Cap: writes at most one brief per session per compaction event. If a
brief already exists for this session, it is OVERWRITTEN with the latest
snapshot — the freshest state wins.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from brief_builder import build_brief, write_brief  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input  # noqa: E402


def main() -> None:
    _, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")
    repo = find_repo_root()

    try:
        brief = build_brief(transcript_path, session_id, trigger="pre-compact")
        write_brief(brief, repo, session_id)
    except (OSError, ValueError, KeyError, TypeError):
        # Never block compaction on a diagnostic failure
        pass

    pass_through()


if __name__ == "__main__":
    main()
