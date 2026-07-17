#!/usr/bin/env python3
"""hook-blocks-report.py — A2-v2: cumulative guardrail-fatigue report.

Reads the per-session journal written by .claude/hooks/lifecycle/
hook-blocks-stats.py (A2):
    {"session_id", "ts", "blocks": {sig: count}, "warns": {sig: count}}
and aggregates a cumulative leaderboard across ALL recorded sessions.

What it answers
---------------
- Which guardrail signature fires most overall (total blocks + warns)?
- In how many distinct sessions does it appear?
- FRICTION PROXY: in how many sessions did it fire 2+ times? A guardrail that
  re-fires within the same session is the strongest journal-only signal of
  friction / likely false positive — the kind worth reclassifying WARN or fixing
  before the friction pushes someone to bypass it.

Honest limit
------------
This is a frequency + repetition view, NOT a true false-positive measure. A real
"blocked then successfully retried" correlation needs transcript-level pairing
the journal does not store (would require enriching A2's capture). Treat
repeat_sessions as a proxy, not proof.

Usage:
  python .claude/hooks/lifecycle/hook-blocks-report.py                 # default journal
  python .claude/hooks/lifecycle/hook-blocks-report.py --journal PATH  # explicit journal
  python .claude/hooks/lifecycle/hook-blocks-report.py --top 15        # limit leaderboard rows
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from common import find_repo_root  # noqa: E402

# Resolve the journal from the repo root, not from this script's position:
# the file lives beside hook-blocks-stats.py (which writes the same journal),
# so both agree on <repo>/.claude/state/hook-blocks.jsonl wherever they sit.
DEFAULT_JOURNAL = find_repo_root(HERE) / ".claude" / "state" / "hook-blocks.jsonl"


def load_entries(path: Path) -> list[dict]:
    """Parse the JSONL journal, skipping blank/malformed lines. Empty if absent."""
    path = Path(path)
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _new_rec() -> dict:
    return {"blocks": 0, "warns": 0, "sessions": 0, "repeat_sessions": 0, "overcome": 0}


def _fold_entry(agg: dict[str, dict], entry: dict) -> None:
    """Merge one session entry into the running aggregate."""
    blocks = entry.get("blocks") if isinstance(entry.get("blocks"), dict) else {}
    warns = entry.get("warns") if isinstance(entry.get("warns"), dict) else {}
    overcome = entry.get("overcome") if isinstance(entry.get("overcome"), dict) else {}

    per_session: dict[str, int] = {}  # blocks + warns combined, this session
    for sig, n in blocks.items():
        agg.setdefault(sig, _new_rec())["blocks"] += n
        per_session[sig] = per_session.get(sig, 0) + n
    for sig, n in warns.items():
        agg.setdefault(sig, _new_rec())["warns"] += n
        per_session[sig] = per_session.get(sig, 0) + n
    for sig, n in overcome.items():
        agg.setdefault(sig, _new_rec())["overcome"] += n

    for sig, count in per_session.items():
        agg[sig]["sessions"] += 1
        if count >= 2:
            agg[sig]["repeat_sessions"] += 1


def aggregate(entries: list[dict]) -> list[dict]:
    """Cumulative per-signature stats, sorted by total occurrences desc.

    Each row: {signature, blocks, warns, total, sessions, repeat_sessions}.
    - sessions        : distinct sessions where the signature appeared
    - repeat_sessions : sessions where it fired 2+ times (friction proxy)
    """
    agg: dict[str, dict] = {}
    for entry in entries:
        _fold_entry(agg, entry)
    rows = [
        {"signature": sig, "total": rec["blocks"] + rec["warns"], **rec}
        for sig, rec in agg.items()
    ]
    rows.sort(key=lambda r: (r["total"], r["repeat_sessions"]), reverse=True)
    return rows


def _print_leaderboard(rows: list[dict], top: int) -> None:
    shown = rows[:top] if top else rows
    print(f"  {'TOTAL':>5}  {'BLK':>4}  {'WRN':>4}  {'SESS':>4}  {'RPT':>4}  SIGNATURE")
    for r in shown:
        print(
            f"  {r['total']:>5}  {r['blocks']:>4}  {r['warns']:>4}  "
            f"{r['sessions']:>4}  {r['repeat_sessions']:>4}  {r['signature']}"
        )


def _print_friction(rows: list[dict], top: int) -> None:
    friction = [r for r in rows if r["repeat_sessions"] > 0]
    if not friction:
        return
    print("\n  Friction proxy — signatures that fired 2+ times in a single session:")
    for r in sorted(friction, key=lambda r: r["repeat_sessions"], reverse=True)[:top or len(friction)]:
        print(f"    {r['repeat_sessions']}x sessions  {r['signature']}")
    print("\n  RPT = repeat sessions (proxy for friction / likely false positive).")
    print("  A chronically repeating guardrail is a candidate to reclassify WARN or fix.")
    print("  Not a true false-positive measure (see module docstring).")


def _print_overcome(rows: list[dict], top: int) -> None:
    overcome = [r for r in rows if r.get("overcome", 0) > 0]
    if not overcome:
        return
    print("\n  ** Parasite candidates — blocks OVERCOME by a same-target retry **")
    print("  (the strongest signal a block was a false positive or forced throwaway work)")
    for r in sorted(overcome, key=lambda r: r["overcome"], reverse=True)[:top or len(overcome)]:
        print(f"    {r['overcome']}x overcome  {r['signature']}")
    print("  -> review these first: reclassify WARN, narrow the trigger, or fix.")


def render(rows: list[dict], n_sessions: int, top: int) -> None:
    print("=== Guardrail-fatigue cumulative report (A2-v2) ===")
    print(f"sessions recorded: {n_sessions}")
    if not rows:
        print("\n  (journal empty — nothing recorded yet; A2 writes at SessionEnd)")
        return
    total_blocks = sum(r["blocks"] for r in rows)
    total_warns = sum(r["warns"] for r in rows)
    total_overcome = sum(r.get("overcome", 0) for r in rows)
    print(f"total: {total_blocks} block(s), {total_warns} warn(s), "
          f"{total_overcome} overcome, {len(rows)} signature(s)\n")
    _print_leaderboard(rows, top)
    _print_overcome(rows, top)
    _print_friction(rows, top)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal", type=Path, default=DEFAULT_JOURNAL,
        help=f"Path to hook-blocks.jsonl (default: {DEFAULT_JOURNAL}).",
    )
    parser.add_argument(
        "--top", type=int, default=0,
        help="Limit leaderboard to the top N signatures (0 = all).",
    )
    args = parser.parse_args()

    entries = load_entries(args.journal)
    rows = aggregate(entries)
    render(rows, n_sessions=len(entries), top=args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
