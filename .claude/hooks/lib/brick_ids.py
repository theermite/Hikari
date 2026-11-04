"""Brick ids as they are written in a PET: recognition, equality and ranges. Shared by plan_bricks.py.

A brick id is `B09a`, `B-001`, `K-B1` (at most 3 digits: a commit hash like b3261e is not a brick). Two ids are the same
brick when they differ only by case or hyphens. A RANGE (`B40-B43`, `B008–B010`, `B02a-c`) names every brick it covers: the
bricks in the middle are invisible to any token scan, so a range is expanded here and each brick it implies must exist.
"""

from __future__ import annotations

import re

ID_TEXT = r"(?:[A-Za-z]{1,2}-)?[Bb]-?\d{1,3}[a-z]?"
ID = re.compile(rf"^{ID_TEXT}$")
ID_START = re.compile(rf"^{ID_TEXT}\b")
HEADING = re.compile(rf"^#{{2,6}}\s+[\W_]*(?:Brique\s+)?({ID_TEXT})\b")
_ANY = re.compile(rf"(?<![A-Za-z0-9_]){ID_TEXT}(?![A-Za-z0-9_])")
_RANGE = re.compile(rf"(?<![A-Za-z0-9_])({ID_TEXT})\s*[-–—]\s*({ID_TEXT})(?![A-Za-z0-9_])")
_LETTERS = re.compile(r"(?<![A-Za-z0-9_])((?:[A-Za-z]{1,2}-)?[Bb]-?\d{1,3})([a-z])[-–—]([a-z])(?![A-Za-z0-9_])")
_PARTS = re.compile(r"^((?:[A-Za-z]{1,2}-)?[Bb]-?)(\d{1,3})([a-z]?)$")
MAX_RANGE = 60


def norm(ident: str) -> str:
    """Equality key of a brick id: case and hyphens do not make two bricks."""
    return ident.strip().upper().replace("-", "")


def _numeric_range(a: str, b: str) -> list[str] | None:
    pa, pb = _PARTS.match(a), _PARTS.match(b)
    if not pa or not pb or pa[1].upper() != pb[1].upper() or pa[3] or pb[3]:
        return None
    lo, hi = int(pa[2]), int(pb[2])
    if hi < lo or hi - lo >= MAX_RANGE:
        return None
    width = len(pa[2]) if pa[2].startswith("0") else 0
    return [f"{pa[1]}{str(n).zfill(width)}" for n in range(lo, hi + 1)]


def _scan_line(line: str, problems: list) -> list[str]:
    """Ids written in one line, plus every brick implied by a range; unexpandable ranges go to `problems`."""
    found = [m.group(0) for m in _ANY.finditer(line)]
    for m in _RANGE.finditer(line):
        expanded = _numeric_range(m[1], m[2])
        if expanded is None:
            problems.append(f"plage « {m.group(0)} » non développable (familles différentes, à l'envers, avec suffixes ou de plus de {MAX_RANGE} briques) : écrire les briques une par une")
        else:
            found += expanded
    for m in _LETTERS.finditer(line):
        if m[2] > m[3]:
            problems.append(f"plage « {m.group(0)} » à l'envers : écrire les briques une par une")
        else:
            found += [f"{m[1]}{chr(c)}" for c in range(ord(m[2]), ord(m[3]) + 1)]
    return found


def stray_ids(text: str, known: set) -> tuple[dict, list]:
    """(id written anywhere, or implied by a range, that `known` does not hold: key -> (id, first line)), (range problems)."""
    stray: dict = {}
    problems: list = []
    for number, line in enumerate(text.splitlines(), 1):
        local: list = []
        for ident in _scan_line(line, local):
            if norm(ident) not in known:
                stray.setdefault(norm(ident), (ident, number))
        problems += [f"ligne {number} : {p}" for p in local]
    return stray, problems


def _family(ident: str):
    m = _PARTS.match(ident.strip())
    return (m[1].upper().replace("-", ""), m) if m else (None, None)


def numbering_gaps(ids: list) -> list[tuple[str, str, str]]:
    """Holes in the numbering of each family (`B`/`B-`, `K-B`...): (missing id, id before, id after).

    A family is checked from its lowest to its highest number; sub-bricks (`B16a`, `B16b`) cover their number, and for one
    number the letters must run from `a` without a break (B14a, B14c lacks B14b). This is what catches a brick forgotten
    from the roadmap whatever the prose says (« B11 à B15 », « B11-15 », « B11 → B15 »).
    """
    numbers: dict = {}
    letters: dict = {}
    for ident in ids:
        key, m = _family(ident)
        if m:
            numbers.setdefault(key, {})[int(m[2])] = (m[1], m[2])
            if m[3]:
                letters.setdefault((key, int(m[2])), set()).add(m[3])
    gaps = []
    for key, nums in numbers.items():
        pad = max(len(d) for _, d in nums.values()) if any(d.startswith("0") for _, d in nums.values()) else 0
        prefix = next(iter(nums.values()))[0]
        show = lambda n, suffix="": f"{prefix}{str(n).zfill(pad)}{suffix}"  # noqa: E731 - display only
        for n in range(min(nums), max(nums) + 1):
            if n not in nums:
                gaps.append((show(n), show(max(k for k in nums if k < n)), show(min(k for k in nums if k > n))))
        for (fam, n), have in letters.items():
            if fam == key:
                top = max(have)
                gaps += [(show(n, c), show(n, "a"), show(n, top)) for c in map(chr, range(ord("a"), ord(top))) if c not in have]
    return gaps
