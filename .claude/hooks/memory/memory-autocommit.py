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

import importlib.util
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


def _regenerate_summaries(root: Path) -> list[str]:
    """Rebuild README.md + MEMORY.md from the memory files. Return their paths.

    Why here: the summaries are GENERATED, but nothing ran the generator. Every
    memory written made the index a little more false — measured 2026-09-06:
    601 announced for 604 files, 28 indexed for 283. A generator nobody runs
    produces exactly the drift a hand-copied summary does.

    Where it lives, and why it moved (relecture independante, 2026-09-06): the
    generator used to sit in `scripts/`, which is NOT propagated to the 32 repos.
    Shinzo is shared — a memory written from any repo lands there — so the index
    was only rebuilt when the memory happened to be written from Kata. Silently
    the rest of the time: the very drift this hook exists to close, coming back
    through 32 doors. It now lives in `hooks/lib/`, which travels.
    """
    generator = Path(__file__).resolve().parent.parent / "lib" / "memory_index.py"
    if not generator.is_file():
        raise FileNotFoundError(str(generator))
    spec = importlib.util.spec_from_file_location("memory_index", generator)
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_index"] = module
    spec.loader.exec_module(module)
    module.ecrire_index(root / MEMORY_SUBDIR)
    return [f"{MEMORY_SUBDIR}/README.md", f"{MEMORY_SUBDIR}/MEMORY.md"]


def _stage_summaries(root: Path) -> list[str]:
    """Regenerate then stage the summaries. Never fatal — the memory matters more."""
    try:
        sommaires = _regenerate_summaries(root)
    except Exception as exc:
        print(f"WARNING: sommaires memoire non regeneres ({exc}). "
              "ACTION: relancer le sommaire — `python .claude/hooks/lib/memory_index.py`. Le souvenir, lui, part.", file=sys.stderr)
        return []
    for sommaire in sommaires:
        _git(root, "add", "--", sommaire)
    return sommaires


def _commit_and_push(root: Path, abs_path: Path) -> str | None:
    """Stage, commit and push the memory file. Return a stderr line, or None.

    Every git call is scoped to NAMED paths. Another session may be writing the
    same repo at the same time: an unscoped `diff --cached` would read its staged
    work as "something changed", and an unscoped `commit` would carry that work
    away under a `chore(memory)` message (observed 2026-08-10).
    """
    rel = _rel_path(abs_path, root)
    _git(root, "add", "--", rel)
    if _git(root, "diff", "--cached", "--quiet", "--", rel).returncode == 0:
        return None  # this memory did not change → no empty commit

    chemins = [rel, *_stage_summaries(root)]

    basename = abs_path.name
    message = f'chore(memory): {basename}\n\nCo-Authored-By: Takumi "IA Dev Partner"'
    commit = _git(root, "commit", "-m", message, "--", *chemins)
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
