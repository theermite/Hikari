#!/usr/bin/env python3
"""Shinzo sync reminder — SessionStart hook.

Non-blocking reminder of the 4 mandatory Shinzo project notes Takumi
MUST read at every session start (per Workflows.md "Sync Shinzo project
notes"). The hook does NOT read files itself — it surfaces the reminder
so Takumi loads the right files via the Read tool (no MCP needed).

The 4 files (in Shinzo/02-Projets/):
  1. _Cross-Project.md
  2. _Index.md
  3. <current-project>.md
  4. <current-project>-Notes-Jay.md

Shinzo path: D:/30-Dev-Projects/Shinzo (local) | ~/Shinzo (VPS).
Current project is auto-detected from the repo basename.

Exit code: 0 always (reminder is non-blocking, printed on stderr so
Takumi sees it; companion hook obsidian-mandatory-read.py blocks the
first mutating tool if the reads aren't done).
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

try:
    from common import (  # type: ignore
        canonical_project_name,
        find_repo_root,
        read_hook_input,
    )
except Exception:
    def read_hook_input():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
        return raw, {}

    def find_repo_root():
        return Path.cwd()

    def canonical_project_name():
        return Path.cwd().name


def _detect_project_name() -> str:
    # Canonical name stays correct inside a git worktree (branch-named dir).
    name = canonical_project_name()
    return name or "<project>"


def main() -> None:
    try:
        read_hook_input()
    except Exception:
        pass

    project = _detect_project_name()
    msg = (
        "SHINZO SYNC reminder (SessionStart) — Read these 3 mandatory files "
        "from Shinzo/02-Projets/ via the Read tool before any mutating tool:\n"
        f"  1. [SHINZO]/02-Projets/_Cross-Project.md\n"
        f"  2. [SHINZO]/02-Projets/_Index.md\n"
        f"  3. [SHINZO]/02-Projets/{project}.md\n"
        f"  (bonus: [SHINZO]/02-Projets/{project}-Notes-Jay.md if it exists)\n"
        "  [SHINZO] = D:/30-Dev-Projects/Shinzo (local) | ~/Shinzo (VPS)\n"
        "Companion hook obsidian-mandatory-read.py will BLOCK the first "
        "Edit/Write/Bash until the 3 mandatory patterns are read."
    )
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
