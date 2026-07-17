#!/usr/bin/env python3
"""Notes-Jay marker check — SessionEnd.

Workflows.md "Notes-Jay processing": each project has `<project>-Notes-Jay.md`
in Obsidian. Items have status markers (👀 / 🔧 / ✅). At session end, all
items touched in the session MUST have their marker updated.

This hook does NOT have access to the Obsidian MCP vault directly. It only
checks any *Notes-Jay*.md files present in the repo (some projects mirror
them locally). The Obsidian-side enforcement remains advisory.

Behavior:
  - Find any `*Notes-Jay*.md` under the repo
  - Count items without a recognized marker
  - Print a SessionEnd summary on stderr (non-blocking — SessionEnd cannot block)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root, pass_through, read_hook_input, warn  # noqa: E402


MARKER_RE = re.compile(r"(👀|🔧|✅|Lu \d|En cours|✅ \d{4}-\d{2}-\d{2})", re.UNICODE)
# Heuristic for "item line": markdown list entry starting with -, *, or numbered
ITEM_RE = re.compile(r"^\s*([-*]|\d+\.)\s+\S")


def count_unseen(path: Path) -> tuple[int, int]:
    """Return (total_items, items_without_marker) for a Notes-Jay file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0
    total, unseen = 0, 0
    for line in text.splitlines():
        if not ITEM_RE.match(line):
            continue
        total += 1
        if not MARKER_RE.search(line):
            unseen += 1
    return total, unseen


def main() -> None:
    read_hook_input()  # drain stdin; SessionEnd has no useful tool input
    repo = find_repo_root()

    candidates = list(repo.glob("**/*Notes-Jay*.md"))
    if not candidates:
        pass_through()

    summary = []
    grand_total, grand_unseen = 0, 0
    for p in candidates:
        total, unseen = count_unseen(p)
        if total == 0:
            continue
        grand_total += total
        grand_unseen += unseen
        if unseen > 0:
            summary.append(f"  - {p.relative_to(repo).as_posix()}: {unseen}/{total} sans marker")

    if grand_unseen > 0:
        warn(
            f"SESSION END — Notes-Jay: {grand_unseen}/{grand_total} item(s) sans marker (👀/🔧/✅).\n"
            + "\n".join(summary)
            + "\n  ACTION: verifie dans Shinzo 02-Projets/[project]-Notes-Jay.md que les items traites ont leur marker mis a jour."
        )

    pass_through()


if __name__ == "__main__":
    main()
