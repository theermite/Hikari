#!/usr/bin/env python3
"""Time-tracker hook: record real session duration.

Triggers:
- SessionStart : record `started_at` for this session
- SessionEnd   : compute duration vs the recorded start and append to
                 `sessions.jsonl`

The hook is single-binary; behavior selected via the `hook_event_name` field
in the stdin JSON (Claude Code passes this for both events). On unknown event,
pass through silently.

NEVER blocks. NEVER warns. Pure observability.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from common import pass_through, read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402
from _log import append_jsonl, now_iso, parse_iso  # noqa: E402

STATE_NAME = "time-session"


def _handle_start(sid: str) -> None:
    if not sid:
        return
    state = read_state(STATE_NAME, session_id=sid) or {}
    if state.get("started_at"):
        return  # Already recorded — SessionStart should fire once
    state["started_at"] = now_iso()
    try:
        write_state(STATE_NAME, state, session_id=sid)
    except OSError:
        pass


def _handle_end(sid: str) -> None:
    if not sid:
        return
    state = read_state(STATE_NAME, session_id=sid) or {}
    started_at = state.get("started_at")
    ended_at = now_iso()

    duration_min: float | None = None
    if started_at:
        start_dt = parse_iso(started_at)
        end_dt = parse_iso(ended_at)
        if start_dt and end_dt:
            duration_min = round((end_dt - start_dt).total_seconds() / 60.0, 2)

    append_jsonl("sessions.jsonl", {
        "session_id": sid,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_min": duration_min,
    })


def main() -> None:
    _, data = read_hook_input()
    event = (data.get("hook_event_name") or "").lower()
    sid = data.get("session_id") or ""

    if event == "sessionstart":
        _handle_start(sid)
    elif event == "sessionend":
        _handle_end(sid)
    # Unknown event → no-op
    pass_through()


if __name__ == "__main__":
    main()
