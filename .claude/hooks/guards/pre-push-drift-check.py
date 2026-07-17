#!/usr/bin/env python3
"""pre-push-drift-check.py — D1 brick 2: warn (never block) on methodology drift
before a `git push` from a propagated project.

Trigger: PreToolUse Bash whose command is a `git push`.

When fired from a propagated project (any repo NOT named Kata), it compares
that project's .claude/{rules,agents,hooks,skills} against the canonical
Kata source (MNK-GoRin methodology) and, if a received file was edited locally
(drift), prints a
WARNING listing the drifted files. It NEVER blocks the push (exit 0) — the right
fix is social/process (edit the source, re-propagate), not a hard stop.

Locating the source:
- env MNK_GORIN_SRC if set (absolute path to the Kata repo), else
- a sibling directory named "Kata" (all repos live side by side:
  D:/30-Dev-Projects/* locally, ~/apps/* on the VPS).
If the source is not found, the hook degrades silently (pass-through) — e.g. a
clone where the canonical repo is absent.

Why WARN, not BLOCK: drift is also produced legitimately when the source moved
ahead and the project has not been re-propagated yet (pending propagation). A
hard block would punish that benign case. The audit script
(scripts/audit-drift.py) is the exhaustive view; this guard is the in-context
nudge at the moment a divergence would be pushed.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import common  # noqa: E402
import drift  # noqa: E402

SYNC_DIRS = ("rules", "agents", "hooks", "skills")
CANONICAL_NAME = "Kata"
_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")


def _find_source(repo_root: Path) -> Path | None:
    """Locate the canonical Kata repo (MNK-GoRin methodology source), or None."""
    override = os.environ.get("MNK_GORIN_SRC", "").strip()
    if override:
        cand = Path(override)
        return cand if (cand / ".claude").is_dir() else None
    sibling = repo_root.parent / CANONICAL_NAME
    return sibling if (sibling / ".claude").is_dir() else None


def _drifted_files(data: dict) -> list[str]:
    """Drifted methodology files for a `git push` from a propagated project.

    Returns [] (nothing to warn) for any guard miss: not a push, in the canonical
    source itself, source unreachable, or no .claude dir.
    """
    if not _GIT_PUSH_RE.search(common.get_command(data)):
        return []
    repo_root = common.find_repo_root()
    if common.canonical_project_name(repo_root) == CANONICAL_NAME:
        return []
    source = _find_source(repo_root)
    if source is None:
        return []
    dst_claude = repo_root / ".claude"
    if not dst_claude.is_dir():
        return []
    return drift.classify_project(source / ".claude", dst_claude, SYNC_DIRS)["drifted"]


def _emit_warning(drifted: list[str]) -> None:
    listing = "\n".join(f"  ~ {f}" for f in drifted)
    common.warn(
        common.format_warn(
            f"{len(drifted)} methodology file(s) drifted from Kata "
            f"in this project (locally edited canonical file)",
            "Fix at the SOURCE (Kata) then re-propagate — do not edit "
            "propagated files in the project. "
            "(If the source merely moved ahead, run the propagation instead.)\n"
            f"{listing}",
            reference="rules/Workflows.md (methodology is canonical in Kata)",
        )
    )


def main() -> int:
    _, data = common.read_hook_input()
    drifted = _drifted_files(data)
    if drifted:
        _emit_warning(drifted)
    return 0  # WARN never blocks the push


if __name__ == "__main__":
    sys.exit(main())
