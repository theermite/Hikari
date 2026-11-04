#!/usr/bin/env python3
"""The run journal: strict JSON lines written by a tool, read CLOSED. Nothing is guessed, nothing is dropped.

Born 2026-11-04 with run_resume.py. Three reviews failed on the same family: reading free Markdown (tables, headings)
is open-ended by nature ("reading less than what is written, then treating the rest as absent"), and every pattern
added left the next form uncovered. The method changed: the journal is one JSON object per line, appended by this
module, and a line that is not exactly one of the three event shapes below is REPORTED (`Journal.orphans`, line
numbers), never skipped.

Events (extra keys allowed, required keys and their types are strict):
  {"type": "brique", "brique": "B07", "livre": true, "commande": "...", "sortie": "...", "sha": "<hex>",
   "cout_usd": 1.25}                      # cout_usd: JSON number >= 0, or null when unknown (which stops a resume)
  {"type": "arret", "raison": "limite de jetons"}
  {"type": "point_valide", "id": "C1"}   # written only on Jay's word

Writer: python .claude/hooks/lib/run_journal.py brique|arret|point-valide <file> ... (see --help). Exit 2 on a refusal.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path


class JournalError(ValueError):
    """An event the journal refuses to hold."""


@dataclass(frozen=True)
class Journal:
    front: dict                                  # {"raison": last stop reason, "points_valides": [ids]}
    rows: list                                   # one dict per brick attempt, in file order
    orphans: list = field(default_factory=list)  # line numbers that are not a valid event


def brick_id(value: str) -> str:
    return value.strip().upper()


def _text(value) -> bool:
    return isinstance(value, str)


def _number_or_none(value) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


_SHAPES = {
    "brique": {"brique": lambda v: _text(v) and bool(v.strip()), "livre": lambda v: isinstance(v, bool),
               "commande": _text, "sortie": _text, "sha": _text, "cout_usd": _number_or_none},
    "arret": {"raison": _text},
    "point_valide": {"id": lambda v: (_text(v) and bool(v.strip())) or (isinstance(v, int) and not isinstance(v, bool))},
}


def event_problem(event) -> str | None:
    """Why this object is not a valid event, or None."""
    if not isinstance(event, dict) or event.get("type") not in _SHAPES:
        return "not one of the known events"
    for name, ok in _SHAPES[event["type"]].items():
        if name not in event or not ok(event[name]):
            return f"field {name!r} missing or of the wrong type"
    return None


def cost_of(event: dict) -> float | None:
    """The cost as a finite number >= 0, or None (unknown: null, text, negative, NaN, infinite, boolean)."""
    value = event.get("cout_usd")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) and value >= 0 else None
    except OverflowError:  # an integer too large for a float
        return None


def _row(event: dict) -> dict:
    return {"brique": brick_id(event["brique"]), "ecrit": event["brique"].strip(), "livre": "oui" if event["livre"] else "non",
            "commande": event["commande"], "sortie": event["sortie"], "sha": event["sha"], "cout": cost_of(event),
            "_malformed": False}


def _no_duplicate_keys(pairs: list) -> dict:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key: the last one must never win silently")
    return dict(pairs)


def parse_journal(text: str) -> Journal:
    rows, orphans, stops, valid = [], [], [], []
    for number, line in enumerate(text.split("\n"), 1):  # not splitlines(): U+2028, U+0085... are not line ends here
        if not line.strip():
            continue
        try:
            event = json.loads(line, object_pairs_hook=_no_duplicate_keys)
        except ValueError:
            orphans.append(number)
            continue
        if event_problem(event):
            orphans.append(number)
        elif event["type"] == "brique":
            rows.append(_row(event))
        elif event["type"] == "arret":
            stops.append(event["raison"])
        else:
            valid.append(str(event["id"]))
    return Journal({"raison": stops[-1] if stops else "non précisé", "points_valides": valid}, rows, orphans)


def append_event(path: Path, event: dict) -> None:
    """Validate then append one event. Refuses what the reader would refuse (and a non-number cost)."""
    problem = event_problem(event)
    if problem is None and event["type"] == "brique" and event["cout_usd"] is not None and cost_of(event) is None:
        problem = "field 'cout_usd' must be a number >= 0 or null"
    if problem:
        raise JournalError(problem)
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one event to a run journal.")
    sub = parser.add_subparsers(dest="kind", required=True)
    brique = sub.add_parser("brique")
    brique.add_argument("file")
    for name in ("brique", "livre", "commande", "sortie", "sha"):
        brique.add_argument(f"--{name}", required=True)
    brique.add_argument("--cout", required=True, help="USD as a number, or 'inconnu'")
    sub.add_parser("arret").add_argument("file")
    sub.choices["arret"].add_argument("--raison", required=True)
    sub.add_parser("point-valide").add_argument("file")
    sub.choices["point-valide"].add_argument("--id", required=True)
    return parser.parse_args(argv)


def _event(args: argparse.Namespace) -> dict:
    if args.kind == "arret":
        return {"type": "arret", "raison": args.raison}
    if args.kind == "point-valide":
        return {"type": "point_valide", "id": args.id}
    cost = None if args.cout == "inconnu" else float(args.cout)  # float() raises ValueError on text: exit 2
    return {"type": "brique", "brique": args.brique, "livre": args.livre.lower() in ("oui", "true", "yes"),
            "commande": args.commande, "sortie": args.sortie, "sha": args.sha, "cout_usd": cost}


def main(argv: list[str] | None = None) -> int:
    args = _args(sys.argv[1:] if argv is None else argv)
    try:
        append_event(Path(args.file), _event(args))
    except (JournalError, ValueError, OSError) as exc:
        print(f"run-journal: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
