#!/usr/bin/env python3
"""Docs progress freshness — PreToolUse(Bash git commit).

When Takumi runs `git commit` with a feat/fix scope, the doc trail
(CDC, PET, Session report) should be fresh. This hook is a soft
reminder: WARN (non-block) when the session log directory has no entry
for today.

Trigger only on `git commit` with a conventional-commits type in
{feat, fix, refactor, perf}. Other types (chore, docs, ci, test, style)
do not require doc updates by themselves.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import (  # noqa: E402
    find_repo_root,
    format_warn,
    get_command,
    pass_through,
    read_hook_input,
    warn,
)


TRIGGER_TYPES = ("feat", "fix", "refactor", "perf")
COMMIT_RE = re.compile(r"git\s+commit\b(.*)", re.DOTALL)
TYPE_RE = re.compile(r"^(feat|fix|refactor|perf|chore|docs|ci|test|style|build)(\([^)]+\))?:", re.MULTILINE)


def extract_commit_type(cmd: str) -> str | None:
    """Best-effort extraction of conventional-commits type from a `git commit` line."""
    m = COMMIT_RE.search(cmd)
    if not m:
        return None
    rest = m.group(1)
    # Look for -m "type(scope): ..." or -m 'type: ...'
    type_match = TYPE_RE.search(rest)
    if not type_match:
        return None
    return type_match.group(1)


def has_session_report_today(repo: Path) -> bool:
    """Return True if docs/Sessions/ has a *YYYY-MM-DD*.md for today."""
    sessions = repo / "docs" / "Sessions"
    if not sessions.is_dir():
        return False
    today = date.today().isoformat()
    return any(today in p.name for p in sessions.glob("*.md"))


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd:
        pass_through()

    ctype = extract_commit_type(cmd)
    if ctype not in TRIGGER_TYPES:
        pass_through()

    repo = find_repo_root()
    if has_session_report_today(repo):
        pass_through()

    warn(format_warn(
        f"`git commit` ({ctype}) sans session report fresh for today ({date.today().isoformat()})",
        "Cree ou mets a jour docs/Sessions/Session-<date>-NNN.md apres ce commit. "
        "Les commits feat/fix/refactor/perf doivent etre traces dans le rapport de session",
        reference="rules/Workflows.md (rapports de session obligatoires)",
    ))
    pass_through()


if __name__ == "__main__":
    main()
