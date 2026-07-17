#!/usr/bin/env python3
"""Rules-vs-memory advisory — PreToolUse(Write|Edit).

Heuristic: when Takumi writes/edits with confidence-from-memory patterns
("je sais que la regle...", "d'apres ma memoire...", "if I recall correctly")
on a methodology topic, surface a WARN suggesting to re-read the rule source.

Non-blocking by design. Pattern detection on assistant text is noisy by
nature; this hook only nudges, it does not stop the work.

Detection:
  - Scan last ~10 assistant text blocks from the transcript.
  - Match memory-claim patterns AND a methodology topic keyword in the same block.
  - Throttle: warn at most once per session per matched topic.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import format_warn, pass_through, read_hook_input, warn  # noqa: E402
from session_state import mark_once  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402


MEMORY_CLAIM_PATTERNS = [
    r"\bje sais que la r[èe]gle\b",
    r"\bd'apr[èe]s ma m[ée]moire\b",
    r"\bje me souviens que\b",
    r"\bif I recall\b",
    r"\bfrom memory\b",
    r"\bI remember that the rule\b",
]
TOPIC_KEYWORDS = [
    "monozukuri", "tdg", "lego", "veille", "jidoka", "poka-yoke",
    "interpretation-protocol", "confidentiality", "dignity",
    "workflow", "quality", "honesty", "identity",
]

MEMORY_RE = re.compile("|".join(MEMORY_CLAIM_PATTERNS), re.IGNORECASE)
TOPIC_RE = re.compile("|".join(re.escape(k) for k in TOPIC_KEYWORDS), re.IGNORECASE)


def main() -> None:
    _, data = read_hook_input()
    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")

    for text in iter_assistant_text(transcript_path, limit=10):
        if not MEMORY_RE.search(text):
            continue
        topic_match = TOPIC_RE.search(text)
        if not topic_match:
            continue
        topic = topic_match.group(0).lower()
        if mark_once("rules-vs-memory", topic, session_id=session_id):
            warn(format_warn(
                f"Memory-claim sur sujet methodo detecte ({topic})",
                f"Re-lis la regle source avant d'affirmer. Files: rules/*.md ou mnk/. "
                "Memoire interne du modele = stale (date d'entrainement)",
                reference="rules/Monozukuri.md + rules/Honesty.md (preuve, jamais affirmation)",
            ))
            break  # one warning per invocation

    pass_through()


if __name__ == "__main__":
    main()
