"""Which files are free-text NOTES, and the helpers to read a commit outside them (2026-10-30).

Used by guards/end-user-data-guard.py. In a repository KNOWN to be private (lib/repo_visibility.py), a free-text note
may name the people of Jay's life (his decision). Code, tests, examples, fixtures and every other kind of file stay
filtered wherever they are (Gate C). Anything this module cannot place counts as NOT a note: strict by default.
"""

from __future__ import annotations

import re
from pathlib import Path

# `.txt` is not here: it is too often a list (requirements, addresses, an export). Data folders are never notes.
FREE_TEXT_EXTS = (".md", ".mdx", ".rst")
_NOT_NOTE_DIRS = re.compile(
    r"(^|/)(tests?|__tests__|fixtures?|examples?|seeds?|mocks?|samples?|snapshots?|__snapshots__"
    r"|data|datasets?|db|exports?|dumps?|backups?)(/|$)",
    re.IGNORECASE,
)


def is_free_note(path: str) -> bool:
    norm = path.replace("\\", "/").strip()
    return norm.lower().endswith(FREE_TEXT_EXTS) and not _NOT_NOTE_DIRS.search(norm)


def repo_of(path: str) -> str | None:
    """The git working tree that holds `path` (it need not exist yet), else None."""
    here = Path(path).resolve()
    for folder in [here, *here.parents][:25]:
        if (folder / ".git").exists():
            return str(folder)
    return None


def split_diff(diff: str) -> list[tuple[str, str]]:
    """(path, added lines) per file of a `git diff -U0`, with a structural reading: a real file header is `diff --git`,
    then `---`, then `+++`. A `+++ …` line anywhere else is ADDED TEXT, so a forged header inside a code file cannot move
    the lines after it into a note. A header it cannot read, or an added line before any header, gets the path ''
    (never a note)."""
    files: list[tuple[str, list[str]]] = []
    expecting = ""
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            expecting = "---"
        elif expecting == "---" and line.startswith("--- "):
            expecting = "+++"
        elif expecting == "+++" and line.startswith("+++ "):
            files.append((_header_path(line), []))
            expecting = ""
        elif line.startswith("+"):
            _add_line(files, line)
    return [(path, "\n".join(lines)) for path, lines in files]


def _header_path(line: str) -> str:
    """The path of a `+++ b/<path>` header; '' for `/dev/null` (a deletion) or any form it does not know."""
    name = line[4:].rstrip("\t")
    return "" if name == "/dev/null" or not name.startswith("b/") else name[2:]


def _add_line(files: list[tuple[str, list[str]]], line: str) -> None:
    if not files:
        files.append(("", []))   # an added line before any header: no path, so never a note
    files[-1][1].append(line[1:])


def outside_notes(diffs: list[str], names: list[str]) -> tuple[str, str]:
    """(added lines, file names) of the files that are NOT free notes: all a private repo still filters."""
    added = [body for diff in diffs for path, body in split_diff(diff) if not is_free_note(path)]
    kept = [name for name in "\n".join(names).splitlines() if name and not is_free_note(name)]
    return "\n".join(added), "\n".join(kept)
