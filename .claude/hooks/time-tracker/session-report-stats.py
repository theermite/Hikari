#!/usr/bin/env python3
"""Time-tracker hook: emit a per-session stats summary on SessionEnd.

Trigger: SessionEnd only. Reads the current session's records from
`estimations.jsonl` and `sessions.jsonl`, computes a tiny summary, and:

1. Writes a markdown snippet to
   `.claude/state/time-tracker/last-session-stats.md` so the session report
   skill can pick it up.
2. Emits a one-line summary to stderr for human visibility.

NEVER blocks. NEVER warns. Pure observability.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from common import pass_through, read_hook_input  # noqa: E402
from _log import read_jsonl, time_dir  # noqa: E402

SNIPPET_NAME = "last-session-stats.md"


def _session_stats(sid: str) -> dict:
    ests = [e for e in read_jsonl("estimations.jsonl") if e.get("session_id") == sid]
    sessions = read_jsonl("sessions.jsonl")
    sess = next((s for s in reversed(sessions) if s.get("session_id") == sid), {})

    minutes = [e.get("minutes", 0.0) for e in ests]
    sum_est = round(sum(minutes), 2) if minutes else 0.0
    median_est = round(statistics.median(minutes), 2) if minutes else 0.0
    real = sess.get("duration_min")
    ratio = None
    if real and real > 0 and sum_est > 0:
        ratio = round(sum_est / real, 2)
    return {
        "session_id": sid,
        "count": len(ests),
        "sum_est_min": sum_est,
        "median_est_min": median_est,
        "real_min": real,
        "ratio": ratio,
    }


def _render(stats: dict) -> str:
    lines = [
        "## Time Tracker — Session Summary",
        "",
        f"- Estimations captured: **{stats['count']}**",
        f"- Sum estimated: **{stats['sum_est_min']} min**",
        f"- Median estimate: **{stats['median_est_min']} min**",
        f"- Real duration: **{stats['real_min']} min**" if stats["real_min"] is not None
        else "- Real duration: **n/a**",
    ]
    if stats["ratio"] is not None:
        lines.append(f"- Ratio Est/Real: **{stats['ratio']}x**")
    else:
        lines.append("- Ratio Est/Real: **n/a**")
    return "\n".join(lines) + "\n"


def main() -> None:
    _, data = read_hook_input()
    event = (data.get("hook_event_name") or "").lower()
    sid = data.get("session_id") or ""

    if event != "sessionend" or not sid:
        pass_through()

    stats = _session_stats(sid)
    if stats["count"] == 0 and stats["real_min"] is None:
        pass_through()

    snippet = _render(stats)

    try:
        (time_dir() / SNIPPET_NAME).write_text(snippet, encoding="utf-8", newline="\n")
    except OSError:
        pass

    ratio_str = f"{stats['ratio']}x" if stats["ratio"] is not None else "n/a"
    sys.stderr.write(
        f"[time-tracker] session {sid[:12]}: {stats['count']} est, "
        f"sum={stats['sum_est_min']}min, real={stats['real_min']}min, "
        f"ratio={ratio_str}\n"
    )
    pass_through()


if __name__ == "__main__":
    main()
