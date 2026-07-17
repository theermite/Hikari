#!/usr/bin/env python3
"""Atomic commit check — PreToolUse Bash.

Enforces Conventions.md "Atomic Commits": one logical change per commit.
Before `git commit`, inspect staged files. If they span multiple distinct
scopes -> WARN (heuristic detection, soft enforcement).

Scope detection (heuristic):
  - Group staged files by top-level meaningful path segment
  - Distinct scope groups exceeding threshold -> WARN
  - Always-paired files (test + source, .ts + .test.ts) count as one scope

The hook is non-blocking (WARN) because scope detection is imperfect and
some legitimate commits touch multiple areas (e.g., methodology rollout).
Recovery hint suggests `git reset` + smaller commits.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root, get_command, pass_through, read_hook_input, warn  # type: ignore

COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)

# Threshold: how many distinct scopes before we WARN
SCOPE_THRESHOLD = 3


def is_git_commit(command: str) -> bool:
    """True if the bash command runs `git commit`."""
    if not command:
        return False
    # Skip `git commit --help` or `git log`
    if re.search(r"\bgit\s+(log|status|diff|show)\b", command):
        return False
    return bool(COMMIT_PATTERN.search(command))


def get_staged_files(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def normalize_scope(file_path: str) -> str:
    """Return a meaningful scope label for grouping staged files.

    Examples:
      .claude/hooks/quality/foo.py  -> .claude/hooks
      src/auth/login.ts             -> src/auth
      docs/Sessions/2026-05-17.md   -> docs/Sessions
      scripts/test-hooks.py         -> scripts
      package.json                  -> ROOT
      README.md                     -> ROOT
    """
    norm = file_path.replace("\\", "/")
    parts = norm.split("/")
    if len(parts) <= 1:
        return "ROOT"
    # First 2 path segments capture most meaningful scopes
    if len(parts) >= 3:
        return "/".join(parts[:2])
    return parts[0]


def group_scopes(files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for f in files:
        scope = normalize_scope(f)
        groups.setdefault(scope, []).append(f)
    return groups


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not is_git_commit(cmd):
        pass_through()

    repo_root = find_repo_root()
    staged = get_staged_files(repo_root)
    if not staged:
        pass_through()  # Nothing staged; git commit will fail on its own

    groups = group_scopes(staged)
    if len(groups) < SCOPE_THRESHOLD:
        pass_through()

    summary_lines = [f"  - {scope}: {len(files)} file(s)" for scope, files in sorted(groups.items())]
    summary = "\n".join(summary_lines)
    warn(
        f"WARNING: Staged commit spans {len(groups)} distinct scopes (threshold: {SCOPE_THRESHOLD}). "
        "ACTION: Consider splitting into atomic commits — one logical change per commit. "
        "Use `git reset HEAD <file>` to unstage, then `git add` + `git commit` per scope.\n"
        "Staged scopes:\n"
        f"{summary}\n"
        "If this commit is intentionally cross-scope (methodology rollout, release bump), continue. "
        "See rules/Conventions.md 'Atomic Commits'."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
