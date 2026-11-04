"""The explicit decisions of the caller on a roadmap read by plan_bricks.py, each announced in the output:
--inclure (bricks written in the PET but absent from the roadmap), --connu (ids that are not bricks), --trou and
--numerotation-libre (numbering holes), plus the numbering check itself."""

from __future__ import annotations

import difflib

from brick_ids import norm as _norm, numbering_gaps as _gaps
from plan_types import Brick, Options, Roadmap


def _include_on_purpose(roadmap: Roadmap, absent: list, include: list) -> list:
    """Bricks the caller decides to add although the roadmap omits them: only cited/detailed ones, visibly."""
    wanted = {_norm(i): i.strip() for i in include}
    names = {_norm(a) for a in absent}
    roadmap.problems += [f"--inclure {orig} : n'est pas une brique écrite dans le PET et absente de la feuille de route" for key, orig in wanted.items() if key not in names]
    known = [b.id for b in roadmap.bricks]
    for ident in absent:
        if _norm(ident) in wanted:
            roadmap.bricks.append(Brick(ident, "à faire", 0))
            roadmap.warnings.append(f"{ident} ajoutée à la main (--inclure) : son état n'est pas lu dans le plan, supposé à faire")
            close = difflib.get_close_matches(_norm(ident), [_norm(k) for k in known], n=1, cutoff=0.8)
            if close and not _is_sub_brick(_norm(ident), close[0]):
                roadmap.warnings.append(f"{ident} est proche de {next(k for k in known if _norm(k) == close[0])} : faute de frappe ?")
    return [a for a in absent if _norm(a) not in wanted]


def _is_sub_brick(ident: str, parent: str) -> bool:
    """B15a under B15: one letter more than a known brick is a split, not a typo."""
    return len(ident) == len(parent) + 1 and ident.startswith(parent) and ident[-1].isalpha()


def check_numbering(roadmap: Roadmap, options: Options) -> None:
    """A hole in the numbering is a brick forgotten from the roadmap, whatever way the prose names the range."""
    if options.libre:
        roadmap.warnings.append("numérotation libre (--numerotation-libre) : les trous de numérotation ne sont pas contrôlés")
        return
    gaps = _gaps([b.id for b in roadmap.bricks])
    wanted = {_norm(t): t for t in options.trou}
    real = {_norm(g[0]) for g in gaps}
    roadmap.problems += [f"--trou {orig} : ce n'est pas un trou de la numérotation de la feuille de route" for key, orig in wanted.items() if key not in real]
    roadmap.warnings += [f"trou de numérotation {g[0]} (entre {g[1]} et {g[2]}) accepté à la demande (--trou)" for g in gaps if _norm(g[0]) in wanted]
    left = [g for g in gaps if _norm(g[0]) not in wanted]
    if left:
        shown = ", ".join(f"{g[0]} (entre {g[1]} et {g[2]})" for g in left[:20]) + (" …" if len(left) > 20 else "")
        step = " ; numérotation par pas ? --numerotation-libre" if len(left) > 5 else ""
        roadmap.problems.append(f"trou dans la numérotation de la feuille de route : {shown} ; brique oubliée ? sinon --trou{step or ' ou --numerotation-libre'}")


def acknowledge(roadmap: Roadmap, stray: dict, details: list, opts: Options) -> None:
    """Settle the ids written in the PET that the roadmap does not hold: --connu (not bricks), --inclure (bricks)."""
    in_roadmap = {_norm(b.id) for b in roadmap.bricks}
    acknowledged = {_norm(k) for k in opts.known}
    sheets = {_norm(d) for d in details}
    roadmap.problems += [f"--connu {k} : cet identifiant n'apparaît pas dans le PET" for k in opts.known if _norm(k) not in stray and _norm(k) not in in_roadmap]
    roadmap.problems += [f"--connu {k} : {k} a une fiche détaillée dans le PET, c'est une brique : --inclure" for k in opts.known if _norm(k) in sheets]
    roadmap.warnings += [f"{ident} reconnu comme n'étant pas une brique (--connu), vu ligne {line}" for key, (ident, line) in stray.items() if key in acknowledged]
    left = {k: v for k, v in stray.items() if k not in acknowledged}
    resolved = _include_on_purpose(roadmap, [ident for ident, _ in left.values()], list(opts.include))
    if resolved:
        where = {_norm(i): n for i, n in left.values()}
        roadmap.problems.append("briques présentes dans le PET mais absentes de la feuille de route : " + ", ".join(f"{i} (ligne {where[_norm(i)]})" for i in resolved))
    missing = [b.id for b in roadmap.bricks if _norm(b.id) not in sheets and b.line]
    if missing:
        roadmap.warnings.append("sans fiche détaillée (titre « ### Bxx — … ») : " + ", ".join(missing))
