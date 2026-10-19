#!/usr/bin/env python3
"""PostToolUse Bash: when Kata has moved a file a project keeps a frozen copy
of, tell the session once that the copy is behind and how to refresh it.

Fires on any git command (commit, merge, pull, rebase...) run in the Kata repo
(it carries `scripts/propagate-methodology.py`), `git -C <dir>` included. It
remembers the last state of Kata it judged (`.claude/state/`) and speaks only
when HEAD moved since, about the files changed in between, as committed (not
as on disk). Silent everywhere else; never blocks: Kata must stay free to
change, the copy is the project's to refresh. See `lib/frozen_copies.py`.
Origin: Jay, 2026-10-18; redesigned after its first review (repeated alert,
merge and `git -C` unheard, disk read instead of the commit).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import get_command, pass_through, read_hook_input, warn  # noqa: E402
from frozen_copies import behind, message  # noqa: E402

_GIT_RE = re.compile(r"\bgit\b")
_DASH_C_RE = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*-C\s+(\"[^\"]+\"|'[^']+'|\S+)")
STATE_FILE = Path(".claude") / "state" / "frozen-copy-alert.json"


def _git(where: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(where), *args], capture_output=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


def _where(data: dict, command: str) -> Path:
    """The directory the git command ran in: `-C <dir>` first, then the session's."""
    base = Path(data.get("cwd") or os.getcwd())
    if match := _DASH_C_RE.search(command):
        return base / Path(os.path.expanduser(match.group(1).strip("\"'")))
    return base


def _last_head(state: Path) -> str | None:
    """The HEAD judged last time; anything unreadable counts as never judged."""
    try:
        saved = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    head = saved.get("head") if isinstance(saved, dict) else None
    return head if isinstance(head, str) else None


def _changed(top: Path, last: str | None, head: str) -> set[str]:
    if last:
        names = _git(top, "diff", "--name-only", last, head)
    else:
        names = _git(top, "diff", "--name-only", f"{head}^1", head)
        if names is None:
            names = _git(top, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", head)
    return set((names or "").splitlines())


def main() -> None:
    _, data = read_hook_input()
    command = get_command(data)
    if not _GIT_RE.search(command):
        pass_through()
    found = _git(_where(data, command), "rev-parse", "--show-toplevel")
    if not found:
        pass_through()
    top = Path(found.strip())
    if not (top / "scripts" / "propagate-methodology.py").is_file():
        pass_through()
    head = (_git(top, "rev-parse", "HEAD") or "").strip()
    state = top / STATE_FILE
    last = _last_head(state)
    if not head or head == last:
        pass_through()
    # Only a step forward is remembered and judged. Going back (reset, checkout of
    # an older commit) says nothing and forgets nothing: coming forward again to
    # what was already judged stays silent.
    if last and _git(top, "merge-base", "--is-ancestor", last, head) is None:
        pass_through()
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"head": head}), encoding="utf-8")
    except OSError:
        pass_through()  # an alert that cannot remember would repeat: say nothing
    changed = _changed(top, last, head)

    def committed(source: str) -> bytes | None:
        try:
            out = subprocess.run(
                ["git", "-C", str(top), "show", f"{head}:{source}"], capture_output=True, timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        return out.stdout if out.returncode == 0 else None

    late = [item for item in behind(top, read=committed) if item.source in changed]
    if not late:
        pass_through()
    text = message(late)
    warn(text)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
