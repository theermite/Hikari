#!/usr/bin/env python3
"""Memory format gate — PreToolUse(Write). A memory is written with its fields, BEFORE the write.

Conversion n°4 of the reactive/anticipative audit (2026-11-24). Measured that day: 643 memories, 432 in the flat schema of
the `Memoire-Format` annex, 211 in the nested format (`metadata:`) the harness writes. A strict gate would refuse the
harness's own format, so BOTH are accepted; what is missing is warned (procedure: never blocks, Jay 2026-11-22).

Checks (facts read from the file about to be written, no wording guessed):
- frontmatter present; `name`, `description`, a valid `type` (feedback | project | user | reference);
- a `feedback` or `project` memory carries its « how to apply » (an anecdote without it is not a lesson, rule 05 § 2);
- the schema keys (audience, status, confidence, why, date) are named when absent, in either format.
Limits written: only a full `Write` is seen (an `Edit` shows a fragment, not the file); the body check looks for the
phrase « How to apply » / « Comment l'appliquer », not for its quality; fails open on any error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_block,
    get_content,
    get_file_path,
    pass_through,
    procedure_warn,
    read_hook_input,
)

TYPES = ("feedback", "project", "user", "reference")
SCHEMA_KEYS = ("audience", "status", "confidence", "why", "date")
NEEDS_APPLY = ("feedback", "project")
_APPLY = re.compile(r"(?i)how to apply|comment (?:l['’] ?)?appliquer")
_KEY = re.compile(r"^\s*([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$")


def is_memory_path(path: str) -> bool:
    p = path.replace("\\", "/")
    if "/05-Memoire/" not in p or not p.endswith(".md"):
        return False
    rest = p.split("/05-Memoire/", 1)[1]
    return rest not in ("MEMORY.md", "README.md") and not rest.startswith("_")


def parse(content: str) -> tuple[dict[str, str] | None, str]:
    """(keys of the frontmatter, body). Nested keys under `metadata:` count as keys; None when there is no frontmatter."""
    lines = content.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None, content
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, content
    keys: dict[str, str] = {}
    for line in lines[1:end]:
        m = _KEY.match(line)
        if m:
            keys.setdefault(m.group(1), m.group(2).strip("\"'"))
    return keys, "\n".join(lines[end + 1:])


def problems(content: str) -> list[str]:
    keys, body = parse(content)
    if keys is None:
        return ["pas d'entête (--- … ---) : name, description, type et les champs du schéma manquent"]
    found = [f"champ `{k}` absent" for k in ("name", "description") if not keys.get(k)]
    found += _type_problems(keys.get("type", ""), body)
    missing = [k for k in SCHEMA_KEYS if not keys.get(k)]
    if missing:
        found.append("champs du schéma absents : " + ", ".join(missing))
    return found


def _type_problems(kind: str, body: str) -> list[str]:
    if not kind:
        return ["champ `type` absent"]
    if kind not in TYPES:
        return [f"`type: {kind}` inconnu (attendu : {' | '.join(TYPES)})"]
    if kind in NEEDS_APPLY and not _APPLY.search(body):
        return ["pas de « Comment l'appliquer » (un souvenir sans cela est une anecdote)"]
    return []


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("tool_name") != "Write":
        pass_through()
    path = get_file_path(data)
    content = get_content(data)
    if not path or not content or not is_memory_path(path):
        pass_through()
    found = problems(content)
    if found:
        procedure_warn(format_block(
            "souvenir incomplet : " + " ; ".join(found),
            "complète l'entête avant d'écrire (les deux formats sont acceptés : plat, ou imbriqué sous `metadata:`)",
            reference=".claude/rules-ondemand/Memoire-Format.md",
        ))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a write
        print(f"[memory-format-gate] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
