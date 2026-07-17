#!/usr/bin/env python3
"""Time awareness — UserPromptSubmit hook.

Injects current Europe/Madrid local time into Takumi's context at each
user prompt, so Takumi knows the date AND the local hour (not just
training data date or UTC).

Output format on stdout (becomes additional context for the model):
    [TIME] YYYY-MM-DD HH:MM Europe/Madrid CEST   (or CET in winter)

Non-blocking: any error -> exit 0 silent (do not break the prompt).
Madrid DST: CEST (UTC+2) from last Sunday March to last Sunday October,
otherwise CET (UTC+1). Uses zoneinfo when tzdata available, manual
fallback otherwise (Windows often lacks system tzdata).
"""

from __future__ import annotations

import datetime as _dt
import sys


def _last_sunday(year: int, month: int) -> _dt.date:
    """Return the date of the last Sunday of (year, month)."""
    if month == 12:
        first_next = _dt.date(year + 1, 1, 1)
    else:
        first_next = _dt.date(year, month + 1, 1)
    last_day = first_next - _dt.timedelta(days=1)
    # weekday: Monday=0 .. Sunday=6
    delta = (last_day.weekday() - 6) % 7
    return last_day - _dt.timedelta(days=delta)


def _madrid_now_manual() -> tuple[_dt.datetime, str]:
    """Compute Madrid local time without tzdata.

    DST rules (EU): CEST starts last Sunday of March 01:00 UTC,
    ends last Sunday of October 01:00 UTC.
    """
    utc_now = _dt.datetime.utcnow()
    year = utc_now.year
    dst_start = _dt.datetime.combine(_last_sunday(year, 3), _dt.time(1, 0))
    dst_end = _dt.datetime.combine(_last_sunday(year, 10), _dt.time(1, 0))
    if dst_start <= utc_now < dst_end:
        offset_hours = 2
        label = "CEST"
    else:
        offset_hours = 1
        label = "CET"
    local = utc_now + _dt.timedelta(hours=offset_hours)
    return local, label


def _madrid_now() -> tuple[_dt.datetime, str]:
    """Prefer zoneinfo (accurate), fall back to manual EU DST rules."""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+

        tz = ZoneInfo("Europe/Madrid")
        local = _dt.datetime.now(tz)
        label = local.strftime("%Z") or "CET"
        # Some zoneinfo backends return "Europe" or empty; normalize
        if label not in ("CET", "CEST"):
            # Derive from UTC offset
            offset = local.utcoffset()
            label = "CEST" if offset and offset.total_seconds() == 7200 else "CET"
        return local, label
    except Exception:
        return _madrid_now_manual()


def main() -> None:
    try:
        # Drain stdin (Claude Code passes a JSON payload, ignored here)
        try:
            sys.stdin.read()
        except Exception:
            pass

        local, label = _madrid_now()
        stamp = local.strftime("%Y-%m-%d %H:%M")
        sys.stdout.write(f"[TIME] {stamp} Europe/Madrid {label}\n")
        sys.stdout.flush()
        sys.exit(0)
    except Exception:
        # Never break the user's prompt
        sys.exit(0)


if __name__ == "__main__":
    main()
