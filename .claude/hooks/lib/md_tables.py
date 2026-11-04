"""Markdown tables and fences, read the way CommonMark/GFM does, for plan_bricks.py. Nothing is dropped silently.

`collect` walks the file once: it returns every table (header + rows, a row may lack its leading pipe) and every title that
names a brick; a table line that belongs to no table is reported in `problems`. Fenced code (``` or ~~~, closing fence at
least as long and without info string) and HTML comments are skipped here, never trusted: plan_bricks.py still checks every
brick id written in them (closure invariant).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from brick_ids import HEADING, ID_START

PIPE = re.compile(r"(?<!\\)\|")
_TITLE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass
class Table:
    line: int
    header: list          # raw header cells
    section: tuple = ()   # titles of the headings that enclose the table, outermost first
    rows: list = field(default_factory=list)  # (line number, cells)


def cells(line: str) -> list[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [c.replace("\\|", "|").strip() for c in PIPE.split(body)]


def is_separator(line: str) -> bool:
    return bool(PIPE.search(line)) and "-" in line and set("".join(cells(line))) <= set("-: ")


def clean_id(cell: str) -> str:
    """The id of a cell: bold, backticks and a Markdown link `[B1](#b1)` are decoration."""
    text = cell.strip().strip("*`_ ").strip()
    link = re.match(r"^\[([^\]]*)\]\([^)]*\)$", text)
    return (link.group(1) if link else text).strip("*`_ ").strip()


FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def fence_state(line: str, fence: tuple | None) -> tuple | None:
    """Fence open/close like CommonMark: same character, at least as long, closing line carries no info string."""
    m = FENCE.match(line.lstrip())
    if fence is None:
        return (m[1][0], len(m[1])) if m else None
    return None if m and m[1][0] == fence[0] and len(m[1]) >= fence[1] and not m[2].strip() else fence


def _setext(lines: list, number: int, line: str):
    """A paragraph line underlined by === or --- is a title (level 1 or 2): (marker, level, text) shaped like _TITLE."""
    nxt = lines[number] if number < len(lines) else ""
    if line.strip() and not line.lstrip().startswith(("|", "#", ">", "-", "*", "+", "`", "<!--")) and re.match(r"^\s*(=+|-{3,})\s*$", nxt):
        return (None, 1 if nxt.strip().startswith("=") else 2, line.strip())
    return None


def collect(lines: list[str], problems: list) -> tuple[list, list]:
    """One pass: tables (with their rows) and detail headings. Orphan table lines are problems."""
    walker = _Walker(lines, problems)
    details, current, fence, comment = [], None, None, False
    for number, line in enumerate(lines, 1):
        was_fenced, fence = fence is not None, fence_state(line, fence)
        if was_fenced or fence is not None:
            current = None
            continue
        found = None if comment else HEADING.match(line)
        if found:
            details.append(found.group(1))
        title = None if comment else _TITLE.match(line)
        if title is None and not comment:
            title = _setext(lines, number, line)
        if title:
            walker.enter(len(title[1]) if isinstance(title[1], str) else title[1], title[2])
            current = None
            continue
        if comment or "<!--" in line:
            comment = "-->" not in line.split("<!--")[-1] if "<!--" in line else "-->" not in line
            current = None
            continue
        current = walker.step(number, line, current)
    return walker.tables, details


class _Walker:
    """Follows the table the walk is in; a pipe line outside any table is a problem, never skipped."""

    def __init__(self, lines: list, problems: list) -> None:
        self.lines, self.problems, self.tables, self.stack = lines, problems, [], []

    def enter(self, level: int, title: str) -> None:
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, title))

    def step(self, number: int, line: str, current):
        if not PIPE.search(line):
            return None
        if is_separator(line):
            return current
        row = cells(line)
        if current is not None:
            current.rows.append((number, row))
            return current
        if is_separator(self.lines[number] if number < len(self.lines) else ""):
            current = Table(number, row, tuple(t for _, t in self.stack))
            self.tables.append(current)
            return current
        if line.lstrip().startswith("|") or ID_START.match(clean_id(row[0])):
            self.problems.append(f"ligne {number} : ligne de tableau hors de tout tableau reconnu (« {line.strip()[:40]} »)")
        return None
