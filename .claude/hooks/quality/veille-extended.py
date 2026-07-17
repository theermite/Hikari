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


def extract_text(node) -> str:
    """Best-effort plain text extraction from a JSONL transcript entry."""
    chunks: list[str] = []

    def walk(n):
        if isinstance(n, str):
            chunks.append(n)
        elif isinstance(n, dict):
            for k, v in n.items():
                if k in ("text", "content", "message", "value"):
                    walk(v)
                elif k == "type" and v == "text":
                    pass
                else:
                    walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return "\n".join(chunks)


def scan_transcript_for_marker(transcript_path: str) -> bool:
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return False

    import json

    recent = lines[-TRANSCRIPT_SCAN_LIMIT:] if len(lines) > TRANSCRIPT_SCAN_LIMIT else lines
    for line in reversed(recent):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            if MARKER_RE.search(line):
                return True
            continue
        text = extract_text(entry)
        if MARKER_RE.search(text):
            return True
    return False


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
