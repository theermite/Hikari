"""frozen_copies — the frozen copies of Kata files that projects keep.

A project may freeze a copy of a Kata file as the reference its own code is
compared to: Dogu keeps Kata's shell guard and secret masker in
`test-fixtures/oracle/`, and its Elixir reader must refuse every command they
refuse. Each copy records its files' SHA-256 in a `SHA256SUMS`. When Kata
changes one of those files, the copy is behind and nothing said so (Jay,
2026-10-18): this module says it.

The copies live next to Kata (`<parent of Kata>/<directory>`), as on every
machine; a copy absent from this machine is skipped, never an error.

Run as a script for the full report: `python3 .claude/hooks/lib/frozen_copies.py
[--strict]` (exit 1 with --strict when a copy is behind).
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# `sha256sum` text (`<hash>  <path>`) and binary (`<hash> *<path>`) forms.
_SUM_LINE = re.compile(r"^([0-9a-fA-F]{64}) [ *](.+)$")


@dataclass(frozen=True)
class Copy:
    consumer: str
    directory: str  # relative to the parent of Kata
    readme: str  # where the consumer says how to refresh its copy
    files: dict[str, str] = field(default_factory=dict)  # Kata path -> path in the copy


@dataclass(frozen=True)
class Late:
    consumer: str
    source: str
    readme: str


COPIES: tuple[Copy, ...] = (
    Copy(
        consumer="Dogu",
        directory="Dogu/test-fixtures/oracle",
        readme="test-fixtures/oracle/README.md",
        files={
            ".claude/hooks/lib/common.py": "hooks/lib/common.py",
            ".claude/hooks/lib/shell_parse.py": "hooks/lib/shell_parse.py",
            ".claude/hooks/lib/secret_mask.py": "hooks/lib/secret_mask.py",
            ".claude/hooks/guards/bash-guard.py": "hooks/guards/bash-guard.py",
            ".claude/hooks/guards/git_push_guard.py": "hooks/guards/git_push_guard.py",
        },
    ),
)


def _recorded(sums: Path) -> dict[str, str]:
    """Path -> hash from a SHA256SUMS, text or binary form, BOM and CRLF tolerated."""
    recorded = {}
    for line in sums.read_text(encoding="utf-8-sig").splitlines():
        if match := _SUM_LINE.match(line.strip()):
            recorded[match.group(2).strip()] = match.group(1).lower()
    return recorded


def _on_disk(kata_root: Path) -> Callable[[str], bytes | None]:
    def read(source: str) -> bytes | None:
        path = kata_root / source
        return path.read_bytes() if path.is_file() else None

    return read


def behind(
    kata_root: Path,
    copies: tuple[Copy, ...] = COPIES,
    read: Callable[[str], bytes | None] | None = None,
) -> list[Late]:
    """Every Kata file whose frozen copy no longer matches it. `read` gives a
    Kata file's content (the hook reads the commit, the report the disk)."""
    read = read or _on_disk(kata_root)
    late = []
    for copy in copies:
        sums = kata_root.parent / copy.directory / "SHA256SUMS"
        if not sums.is_file():
            continue
        recorded = _recorded(sums)
        for source, target in copy.files.items():
            content = read(source)
            digest = hashlib.sha256(content).hexdigest() if content is not None else None
            if digest != recorded.get(target):
                late.append(Late(copy.consumer, source, copy.readme))
    return late


def message(late: list[Late]) -> str:
    lines = ["[COPIE-FIGEE] Une copie figée d'un fichier Kata est en retard :"]
    for item in late:
        lines.append(f"- {item.consumer} : {item.source} (marche à suivre : {item.consumer}/{item.readme})")
    lines.append(
        "Recopier ces fichiers dans la copie du projet, régénérer son SHA256SUMS et son "
        "KATA_COMMIT, puis relancer ses tests de comparaison. Sans cela, le projet "
        "applique encore l'ancienne version de la règle."
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    kata_root = Path(__file__).resolve().parents[3]
    late = behind(kata_root)
    print(message(late) if late else "Copies figées : toutes à jour (ou absentes de cette machine).")
    return 1 if late and "--strict" in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
