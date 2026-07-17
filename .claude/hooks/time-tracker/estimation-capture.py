#!/usr/bin/env python3
"""Time-tracker hook: capture Takumi's time-estimation phrases.

Trigger: PreToolUse on every tool. Reads the recent assistant text from the
transcript and detects time-estimation patterns like:

  "ca prendra environ 10 minutes"
  "this should take about 2 hours"
  "estime a 30min"
  "prevoir 45 secondes"

When such a phrase is detected and has not been seen this session, append a
record to `time-tracker/estimations.jsonl`. NEVER blocks. NEVER warns. Pure
observability — the comparator-tool reads the log later.

The motivation (per feedback memory `feedback_time-estimation.md`):
AI estimates are reliably MUCH HIGHER than real time. Collecting raw pairs
lets us derive a conversion coefficient.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from common import pass_through, read_hook_input  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402
from _log import append_jsonl, hash_snippet, now_iso, to_minutes  # noqa: E402
from session_state import read_state, write_state  # noqa: E402

STATE_NAME = "time-estimation-seen"

# Trigger phrases (case-insensitive). We require one of these AT MOST 80 chars
# before a numeric quantity to count as an estimation (avoid false positives
# like "the test took 5 minutes ago" — past tense is not an estimation).
_TRIGGERS = [
    r"ca prendra",
    r"ca va prendre",
    r"prendra environ",
    r"je prevois",
    r"prevoir",
    r"estime[er]?\s+a",
    r"je dirais",
    r"environ",
    r"approximativement",
    r"this will take",
    r"this should take",
    r"should take",
    r"estimate(?:d)?\s+(?:at|around)?",
    r"about\s+(?:around\s+)?",
    r"i'd say",
    r"roughly",
]
_TRIGGER_RE = re.compile(
    r"(?:" + r"|".join(_TRIGGERS) + r")",
    re.IGNORECASE,
)

# Numeric + unit. Accepts: 5min, 5 minutes, 1h, 1.5h, 30 secondes, 2 hours, 1 jour.
_QTY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(secondes?|seconds?|sec\b|s\b|minutes?|minute|mins?\b|min\b|"
    r"heures?|hours?|hrs?\b|hr\b|h\b|jours?|days?|day\b|d\b)",
    re.IGNORECASE,
)


def _scan(text: str) -> list[tuple[float, str, str]]:
    """Return list of (minutes, raw_match, snippet_context). Empty if no trigger."""
    matches: list[tuple[float, str, str]] = []
    for trig in _TRIGGER_RE.finditer(text):
        # Look at up to 80 chars AFTER the trigger for a quantity.
        window = text[trig.start(): trig.end() + 80]
        for q in _QTY_RE.finditer(window):
            raw_value = q.group(1).replace(",", ".")
            try:
                value = float(raw_value)
            except ValueError:
                continue
            minutes = to_minutes(value, q.group(2))
            if minutes <= 0 or minutes > 60 * 24 * 7:  # cap at 1 week
                continue
            snippet = window[: q.end()].strip()
            matches.append((minutes, q.group(0), snippet[:200]))
    return matches


def main() -> None:
    _, data = read_hook_input()
    transcript_path = data.get("transcript_path") or ""
    sid = data.get("session_id") or "no-session"

    if not transcript_path:
        pass_through()

    try:
        chunks = list(iter_assistant_text(transcript_path, limit=4))
    except Exception:
        pass_through()
    if not chunks:
        pass_through()

    # Only scan the MOST recent assistant turn — older turns were processed
    # at their own time. This keeps the hook cheap and dedup small.
    # iter_assistant_text yields latest-first, so [0] = most recent.
    text = chunks[0] if chunks else ""
    if not text:
        pass_through()

    found = _scan(text)
    if not found:
        pass_through()

    # Dedup via session-state seen set
    state = read_state(STATE_NAME, session_id=sid) or {}
    seen: set[str] = set(state.get("seen", []))
    new_entries = 0
    for minutes, raw, snippet in found:
        h = hash_snippet(snippet + f"|{minutes}")
        if h in seen:
            continue
        seen.add(h)
        append_jsonl("estimations.jsonl", {
            "ts": now_iso(),
            "session_id": sid,
            "hash": h,
            "minutes": round(minutes, 2),
            "raw": raw,
            "snippet": snippet,
        })
        new_entries += 1

    if new_entries:
        state["seen"] = sorted(seen)
        try:
            write_state(STATE_NAME, state, session_id=sid)
        except OSError:
            pass

    pass_through()


if __name__ == "__main__":
    main()
