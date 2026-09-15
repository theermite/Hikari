"""Read recent entries from the Claude Code transcript JSONL.

The Claude Code harness passes `transcript_path` to every hook event.
This module yields parsed entries from that file, latest-first by default,
so hooks can scan recent assistant text, tool calls, and tool results without
re-implementing JSONL parsing.

Stdlib only. Cross-platform (Windows + Linux).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


# iter_entries: every OSError or ValueError from opening OR READING the file
# (missing file, a permission denial, an unencodable path -- 10th and 11th
# independent reviews, 2026-09-15) is swallowed the same way -- this is a
# best-effort reader, never a hard requirement. It reads the open file object
# directly
# rather than read_text().splitlines() (10th review): str.splitlines() also
# breaks on the Unicode line separators U+2028, U+2029 and NEL (\x85) --
# legal INSIDE a JSON string value (a prompt pasted from Word/PDF, a file
# read by the Read tool), which silently cut one valid entry into two invalid
# ones. Universal-newline text mode only ever splits on \n, \r or \r\n. It
# also avoids loading the whole file into one string before splitting it a
# second time -- measured on a real 63.7 MB transcript: 573.1 MB peak before
# this change (both reverse=True and reverse=False, the two were identical),
# 1.3 MB after for reverse=False (true streaming), 74.6 MB for reverse=True
# (still one list of lines, but only one, and proportional to file size).
def iter_entries(transcript_path: str | Path, reverse: bool = True) -> Iterator[dict[str, Any]]:
    """Yield parsed JSONL entries from the transcript.

    Returns latest-first when reverse=True (default — most hooks scan
    recent activity). Malformed lines are skipped silently. Empty/missing
    transcript yields nothing — caller decides policy.
    """
    p = Path(transcript_path) if transcript_path else None
    if not p:
        return
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            lines = reversed(list(f)) if reverse else f
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
    except (OSError, ValueError):
        return


# entry_message closes a 9-site family (2026-09-14/15, 3 rounds of review):
# a transcript JSON line can be valid yet non-object (`null`), and callers
# assumed a dict. 3 rounds searched for a CODE SHAPE
# ("entry.get('message') or entry") instead of the FAMILY -- context-gauge.py's
# own inline parsing matched neither shape textually and was missed twice.
#
# Importers that want the fallback: iter_tool_calls, assistant_text_blocks and
# count_turns (this file), brief_builder.py, friction.py, logs-first.py,
# reformulate-gate.py, veille-extended.py, hook-blocks-stats.entry_role.
#
# context-gauge.py deliberately does NOT import THIS function: the 6th review
# found its fallback ("no dict message? use the entry itself") made
# context-gauge accept a `usage` field placed flat on the entry, a shape it
# has never accepted (test_a_flat_usage_is_not_accepted). It DOES import
# iter_entries, though (9th review, 2026-09-15): 3 earlier rounds each found
# one more way a hand-rolled copy of file-reading + json.loads in
# context-gauge.py had drifted narrower than this module's own error handling
# -- isinstance on usage, then int()/OverflowError, then json.loads/ValueError,
# each fixed one line higher in the same function. The file-open itself (no
# errors="replace") was the line above all three, and losing THAT one meant
# one bad byte anywhere in the transcript discarded every measurement already
# read, not just the offending line. Delegating the read to iter_entries ends
# the pattern instead of closing it a 4th time.
def entry_message(entry) -> dict | None:
    """The "message" dict a transcript entry carries, or None."""
    if not isinstance(entry, dict):
        return None
    msg = entry.get("message") or entry
    return msg if isinstance(msg, dict) else None


def iter_tool_calls(transcript_path: str | Path, tool_name: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield tool_use blocks from assistant messages, latest-first.

    If `tool_name` is given, filter to that tool only ("Read", "Edit", ...).
    Each yielded dict contains at least: name, input.
    """
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg is None:
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if tool_name and block.get("name") != tool_name:
                continue
            yield block


def assistant_text_blocks(entry: dict) -> list[str]:
    """Text blocks Takumi actually SAID in this one parsed entry, or [].

    Only role == "assistant" counts: a tool_use input or a tool_result's
    content sits in the same JSON tree as his real text blocks but is never
    something he said (independent review, 2026-09-14 -- veille_markers.py and
    veille-extended.py each duplicated this before sharing it here).
    """
    msg = entry_message(entry)
    if msg is None or msg.get("role") != "assistant":
        return []
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    return [b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]


def iter_assistant_text(transcript_path: str | Path, limit: int = 20) -> Iterator[str]:
    """Yield text content from recent assistant messages, latest-first.

    Stops after `limit` text blocks to bound cost. Useful for pattern-scan
    hooks (e.g. rules-vs-memory) that need recent Takumi output.
    """
    count = 0
    for entry in iter_entries(transcript_path):
        if count >= limit:
            return
        for text in assistant_text_blocks(entry):
            yield text
            count += 1
            if count >= limit:
                return


def count_turns(transcript_path: str | Path) -> tuple[int, int]:
    """Return (user_turns, assistant_turns) in the transcript.

    Rough proxy for conversation length. Used by context-awareness hook.
    """
    user, assistant = 0, 0
    for entry in iter_entries(transcript_path, reverse=False):
        msg = entry_message(entry)
        if msg is None:
            continue
        role = msg.get("role")
        if role == "user":
            user += 1
        elif role == "assistant":
            assistant += 1
    return user, assistant


def count_tool_calls(transcript_path: str | Path, tool_name: str | None = None) -> int:
    """Count tool_use blocks in the transcript, optionally filtered by name."""
    return sum(1 for _ in iter_tool_calls(transcript_path, tool_name=tool_name))


def has_read_file(transcript_path: str | Path, file_path_substring: str) -> bool:
    """Return True if any Read tool call references a path containing the substring.

    Match is substring-based (case-sensitive) to tolerate absolute vs relative paths
    and forward/backward slash variations. Caller normalizes input as needed.
    """
    needle = file_path_substring.replace("\\", "/")
    for block in iter_tool_calls(transcript_path, tool_name="Read"):
        fp = (block.get("input") or {}).get("file_path", "") or ""
        if needle in fp.replace("\\", "/"):
            return True
    return False
