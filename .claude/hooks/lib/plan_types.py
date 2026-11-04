"""Data shared by plan_bricks.py and plan_settle.py: a brick, the roadmap read from a PET, what the caller decided."""

from __future__ import annotations

from dataclasses import dataclass, field

from md_tables import Table  # noqa: F401 - re-exported with the types below


@dataclass(frozen=True)
class Brick:
    id: str
    state: str
    line: int


@dataclass(frozen=True)
class Options:
    """What the caller decides on purpose; every use is announced in the output."""
    include: tuple = ()   # bricks written in the PET but missing from the roadmap, added as « à faire »
    ignore: tuple = ()    # first header cells of tables that are not the roadmap
    known: tuple = ()     # ids written in the PET that are not bricks
    trou: tuple = ()      # holes in the numbering that are on purpose
    libre: bool = False   # numbering is free: no hole check
    section: str = ""     # title of the section that holds the roadmap (default: any title with « roadmap » or « feuille de route »)


@dataclass
class Roadmap:
    bricks: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
