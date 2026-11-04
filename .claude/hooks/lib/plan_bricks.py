#!/usr/bin/env python3
"""The closed list of bricks of a contract, COMPUTED from the roadmap of the PET, with every gap reported.

Born 2026-11-04 (dry run on Dogu's real PET): the `briques` list of a mode-projet contract was copied by hand, and five
forgotten bricks were seen by nobody. Closed reading (a PET is free Markdown; open readers failed review three times):
tables are CLASSIFIED BY CONTENT, never by the name of a column, and whatever cannot be classified is a PROBLEM.

  * a table with a Statut/Status column AND a column of brick ids (found by content: `B09a`, `B-001`, `K-B1`) = roadmap;
  * a Statut/Status table without a column of brick ids = PROBLEM if its header speaks of bricks (--ignorer-tableau to
    name it away), else a named warning (the PET template carries such tables: functions, tests, tools);
  * CLOSURE INVARIANT, independent of the Markdown structure: every brick id written ANYWHERE in the file (a quote, a
    code block, a comment, prose, a cell, a title) must exist in the roadmap, else PROBLEM with its line number. An id that
    is not a brick (a model name...) is acknowledged with --connu. A roadmap hidden in a quote, in a misread code fence or
    behind --ignorer-tableau therefore cannot lose a brick silently;
  * a pipe line outside any table that starts with a brick id, or a line that starts with `|` and belongs to no table = PROBLEM.

  * NUMBERING: a hole in the numbers of the roadmap (B13 then B15) is a PROBLEM, whatever way the prose writes a range
    (« B11 à B15 », « B11-15 », « B11 → B15 ») ; sub-bricks cover their number (B16a, B16b cover B16) ; each family
    (`B`, `B-`, `K-B`) apart ; `--trou B14` accepts a hole on purpose, `--numerotation-libre` switches the check off, loudly.

With any PROBLEM no list is produced (exit 1). Order = order of the file (the tool does not guess dependencies). Status =
the state emoji of the cell: 🟢 fait · ⬜ à faire · 🟡 en cours · 🔵 en cours (tests écrits) · 🔴 bloqué · ⚫ ignoré;
two DIFFERENT states in one cell = PROBLEM (« 🟢 → 🟡 », « 🔴 bloqué (B0 🟢) »). Remaining = not fait, not ignoré. `--inclure B38,B39` adds on purpose
bricks that are written in the PET but missing from the roadmap (state assumed « à faire », loud warning).

Usage:
    python .claude/hooks/lib/plan_bricks.py docs/PET.md [--tout] [--inclure IDS] [--connu IDS] [--trou IDS] [--section TITRE] [--ignorer-tableau ENTETE]
    python .claude/hooks/lib/plan_bricks.py docs/PET.md --check docs/Contrat-Autonomie.md   # gaps between PET and contract

Exit codes: 0 clean · 1 problems in the PET, or gaps with the contract · 2 unreadable input.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract_lint as cl  # noqa: E402
from brick_ids import ID as _ID, norm as _norm, stray_ids as _stray  # noqa: E402
from md_tables import clean_id as _clean_id, collect as _collect  # noqa: E402
from plan_settle import acknowledge as _acknowledge, check_numbering as _check_numbering  # noqa: E402
from plan_types import Brick, Options, Roadmap, Table  # noqa: E402,F401

_STATES = {"🟢": "fait", "⬜": "à faire", "🟡": "en cours", "🔵": "en cours", "🔴": "bloqué", "⚫": "ignoré"}
_FINISHED = {"fait", "ignoré"}


def _key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name.replace("*", "").replace("`", "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "_", plain.strip().lower())


def _states_in(cell: str) -> list[str]:
    """The states whose glyph appears in the cell, in the order of the text."""
    found = sorted((cell.index(g), s) for g, s in _STATES.items() if g in cell)
    return [s for _, s in found]


def _id_column(table: Table, header: list) -> tuple[int | None, bool]:
    """(column of brick ids, ambiguous). Found by content: among the columns that hold ids, one whose header speaks of ids or
    bricks wins, else the one holding the most ids; a tie is ambiguous (a prerequisites column is not the bricks)."""
    width = max((len(c) for _, c in table.rows), default=0)
    counts = [sum(1 for _, c in table.rows if i < len(c) and _ID.match(_clean_id(c[i]))) for i in range(width)]
    holding = [i for i, n in enumerate(counts) if n]
    if not holding:
        return None, False
    named = [i for i in holding if i < len(header) and (header[i] == "id" or "brique" in header[i] or "brick" in header[i])]
    pool = named or holding
    best = [i for i in pool if counts[i] == max(counts[j] for j in pool)]
    return (best[0], False) if len(best) == 1 else (None, True)


class _Reader:
    """Reads the roadmap tables once, keeping the duplicate check and the problems in one place."""

    def __init__(self, roadmap: Roadmap) -> None:
        self.roadmap, self.seen = roadmap, {}

    def read(self, table: Table, id_col: int, status_col: int) -> None:
        for number, cells in table.rows:
            ident = _clean_id(cells[id_col]) if id_col < len(cells) else ""
            if status_col >= len(cells) or not _ID.match(ident):
                self.roadmap.problems.append(f"ligne {number} : ligne de la feuille de route sans identifiant de brique reconnu (« {ident or '?'} ») ou trop courte")
                continue
            self._add(ident, number, cells[status_col])

    def _add(self, ident: str, number: int, cell: str) -> None:
        states = _states_in(cell)
        if not states:
            self.roadmap.problems.append(f"ligne {number} : {ident} a un statut non reconnu (« {cell[:30]} »)")
        elif len(set(states)) > 1:
            self.roadmap.problems.append(f"ligne {number} : {ident} a plusieurs statuts dans la même cellule (« {cell[:40]} »)")
        elif _norm(ident) in self.seen:
            self.roadmap.problems.append(f"{ident} apparaît deux fois (lignes {self.seen[_norm(ident)]} et {number})")
        else:
            self.seen[_norm(ident)] = number
            self.roadmap.bricks.append(Brick(ident, states[0], number))


def _status_without_ids(roadmap: Roadmap, table: Table, header: list) -> None:
    """A Statut table with no brick ids: a PROBLEM when its header speaks of bricks (ids in an unknown format),
    otherwise a named warning (the PET template itself carries such tables: functions, tests, tools)."""
    shown = " | ".join(table.header)[:60]
    if any(h == "id" or "brique" in h or "brick" in h for h in header):
        roadmap.problems.append(f"ligne {table.line} : tableau avec une colonne Statut mais sans colonne d'identifiants de brique reconnue (« {shown} ») ; si ce n'est pas une feuille de route : --ignorer-tableau « {table.header[0]} »")
    else:
        roadmap.warnings.append(f"ligne {table.line} : tableau avec une colonne Statut ignoré, il ne contient aucun identifiant de brique (« {shown} »)")


def _classify(tables: list, roadmap: Roadmap, opts: Options) -> list:
    """Reads the tables of the roadmap SECTION; returns them. A table with a Statut column AND brick ids outside that section
    is never dropped silently: it is a problem until the caller reads it (--section) or sets it aside (--ignorer-tableau)."""
    pattern = re.compile(re.escape(opts.section) if opts.section else r"roadmap|feuille de route", re.IGNORECASE)
    ignore = {_key(i) for i in opts.ignore}
    if opts.section:
        roadmap.warnings.append(f"section « {opts.section} » désignée à la demande (--section)")
    reader, anchored = _Reader(roadmap), []
    for table in tables:
        if (_key(table.header[0]) if table.header else "") in ignore:
            roadmap.warnings.append(f"tableau « {table.header[0]} » (ligne {table.line}) ignoré à la demande (--ignorer-tableau)")
            continue
        header = ["statut" if _key(h) == "status" else _key(h) for h in table.header]
        id_col, ambiguous = _id_column(table, header)
        if not any(pattern.search(title) for title in table.section):
            _outside_section(roadmap, table, header, id_col)
            continue
        anchored.append(table)
        if ambiguous:
            roadmap.problems.append(f"ligne {table.line} : plusieurs colonnes d'identifiants de brique indiscernables (« {' | '.join(table.header)[:60]} ») : nommer la bonne colonne « ID » ou « Brique »")
        elif header.count("statut") > 1:
            roadmap.problems.append(f"ligne {table.line} : plusieurs colonnes Statut dans le même tableau (« {' | '.join(table.header)[:60]} ») : une seule est lue")
        elif "statut" in header and id_col is None:
            _status_without_ids(roadmap, table, header)
        elif "statut" in header:
            reader.read(table, id_col, header.index("statut"))
    return anchored


def _outside_section(roadmap: Roadmap, table: Table, header: list, id_col) -> None:
    if "statut" in header and id_col is not None:
        where = table.section[-1] if table.section else "-"
        roadmap.problems.append(f"ligne {table.line} : tableau « {' | '.join(table.header)[:50]} » avec un Statut et des identifiants de brique HORS de la section de la feuille de route (section « {where} ») : feuille de route probable ? --section TITRE pour désigner la bonne section, ou --ignorer-tableau « {table.header[0]} » si ce n'est pas la feuille de route")


def read_roadmap(text: str, options: Options | None = None, **kw) -> Roadmap:
    opts = options or Options(**{k: (tuple(v) if isinstance(v, (list, tuple)) else v) for k, v in kw.items()})
    roadmap = Roadmap()
    tables, details = _collect(text.splitlines(), roadmap.problems)
    anchored = _classify(tables, roadmap, opts)
    if not roadmap.bricks and not roadmap.problems:
        seen = "; ".join(f"« {' | '.join(t.header)[:50]} » (ligne {t.line}, section « {t.section[-1] if t.section else '-'} »)" for t in tables[:6]) or "aucun"
        roadmap.problems.append(f"aucune feuille de route trouvée : il faut un tableau avec une colonne Statut et une colonne d'identifiants de brique DANS une section « Roadmap » (ou --section TITRE pour la désigner) ; tableaux vus : {seen}")
    stray, range_problems = _stray(text, {_norm(b.id) for b in roadmap.bricks})
    roadmap.problems += range_problems
    _acknowledge(roadmap, stray, details, opts)
    _check_numbering(roadmap, opts)
    return roadmap


def remaining(roadmap: Roadmap, include_done: bool = False) -> list[str]:
    return [b.id for b in roadmap.bricks if include_done or b.state not in _FINISHED]


def check_contract(contract: dict, roadmap: Roadmap) -> list[str]:
    """Gaps between the contract's closed list (`briques` or `scope`) and the roadmap."""
    lint_errors = [f"contrat invalide ({v.code}) : {v.message}" for v in cl.lint(contract) if v.severity == "error"]
    if lint_errors:
        return lint_errors
    projet = contract.get("mode") == "projet"
    listed = contract.get("briques") if projet else contract.get("scope")
    listed = [str(b).strip() for b in listed] if isinstance(listed, list) else []
    by_id = {_norm(b.id): b for b in roadmap.bricks}
    gaps = []
    for ident in listed:
        brick = by_id.get(_norm(ident))
        if brick is None:
            gaps.append(f"{ident} : brique inconnue de la feuille de route")
        elif brick.state in _FINISHED:
            gaps.append(f"{ident} : brique déjà faite ({brick.state}) dans la feuille de route")
    if projet:
        have = {_norm(b) for b in listed}
        gaps += [f"{i} : brique restante qui manque dans le contrat" for i in remaining(roadmap) if _norm(i) not in have]
    return gaps


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute the closed brick list of a contract from the PET roadmap.")
    parser.add_argument("pet")
    parser.add_argument("--tout", action="store_true", help="include the bricks already done")
    parser.add_argument("--check", metavar="CONTRAT", help="compare with a contract instead of printing the list")
    parser.add_argument("--inclure", metavar="IDS", default="", help="comma-separated cited/detailed bricks the roadmap omits, added on purpose")
    parser.add_argument("--connu", metavar="IDS", default="", help="comma-separated ids written in the PET that are NOT bricks (acknowledged)")
    parser.add_argument("--trou", metavar="IDS", default="", help="comma-separated holes of the numbering that are on purpose")
    parser.add_argument("--numerotation-libre", action="store_true", help="the numbering is free: do not check for holes")
    parser.add_argument("--section", metavar="TITRE", default="", help="title of the section that holds the roadmap (default: a title with « roadmap » or « feuille de route »)")
    parser.add_argument("--ignorer-tableau", metavar="ENTETE", default="", help="comma-separated first header cells of tables that are not the roadmap")
    return parser.parse_args(argv)


