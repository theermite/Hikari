#!/usr/bin/env python3
"""LOGS FIRST gate — PreToolUse Edit.

Enforces Workflows.md "LOGS FIRST" rule: on any bug fix sequence, logs
MUST be read BEFORE hypothesizing on the cause.

Detection heuristic:
  - Look at recent tool calls in the current turn (since last user message)
  - If pattern detected: [Bash that failed (exit != 0 OR stderr non-empty)] -> [Edit being attempted]
  - Without a Read of logs/error/stderr between -> WARN (not block, since
    detection is heuristic and can have false positives)

The hook is intentionally non-blocking — it nudges Takumi to verify logs
were consulted rather than jumping to a fix. A false positive (legitimate
quick edit) should not stop the workflow.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import get_file_path, pass_through, read_hook_input, warn  # type: ignore
from transcript_reader import iter_entries  # type: ignore

# Keywords suggesting log/error inspection
LOG_KEYWORDS = re.compile(
    r"(log|logs|stderr|stdout|error|traceback|exception|stacktrace|"
    r"\.log\b|/var/log|journalctl|docker logs|tail -f|tail -n)",
    re.IGNORECASE,
)


def analyze_recent_sequence(transcript_path: str) -> tuple[bool, bool]:
    """Return (had_failed_bash, read_logs_after).

    Walks back to last user message, tracks tool sequence in chronological order.
    """
    if not transcript_path:
        return False, True  # No transcript = pass

    entries_reversed = list(iter_entries(transcript_path))
    # Find last user message index, then take entries AFTER it (chronological)
    entries_after_user: list[dict] = []
    for entry in entries_reversed:
        msg = entry.get("message") or entry
        if isinstance(msg, dict) and msg.get("role") == "user":
            break
        entries_after_user.append(entry)
    entries_after_user.reverse()  # Now chronological within current turn

    had_failed_bash = False
    read_logs_after_fail = False

    for entry in entries_after_user:
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue

        for blk in content:
            if not isinstance(blk, dict):
                continue
            btype = blk.get("type")

            if btype == "tool_use":
                name = blk.get("name", "")
                inp = blk.get("input") or {}
                if name == "Bash":
                    # Track that a Bash was attempted; failure detection comes from tool_result
                    pass
                elif name == "Read":
                    fp = (inp.get("file_path") or "").lower()
                    if had_failed_bash and LOG_KEYWORDS.search(fp):
                        read_logs_after_fail = True
                elif name == "Grep":
                    pat = (inp.get("pattern") or "").lower()
                    if had_failed_bash and LOG_KEYWORDS.search(pat):
                        read_logs_after_fail = True
                elif name == "Bash":
                    cmd = (inp.get("command") or "").lower()
                    if had_failed_bash and LOG_KEYWORDS.search(cmd):
                        read_logs_after_fail = True

            elif btype == "tool_result":
                # Look for failure indicators in result text
                tr_content = blk.get("content")
                tr_text = ""
                if isinstance(tr_content, str):
                    tr_text = tr_content
                elif isinstance(tr_content, list):
                    for c in tr_content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            tr_text += c.get("text", "")
                is_error = blk.get("is_error", False)
                # Heuristic: tool_result mentions error/exit code/stderr
                if is_error or re.search(
                    r"(error|exit\s*code\s*[1-9]|stderr|exception|failed|traceback)",
                    tr_text,
                    re.IGNORECASE,
                ):
                    had_failed_bash = True

    return had_failed_bash, read_logs_after_fail


def main() -> None:
    _, data = read_hook_input()
    file_path = get_file_path(data)
    if not file_path:
        pass_through()

    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    had_fail, read_logs = analyze_recent_sequence(transcript_path)

    if not had_fail or read_logs:
        pass_through()

    warn(
        "WARNING: LOGS FIRST — a failed command was detected this turn but no logs "
        "appear to have been read before this Edit. "
        f"Target: {file_path}. "
        "ACTION: If you're fixing a bug, read the relevant log/error output first "
        "(Read tool on log file, or Grep for the error message). "
        "If you've already analyzed the failure (visible in tool_result), continue. "
        "See rules/Workflows.md 'Read logs before hypothesizing'."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
