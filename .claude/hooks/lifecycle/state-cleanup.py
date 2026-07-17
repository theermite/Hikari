#!/usr/bin/env python3
"""State cleanup — SessionEnd only.

The `.claude/state/` directory accumulates handoff briefs (one per
session that crossed the 85% context threshold), snapshot files, and
other transient artefacts. Over time it bloats and becomes hard to scan.

This hook archives `.claude/state/handoff-*.md` files older than
RETAIN_DAYS into `.claude/state/_archive/YYYY-MM/` once per session-end.

Design note (5S Seiri + LLM-code split, Jay 2026-05-19):
  Asking the LLM to "clean up old handoffs at session end" was unreliable
  and burned tokens. Determinism wins — the script does it silently.

NEVER blocks. NEVER warns destructively. Pure maintenance.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from common import find_repo_root, pass_through, read_hook_input  # noqa: E402


RETAIN_DAYS = 7
HANDOFF_GLOB = "handoff-*.md"


def main() -> None:
    _, data = read_hook_input()
    event = (data.get("hook_event_name") or "").lower()
    if event != "sessionend":
        pass_through()

    repo = find_repo_root()
    state_dir = repo / ".claude" / "state"
    if not state_dir.exists():
        pass_through()

    cutoff = time.time() - (RETAIN_DAYS * 86400)
    archived = 0
    failed = 0

    for path in state_dir.glob(HANDOFF_GLOB):
        if not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            failed += 1
            continue
        if mtime >= cutoff:
            continue

        # Archive bucket: .claude/state/_archive/YYYY-MM/
        bucket = time.strftime("%Y-%m", time.localtime(mtime))
        dest_dir = state_dir / "_archive" / bucket
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest_dir / path.name))
            archived += 1
        except (OSError, shutil.Error):
            failed += 1

    if archived or failed:
        sys.stderr.write(
            f"[state-cleanup] archived={archived} failed={failed} "
            f"(retain={RETAIN_DAYS}d) -> {state_dir.as_posix()}/_archive\n"
        )
    pass_through()


if __name__ == "__main__":
    main()
