#!/usr/bin/env python3
"""Auto-commit & push Shinzo memory — PostToolUse(Write|Edit).

When a `.md` memory file is written under <SHINZO_DIR>/05-Memoire, stage it,
commit it, and push the Shinzo repo. Every new memory lands in Shinzo and is
persisted immediately.

Why: methodology decision 2026-06-28 — memory is code-enforced into Shinzo, not
left to AI discipline (see Shinzo 05-Memoire feedback-code-enforcement-over-
instruction-reliance). Pairs with the `autoMemoryDirectory` user setting that
redirects the agent memory dir to Shinzo/05-Memoire.

Never blocks: PostToolUse always exits 0. Push failure → WARNING, commit stays
local. SHINZO_DIR overrides the repo root (per-machine path + test injection).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_SHINZO_DIR = "D:/30-Dev-Projects/Shinzo"
MEMORY_SUBDIR = "05-Memoire"
GIT_TIMEOUT = 30


def _shinzo_root() -> Path:
    return Path(os.environ.get("SHINZO_DIR", DEFAULT_SHINZO_DIR))


def _read_data() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _file_path(data: dict) -> str:
    tool_input = data.get("tool_input") or data
    return (tool_input.get("file_path") or "").replace("\\", "/")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )


def _is_memory_file(file_path: str, root: Path) -> bool:
    if not file_path.lower().endswith(".md"):
        return False
    mem_dir = (root / MEMORY_SUBDIR).as_posix().lower()
    return file_path.lower().startswith(mem_dir + "/")


def _rel_path(abs_path: Path, root: Path) -> str:
    try:
        return abs_path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return abs_path.as_posix()


def _commit_and_push(root: Path, abs_path: Path) -> str | None:
    """Stage, commit and push the memory file. Return a stderr line, or None."""
    _git(root, "add", "--", _rel_path(abs_path, root))
    if _git(root, "diff", "--cached", "--quiet").returncode == 0:
        return None  # nothing actually changed → no empty commit

    basename = abs_path.name
    message = f'chore(memory): {basename}\n\nCo-Authored-By: Takumi "IA Dev Partner"'
    commit = _git(root, "commit", "-m", message)
    if commit.returncode != 0:
        return f"WARNING: memory auto-commit failed. ACTION: commit Shinzo manually. {commit.stderr.strip()}"

    push = _git(root, "push")
    if push.returncode != 0:
        return f"WARNING: memory committed but auto-push failed. ACTION: push Shinzo manually. {push.stderr.strip()}"

    return f"[memory] committed + pushed: {basename}"


def main() -> None:
    data = _read_data()
    file_path = _file_path(data)
    root = _shinzo_root()

    if not file_path or not _is_memory_file(file_path, root) or not root.exists():
        sys.exit(0)

    try:
        line = _commit_and_push(root, Path(file_path))
        if line:
            print(line, file=sys.stderr)
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"WARNING: memory auto-commit error. ACTION: check Shinzo repo. {exc}",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
