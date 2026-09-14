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

**CLAUDE.md check (2026-09-14)**: same trigger, same WARN-never-BLOCK, runs
`scripts/check-claude-md.py` on this repo's CLAUDE.md file(s). Nothing ran
that checker anywhere before this — a stale entry point could rot silently
forever (audit 2026-09-13, 42 files, most carrying a dead path or a document
long abandoned). Unlike the drift check, this one ALSO runs from Kata itself:
a project's identity file is never exempt just because it lives in the
canonical repo.

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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import common  # noqa: E402
import drift  # noqa: E402

SYNC_DIRS = ("rules", "agents", "hooks", "skills")
CANONICAL_NAME = "Kata"
_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")
# Reconnait la ligne de resume de check-claude-md.py PAR SA FORME, jamais par
# sa position. `lines[:-1]` supposait que le resume est toujours la derniere
# ligne -- faux des que le script plante avant de l'imprimer (relecture
# independante 2026-09-14) : la derniere ligne restante devient alors un vrai
# defaut, et l'ancien code l'avalait avec le resume absent.
_SUMMARY_RE = re.compile(r"^\d+ fichier\(s\), \d+ defaut\(s\)$")


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


def _claude_md_files(repo_root: Path) -> list[Path]:
    """This repo's CLAUDE.md file(s) -- root and/or .claude/, either or both."""
    candidates = (repo_root / "CLAUDE.md", repo_root / ".claude" / "CLAUDE.md")
    return [p for p in candidates if p.is_file()]


def _checker_script(repo_root: Path, source: Path | None) -> Path | None:
    """Where scripts/check-claude-md.py lives for this repo, or None.

    Kata carries its own copy; a propagated project reads it from the source.
    Absent (old Kata, source unreachable) -> None, caller degrades silently.
    """
    base = repo_root if common.canonical_project_name(repo_root) == CANONICAL_NAME else source
    if base is None:
        return None
    script = base / "scripts" / "check-claude-md.py"
    return script if script.is_file() else None


def _run_checker(script: Path, files: list[Path]) -> str:
    """stdout of `check-claude-md.py --check`, or "" on any failure to run it."""
    try:
        result = subprocess.run(
            [sys.executable, str(script), *(str(f) for f in files), "--check"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode != 0 else ""


def _defect_lines(stdout: str) -> list[str]:
    """`stdout` minus its trailing "N fichier(s), M defaut(s)" summary line.

    The summary is dropped by its own SHAPE, never by position: a checker
    crash (e.g. a CLAUDE.md with invalid encoding) can print defects for an
    earlier file then die before reaching its own summary print -- the last
    surviving line is then a real defect, never the summary (independent
    review, 2026-09-14).
    """
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    return [ln for ln in lines if not _SUMMARY_RE.match(ln)]


def _stale_claude_md_lines(data: dict) -> list[str]:
    """Defect lines from `check-claude-md.py --check` on this repo's CLAUDE.md(s).

    [] for any guard miss: not a push, no CLAUDE.md here, or the checker
    script itself is unreachable (never crash a push over a missing tool).
    """
    if not _GIT_PUSH_RE.search(common.get_command(data)):
        return []
    repo_root = common.find_repo_root()
    files = _claude_md_files(repo_root)
    if not files:
        return []
    script = _checker_script(repo_root, _find_source(repo_root))
    if script is None:
        return []
    return _defect_lines(_run_checker(script, files))


def _emit_claude_md_warning(lines: list[str]) -> None:
    listing = "\n".join(f"  ~ {ln}" for ln in lines)
    common.warn(
        common.format_warn(
            f"{len(lines)} defaut(s) dans le(s) CLAUDE.md de ce depot",
            "Corriger (chemin mort, document abandonne, taille) puis relancer "
            f"le controle avant de pousser a nouveau.\n{listing}",
            reference="Kata/scripts/check-claude-md.py",
        )
    )


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
    stale = _stale_claude_md_lines(data)
    if stale:
        _emit_claude_md_warning(stale)
    return 0  # WARN never blocks the push


if __name__ == "__main__":
    sys.exit(main())
