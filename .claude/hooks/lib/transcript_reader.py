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


def iter_entries(transcript_path: str | Path, reverse: bool = True) -> Iterator[dict[str, Any]]:
    """Yield parsed JSONL entries from the transcript.

    Returns latest-first when reverse=True (default — most hooks scan
    recent activity). Malformed lines are skipped silently.

    Empty/missing transcript yields nothing — caller decides policy.
    """
    p = Path(transcript_path) if transcript_path else None
    if not p or not p.exists():
        return
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if reverse:
        lines = reversed(lines)
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue


def iter_tool_calls(transcript_path: str | Path, tool_name: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield tool_use blocks from assistant messages, latest-first.

    If `tool_name` is given, filter to that tool only ("Read", "Edit", ...).
    Each yielded dict contains at least: name, input.
    """
    for entry in iter_entries(transcript_path):
        # Claude Code transcript shape varies; defensive extraction.
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
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
    if not isinstance(entry, dict):
        return []
    msg = entry.get("message") or entry
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
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
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
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
