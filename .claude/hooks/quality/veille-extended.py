#!/usr/bin/env python3
"""Veille / SKB Evidence guard EXTENDED — PreToolUse Write|Edit.

Extends guards/pre-code-veille-check.py to non-code paths that ALSO require
verified-source evidence:
  - docs/Audits/         — audits and competitive analyses
  - docs/Decisions/      — architectural decision records (ADRs)
  - docs/Research/       — research findings, evaluations

These paths are NOT covered by pre-code-veille-check.py (which only targets
source code extensions). Yet they often contain version numbers, library
recommendations, or technical claims that need the same marker discipline.

Markers (same as pre-code-veille-check.py, case-sensitive):
  [VEILLE] <techno>@<version> verifie <date> via <source>
  [SKB] consulte: <paths>
  [VEILLE-SKIP] motif: <reason>

If target file is in extended-scope path AND no marker found in recent
transcript -> BLOCK with recovery message.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import block, get_file_path, pass_through, read_hook_input  # type: ignore

# Extended scope: paths that require veille evidence beyond source code
EXTENDED_SCOPE_PARTS = (
    "/docs/audits/",
    "\\docs\\audits\\",
    "/docs/decisions/",
    "\\docs\\decisions\\",
    "/docs/research/",
    "\\docs\\research\\",
    "/docs/adr/",
    "\\docs\\adr\\",
)

MARKER_RE = re.compile(r"(^|\s)\[(VEILLE|SKB|VEILLE-SKIP)\][^\n]+", re.MULTILINE)
TRANSCRIPT_SCAN_LIMIT = 40


def in_extended_scope(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lower()
    return any(part.replace("\\", "/").lower() in norm for part in EXTENDED_SCOPE_PARTS)


def extract_text(entry) -> str:
    """Text Takumi actually SAID in this transcript entry, or "" if it is not
    his turn.

    Before 2026-09-14 this walked the WHOLE JSON tree, so a tool result
    quoting marker-shaped text (a file read whose content says "[VEILLE] ...")
    was indistinguishable from a marker Takumi actually wrote — same defect,
    found the same day, as veille_markers.py's own _entry_text. Only role ==
    "assistant" content blocks of type "text" count.
    """
    msg = (entry.get("message") or entry) if isinstance(entry, dict) else None
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        return ""
    content = msg.get("content")
    if not isinstance(content, list):
        return ""
    chunks = [b.get("text", "") for b in content
              if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
    return "\n".join(chunks)


def _speech_turns_have_a_marker(lines: list[str], limit: int) -> bool:
    """Walk `lines` backwards, spending the budget only on Takumi's own turns.

    TRANSCRIPT_SCAN_LIMIT counts SPEECH TURNS, never raw transcript lines
    (independent review, 2026-09-14): a tool result answering in between costs
    nothing against the budget, since `extract_text` returns "" for anything
    that is not role == "assistant" text. A budget spent per raw line starves
    on tool-heavy sessions -- 83% of real markers sat beyond the old 40-line
    budget once tool-result echoes stopped padding it out.
    """
    import json

    spent = 0
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # not a parseable entry: never something Takumi said
        text = extract_text(entry)
        if not text:
            continue
        spent += 1
        if MARKER_RE.search(text):
            return True
        if spent >= limit:
            break
    return False


def scan_transcript_for_marker(transcript_path: str) -> bool:
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return False
    return _speech_turns_have_a_marker(lines, TRANSCRIPT_SCAN_LIMIT)


def main() -> None:
    _, data = read_hook_input()
    file_path = get_file_path(data)
    if not in_extended_scope(file_path):
        pass_through()

    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if scan_transcript_for_marker(transcript_path):
        pass_through()

    block(
        f"BLOCKED: Veille / SKB evidence missing for extended-scope doc.\n"
        f"Target: {file_path}\n"
        "RECOVERY: Output one of the three strict markers BEFORE retrying:\n"
        "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>\n"
        "  [SKB] consulte: <chemin1>, <chemin2>\n"
        "  [VEILLE-SKIP] motif: <raison concrete>\n"
        "Audits, Decisions and Research docs contain technical claims that "
        "need the same source discipline as code. "
        "See rules/Workflows.md 'Veille/SKB Evidence Protocol'."
    )


if __name__ == "__main__":
    main()
