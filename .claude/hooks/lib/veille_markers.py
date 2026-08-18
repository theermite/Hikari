"""Marker reading for the veille / SKB evidence guard.

Reads the session transcript and answers:

  latest_marker()       — the most recent [VEILLE] / [SKB] / [VEILLE-SKIP]
  has_web_veille_call() — did a REAL web tool call happen this session?

The second one is the proof that separates a claim from a fact: marker text
can be typed, a tool call cannot be faked.

Extracted from guards/pre-code-veille-check.py on 2026-08-18. One deliberate
change during the move: the marker fingerprint switched from SHA-1 to SHA-256
(write-guard.py refuses weak hashes, Security.md). The digest is a per-session
dedup key, never a security primitive, so only its value changes — a marker is
still counted exactly once.

Stdlib only. Cross-platform (Windows + Linux).
"""

from __future__ import annotations

import hashlib
import json
import os

from transcript_reader import iter_tool_calls
from veille_config import (
    MARKER_RE,
    RECOVERY_LINE_HINTS,
    TRANSCRIPT_SCAN_LIMIT,
    WEB_TOOL_NAMES_EXACT,
    WEB_TOOL_SUBSTRINGS,
)


def extract_text(entry) -> str:
    chunks: list[str] = []

    def walk(node):
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for _, v in node.items():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(entry)
    return "\n".join(chunks)


def _entry_text(raw: str) -> str:
    """Plain text of a transcript line, with our own recovery/block lines removed
    (they contain literal marker templates that would otherwise be re-matched)."""
    try:
        text = extract_text(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        text = raw
    kept = [ln for ln in text.splitlines()
            if not any(h in ln for h in RECOVERY_LINE_HINTS)]
    return "\n".join(kept)


def _concrete_markers(text: str) -> list:
    """MARKER_RE matches that are real, not angle-bracket / set-repr templates
    (e.g. the literal "[VEILLE] <techno>@<version> ..." in a recovery message)."""
    return [m for m in MARKER_RE.finditer(text)
            if "<" not in m.group(0) and "{" not in m.group(0)]


DIGEST_ALGO = "sha256"


def marker_digest(marker_line: str) -> str:
    """Short fingerprint used to count a given marker exactly once per session.

    Callers persist DIGEST_ALGO next to the value: a state carrying another
    algorithm holds a fingerprint that cannot be recomputed, and comparing it
    to a fresh one would read an unchanged marker as a new one.
    """
    return hashlib.sha256(marker_line.encode("utf-8")).hexdigest()[:16]


def latest_marker(transcript_path: str) -> tuple[str, str, str] | None:
    """Return (marker_type, marker_line, hash) of the most recent marker, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    for raw in reversed(lines[-TRANSCRIPT_SCAN_LIMIT:]):
        raw = raw.strip()
        if not raw:
            continue
        matches = _concrete_markers(_entry_text(raw))
        if matches:
            line = matches[-1].group(0).strip()
            return matches[-1].group(1), line, marker_digest(line)
    return None


def has_web_veille_call(transcript_path: str) -> bool:
    """True if a real web tool call (WebSearch/WebFetch/MCP web) happened.

    Scope is session-wide on purpose: under plan mode (Chantier B) the veille
    is performed in the plan phase and the code is written in a later turn, so
    a per-turn scan would false-block legitimate plan execution. A real tool
    call cannot be fabricated by writing marker text — that is the proof.
    """
    if not transcript_path:
        return False
    try:
        for call in iter_tool_calls(transcript_path):
            name = call.get("name") or ""
            if name in WEB_TOOL_NAMES_EXACT:
                return True
            low = name.lower()
            if any(sub in low for sub in WEB_TOOL_SUBSTRINGS):
                return True
    except Exception:
        return False
    return False
