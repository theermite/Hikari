#!/usr/bin/env python3
"""Time-tracker tool: compare estimations vs reality.

This is NOT a hook — it is a standalone CLI tool invoked on demand:

    python .claude/hooks/time-tracker/comparator-tool.py [--session SID]
    python .claude/hooks/time-tracker/comparator-tool.py --json

Reads `estimations.jsonl` and `sessions.jsonl` from .claude/state/time-tracker/
and prints a markdown report covering:

- Number of estimations captured
- Median / mean estimated minutes
- Total estimated minutes per session
- Real session duration
- Ratio estimated/real per session and overall (the conversion coefficient)

The motivation: AI estimates are reliably MUCH HIGHER than real time
(`feedback_time-estimation.md`). The ratio over many sessions converges to a
usable conversion formula.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))

from _log import read_jsonl  # noqa: E402


def _group_by_session(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        sid = r.get("session_id") or "unknown"
        out.setdefault(sid, []).append(r)
    return out


def _safe_median(values: list[float]) -> float:
    return round(statistics.median(values), 2) if values else 0.0


def _safe_mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 2) if values else 0.0


def _safe_sum(values: list[float]) -> float:
    return round(sum(values), 2) if values else 0.0


def _format_report(estimations: list[dict], sessions: list[dict], only: str | None) -> str:
    est_by_sid = _group_by_session(estimations)
    ses_by_sid = {s.get("session_id"): s for s in sessions if s.get("session_id")}

    if only:
        est_by_sid = {only: est_by_sid.get(only, [])}
        ses_by_sid = {only: ses_by_sid.get(only, {})} if only in ses_by_sid else {}

    lines: list[str] = []
    lines.append("# Time Comparator — Estimations vs Reality")
    lines.append("")
    lines.append(f"- Total estimations captured: **{len(estimations)}**")
    lines.append(f"- Total sessions logged: **{len(sessions)}**")
    if estimations:
        all_minutes = [e.get("minutes", 0.0) for e in estimations]
        lines.append(f"- Overall estimate median: **{_safe_median(all_minutes)} min**")
        lines.append(f"- Overall estimate mean: **{_safe_mean(all_minutes)} min**")
    lines.append("")
    lines.append("## Per-session comparison")
    lines.append("")
    lines.append("| Session | # Est. | Sum Est. (min) | Real (min) | Ratio Est/Real |")
    lines.append("|---------|--------|----------------|------------|----------------|")

    ratios: list[float] = []
    all_sids = sorted(set(est_by_sid) | set(ses_by_sid))
    for sid in all_sids:
        ests = est_by_sid.get(sid, [])
        sess = ses_by_sid.get(sid) or {}
        sum_est = _safe_sum([e.get("minutes", 0.0) for e in ests])
        real = sess.get("duration_min")
        if real and real > 0 and sum_est > 0:
            ratio = round(sum_est / real, 2)
            ratios.append(ratio)
            ratio_str = f"{ratio}x"
        else:
            ratio_str = "n/a"
        real_str = f"{real}" if real is not None else "n/a"
        sid_short = sid[:12] + ("..." if len(sid) > 12 else "")
        lines.append(f"| {sid_short} | {len(ests)} | {sum_est} | {real_str} | {ratio_str} |")

    lines.append("")
    if ratios:
        lines.append("## Conversion coefficient")
        lines.append("")
        lines.append(f"- Median ratio (Est/Real): **{_safe_median(ratios)}x**")
        lines.append(f"- Mean ratio (Est/Real): **{_safe_mean(ratios)}x**")
        lines.append("")
        lines.append(
            "_To convert an estimate to a realistic duration: "
            f"divide it by the median ratio ({_safe_median(ratios)})._"
        )
    else:
        lines.append("_Not enough paired sessions to compute a ratio yet._")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare time estimations vs real session durations.")
    parser.add_argument("--session", help="Restrict to a single session_id.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of markdown.")
    args = parser.parse_args()

    estimations = read_jsonl("estimations.jsonl")
    sessions = read_jsonl("sessions.jsonl")

    if args.json:
        sys.stdout.write(json.dumps({
            "estimations": estimations,
            "sessions": sessions,
        }, indent=2, ensure_ascii=False) + "\n")
        return 0

    report = _format_report(estimations, sessions, only=args.session)
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
