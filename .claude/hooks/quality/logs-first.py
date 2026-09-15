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
from transcript_reader import entry_message, iter_entries  # type: ignore

# Keywords suggesting log/error inspection
LOG_KEYWORDS = re.compile(
    r"(log|logs|stderr|stdout|error|traceback|exception|stacktrace|"
    r"\.log\b|/var/log|journalctl|docker logs|tail -f|tail -n)",
    re.IGNORECASE,
)


def _entries_since_last_user(transcript_path: str) -> list[dict]:
    """Entries after the last user message, chronological order."""
    after: list[dict] = []
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg is not None and msg.get("role") == "user":
            break
        after.append(entry)
    after.reverse()
    return after


def _reads_logs(name: str, inp: dict) -> bool:
    """True if this tool_use block's target text mentions logs/errors.

    "Bash" is deliberately absent from the map: the pre-refactor code had a
    dead `if name == "Bash": pass` branch here, so a Bash command mentioning
    log keywords never counted. 4th independent review (2026-09-15): keeping
    the split-out function iso-behaviour matters more than completing a
    heuristic no one asked to widen -- resurrecting the branch loosened a
    gate silently. Widening this is a real decision, not a refactor side
    effect; make it its own change, with its own test, if it's wanted.
    """
    target = {
        "Read": inp.get("file_path"),
        "Grep": inp.get("pattern"),
    }.get(name)
    return bool(target) and bool(LOG_KEYWORDS.search(target.lower()))


_FAILURE_RE = re.compile(
    r"(error|exit\s*code\s*[1-9]|stderr|exception|failed|traceback)", re.IGNORECASE
)


def _tool_result_text(blk: dict) -> str:
    content = blk.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")


def _looks_like_failure(blk: dict) -> bool:
    return bool(blk.get("is_error")) or bool(_FAILURE_RE.search(_tool_result_text(blk)))


def _scan_block(blk: dict, had_failed_bash: bool) -> tuple[bool, bool]:
    """One content block's contribution: (marks a failure, reads logs after one)."""
    btype = blk.get("type")
    if btype == "tool_use":
        return False, had_failed_bash and _reads_logs(blk.get("name", ""), blk.get("input") or {})
    if btype == "tool_result":
        return _looks_like_failure(blk), False
    return False, False


def analyze_recent_sequence(transcript_path: str) -> tuple[bool, bool]:
    """Return (had_failed_bash, read_logs_after).

    Walks back to last user message, tracks tool sequence in chronological order.
    """
    if not transcript_path:
        return False, True  # No transcript = pass

    had_failed_bash = False
    read_logs_after_fail = False

    for entry in _entries_since_last_user(transcript_path):
        msg = entry_message(entry)
        if msg is None:
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            failed, read_after = _scan_block(blk, had_failed_bash)
            had_failed_bash = had_failed_bash or failed
            read_logs_after_fail = read_logs_after_fail or read_after

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
