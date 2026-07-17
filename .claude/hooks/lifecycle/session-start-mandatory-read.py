#!/usr/bin/env python3
"""Session-start mandatory read gate — PreToolUse(Edit|Bash|Write).

CLAUDE.md declares 3 BLOCKING files Takumi MUST read before any work:
  1. .claude/rules/Interpretation-Protocol.md
  2. .claude/rules/Confidentiality.md
  3. .claude/rules/Monozukuri.md

This hook scans the transcript for Read tool calls on those files. If any
is missing when Takumi first attempts an Edit/Write/Bash (state-mutating
tool), BLOCK with explicit recovery: read the missing files first.

After the gate passes once per session, a state marker is written and
subsequent tool calls pass through silently (no overhead).

Skip cases:
  - The Edit/Write target IS one of the mandatory files (allow editing them)
  - State marker already exists for this session
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import (  # noqa: E402
    block,
    find_repo_root,
    format_block,
    get_command,
    get_file_path,
    pass_through,
    read_hook_input,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import has_read_file  # noqa: E402


MANDATORY_FILES = [
    ".claude/rules/Interpretation-Protocol.md",
    ".claude/rules/Confidentiality.md",
    ".claude/rules/Monozukuri.md",
]


def main() -> None:
    raw, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")
    tool_name = data.get("tool_name") or ""

    # Skip if the target IS one of the mandatory files
    target = get_file_path(data).replace("\\", "/")
    for mf in MANDATORY_FILES:
        if mf in target:
            pass_through()

    # Skip read-only Bash commands (cd, ls, git status, etc.) — only block writes
    if tool_name == "Bash":
        cmd = get_command(data).strip()
        # git pull/fetch are session-start bootstrap mechanics (sync the repo),
        # not work — they must never be gated by the mandatory-read check.
        read_only_prefixes = ("ls", "cd", "pwd", "git status", "git log", "git diff", "git branch",
                              "git pull", "git fetch", "git remote", "git show",
                              "cat", "head", "tail", "grep", "find", "echo", "which", "wc")
        if any(cmd.startswith(p) for p in read_only_prefixes):
            pass_through()

    # One-shot per session: if marker already set, pass through
    if not mark_once("mandatory-read-checked", "checked", session_id=session_id):
        pass_through()

    # Verify all 3 mandatory files were read in this session's transcript
    missing = [mf for mf in MANDATORY_FILES if not has_read_file(transcript_path, mf)]

    if missing:
        # Remove the marker so the gate re-fires until satisfied
        from session_state import read_state, write_state  # local import
        repo = find_repo_root()
        st = read_state("mandatory-read-checked", session_id=session_id, repo_root=repo)
        st["seen"] = []
        write_state("mandatory-read-checked", st, session_id=session_id, repo_root=repo)

        listing = "\n  - ".join([""] + missing)
        block(format_block(
            f"MANDATORY FIRST READ not satisfied — {len(missing)}/3 file(s) unread",
            f"Read the missing file(s) before any Edit/Write/Bash:{listing}\n"
            "These are the BLOCKING files declared in CLAUDE.md (Interpretation-Protocol, "
            "Confidentiality, Monozukuri). They define how Takumi reads every other rule",
            reference="CLAUDE.md MANDATORY FIRST READ",
        ))

    pass_through()


if __name__ == "__main__":
    main()
