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
import re

from transcript_reader import assistant_text_blocks, iter_assistant_text, iter_tool_calls
from veille_config import (
    MARKER_RE,
    RECOVERY_LINE_HINTS,
    TRANSCRIPT_SCAN_LIMIT,
    WEB_TOOL_NAMES_EXACT,
    WEB_TOOL_SUBSTRINGS,
)

# The most recent independent-review verdict spoken in chat (shared with
# quality/post-review-cause-check.py's own _VERDICT -- same marker, read here
# for a second, unrelated guard: 2026-09-10, the veille-skip motif below).
_REVIEW_VERDICT = re.compile(r"\[REVIEW\][^\n]*?verdict\s*:\s*(PASS|FAIL)", re.IGNORECASE)
_CODE_BLOCK = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)
# Same marker, same span rule as post-review-cause-check.py's own _FAMILY: the
# slug ends at a comma or a line break, read from the marker's own line only.
_REVIEW_FAMILY = re.compile(r"famille[^\S\n]*:[^\S\n]*([^,\n]+)", re.IGNORECASE)


def _entry_text(raw: str) -> str:
    """What Takumi actually SAID on this transcript line, recovery lines removed.

    Before 2026-09-14 this walked the WHOLE JSON tree, so a tool result
    quoting marker-shaped text -- this very module's own docstring, a recovery
    message, any file read whose content says "[VEILLE] ..." -- was
    indistinguishable from a marker Takumi actually wrote. Caught live: Read
    on this file made the guard refuse a genuine retry, twice, on a phrase
    quoted in a recovery message elsewhere in this codebase. Text extraction
    itself lives in transcript_reader.assistant_text_blocks (shared with
    iter_assistant_text -- one reader, not two, Honesty.md's first question).
    """
    try:
        entry = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ""
    text = "\n".join(assistant_text_blocks(entry))
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


def _scan_speech_turns(lines: list[str], limit: int) -> tuple[str, str, str] | None:
    """Walk `lines` backwards, spending the budget only on Takumi's own turns.

    A tool result or a `tool_use` input costs nothing: it is not something
    Takumi said (see _entry_text). Real cost measured by independent review
    (2026-09-14): median 274 RAW lines between a genuine marker and the write
    it covers -- a budget spent per raw line starved on tool-heavy sessions.
    """
    spent = 0
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        text = _entry_text(raw)
        if not text:
            continue
        spent += 1
        matches = _concrete_markers(text)
        if matches:
            line = matches[-1].group(0).strip()
            return matches[-1].group(1), line, marker_digest(line)
        if spent >= limit:
            break
    return None


def latest_marker(transcript_path: str) -> tuple[str, str, str] | None:
    """Return (marker_type, marker_line, hash) of the most recent marker, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    return _scan_speech_turns(lines, TRANSCRIPT_SCAN_LIMIT)


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


def latest_review_verdict(transcript_path: str, limit: int = 40) -> str | None:
    """PASS, FAIL, or None -- the most recent independent-review verdict spoken
    in chat. A verdict shown inside a code block (a gabarit, an example) is not
    a verdict that happened (same exclusion as post-review-cause-check.py).

    Used by the veille-skip guard (2026-09-10): a cause claimed "known" while
    its own review is still failing was not actually known.
    """
    if not transcript_path:
        return None
    try:
        for text in iter_assistant_text(transcript_path, limit=limit):
            spoken = _CODE_BLOCK.sub(" ", text or "")
            match = _REVIEW_VERDICT.search(spoken)
            if match:
                return match.group(1).upper()
    except Exception:
        return None
    return None


def latest_review_family(transcript_path: str, limit: int = 40) -> str | None:
    """The family slug of the most recent FAIL verdict, or None (no FAIL, or
    unnamed). Used by the 'sans-rapport' motif check (2026-09-11, independent
    review): a motif claiming no relation to the failing family is only
    honest if the file being written shares no distinctive word with it.
    """
    if not transcript_path:
        return None
    try:
        for text in iter_assistant_text(transcript_path, limit=limit):
            spoken = _CODE_BLOCK.sub(" ", text or "")
            verdict = _REVIEW_VERDICT.search(spoken)
            if not verdict:
                continue
            if verdict.group(1).upper() != "FAIL":
                return None
            line_end = spoken.find("\n", verdict.end())
            tail = spoken[verdict.end():line_end if line_end != -1 else None]
            family = _REVIEW_FAMILY.search(tail)
            return family.group(1).strip() if family else None
    except Exception:
        return None
    return None