def _csv(value: str) -> list[str]:
    return [i.strip() for i in value.split(",") if i.strip()]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        opts = Options(tuple(_csv(args.inclure)), tuple(_csv(args.ignorer_tableau)), tuple(_csv(args.connu)), tuple(_csv(args.trou)), args.numerotation_libre, args.section)
        roadmap = read_roadmap(Path(args.pet).read_text(encoding="utf-8-sig"), opts)
        contract = None
        if args.check:
            if cl.yaml is None:
                raise ValueError("PyYAML is missing. Install it: pip install pyyaml")
            contract = cl.load_frontmatter(Path(args.check).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"plan-bricks: {exc}", file=sys.stderr)
        return 2
    for warning in roadmap.warnings:
        print(f"ATTENTION : {warning}", file=sys.stderr)
    if roadmap.problems:
        print("\n".join(f"PROBLÈME : {p}" for p in roadmap.problems), file=sys.stderr)
        return 1
    if contract is not None:
        gaps = check_contract(contract, roadmap)
        print("\n".join(f"ÉCART : {g}" for g in gaps) or "Aucun écart entre le contrat et la feuille de route.")
        return 1 if gaps else 0
    print("briques:\n" + "\n".join(f"  - {i}" for i in remaining(roadmap, args.tout)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
