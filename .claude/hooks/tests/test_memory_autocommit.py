"""memory-autocommit.py — PostToolUse(Write|Edit) Shinzo memory auto-commit/push.

Behavior:
- When a `.md` file is written under <SHINZO_DIR>/05-Memoire, stage + commit +
  push the Shinzo repo.
- Push failure → exit 0 + WARNING (commit stays local).
- Anything else (file outside the memory dir, non-md, empty/malformed stdin,
  no actual change) → silent exit 0.

Uses a REAL temporary git repo (no bash stub) so it runs on every OS, Windows
included. The Shinzo root is injected via the SHINZO_DIR env var.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "memory" / "memory-autocommit.py"


# --- helpers -----------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )


def _init_repo(tmp_path: Path, with_remote: bool = True) -> Path:
    """Init a Shinzo-like repo with a 05-Memoire dir and one initial commit."""
    root = tmp_path / "Shinzo"
    (root / "05-Memoire").mkdir(parents=True)
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "branch", "-M", "main")
    (root / "README.md").write_text("seed", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    if with_remote:
        bare = tmp_path / "remote.git"
        _git(tmp_path, "init", "-q", "--bare", str(bare))
        _git(root, "remote", "add", "origin", str(bare))
        _git(root, "push", "-q", "-u", "origin", "main")
    return root


def _run(payload: dict, root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "SHINZO_DIR": str(root)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=30,
        env=env,
    )


def _commit_count(root: Path) -> int:
    return int(_git(root, "rev-list", "--count", "HEAD").stdout.strip())


def _write_memory(root: Path, name: str, body: str = "fact") -> Path:
    f = root / "05-Memoire" / name
    f.write_text(body, encoding="utf-8")
    return f


# --- commit/push path --------------------------------------------------------


def test_commits_and_pushes_when_memory_written(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    before = _commit_count(root)
    f = _write_memory(root, "feedback-new-thing.md")
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    assert r.returncode == 0
    assert _commit_count(root) == before + 1, "a commit must be created"
    assert b"committed" in r.stderr.lower()
    # file is tracked (not untracked anymore)
    status = _git(root, "status", "--porcelain").stdout
    assert "feedback-new-thing.md" not in status, "file must be committed, not pending"


def test_push_failure_warns_but_commit_stays(tmp_path):
    root = _init_repo(tmp_path, with_remote=False)  # no origin → push fails
    before = _commit_count(root)
    f = _write_memory(root, "feedback-no-remote.md")
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    assert r.returncode == 0, "PostToolUse must never block"
    assert _commit_count(root) == before + 1, "commit must happen even if push fails"
    assert b"WARNING" in r.stderr
    assert b"push" in r.stderr.lower()


# --- silent / non-trigger paths ---------------------------------------------


def test_silent_when_no_change(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    f = _write_memory(root, "feedback-once.md")
    _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    before = _commit_count(root)
    # second run, file unchanged → nothing to commit
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    assert r.returncode == 0
    assert _commit_count(root) == before, "no empty commit when nothing changed"


def test_silent_on_file_outside_memory_dir(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    before = _commit_count(root)
    other = root / "08-Notes"
    other.mkdir()
    f = other / "note.md"
    f.write_text("raw", encoding="utf-8")
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    assert r.returncode == 0
    assert _commit_count(root) == before, "files outside 05-Memoire must be ignored"
    assert r.stderr == b""


def test_silent_on_non_markdown(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    before = _commit_count(root)
    f = root / "05-Memoire" / "data.txt"
    f.write_text("x", encoding="utf-8")
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    assert r.returncode == 0
    assert _commit_count(root) == before
    assert r.stderr == b""


# --- multi-session isolation -------------------------------------------------
#
# Two sessions can write Shinzo at the same time. The hook must commit ONLY the
# memory file it was given, and leave every other staged file where it is —
# otherwise the first session to commit carries away the other one's work under
# its own message (observed 2026-08-10, see docs/Briefs/Isolation-Commits-
# Shinzo-Multi-Sessions-2026-08-10.md).


def _staged_paths(root: Path) -> set[str]:
    out = _git(root, "diff", "--cached", "--name-only").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _paths_in_head(root: Path) -> set[str]:
    out = _git(root, "show", "--pretty=", "--name-only", "HEAD").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def test_commit_excludes_a_file_staged_by_another_session(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    # another session stages its own work
    other = root / "02-Projets"
    other.mkdir()
    (other / "Takumi.md").write_text("work from the other session", encoding="utf-8")
    _git(root, "add", "--", "02-Projets/Takumi.md")

    f = _write_memory(root, "feedback-isolation.md")
    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)

    assert r.returncode == 0
    assert _paths_in_head(root) == {"05-Memoire/feedback-isolation.md"}, (
        "the memory commit must carry the memory file and nothing else"
    )
    assert "02-Projets/Takumi.md" in _staged_paths(root), (
        "the other session's file must stay staged, available to its owner"
    )


def test_no_commit_when_memory_unchanged_even_if_another_file_is_staged(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    f = _write_memory(root, "feedback-stable.md")
    _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)
    before = _commit_count(root)

    # another session stages work; the memory itself did not change
    other = root / "02-Projets"
    other.mkdir()
    (other / "Boken.md").write_text("unrelated work", encoding="utf-8")
    _git(root, "add", "--", "02-Projets/Boken.md")

    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)

    assert r.returncode == 0
    assert _commit_count(root) == before, (
        "an unchanged memory must not produce a commit just because the index is dirty"
    )
    assert "02-Projets/Boken.md" in _staged_paths(root), (
        "the other session's file must stay staged"
    )


def test_working_tree_version_wins_over_a_stale_staged_version(tmp_path):
    """`git commit -- <path>` bypasses the index and takes the working tree.

    That is the behavior we want — the memory was just written — but it is a
    consequence of the pathspec, so it is pinned here rather than assumed.
    """
    root = _init_repo(tmp_path, with_remote=True)
    f = _write_memory(root, "feedback-stale-index.md", "old version")
    _git(root, "add", "--", "05-Memoire/feedback-stale-index.md")
    f.write_text("new version", encoding="utf-8")  # written after staging

    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)

    assert r.returncode == 0
    committed = _git(
        root, "show", "HEAD:05-Memoire/feedback-stale-index.md"
    ).stdout.strip()
    assert committed == "new version", "the freshly written version must be committed"


def test_commits_a_brand_new_memory_never_tracked_by_git(tmp_path):
    """Guard: `git commit -- <path>` fails on a path git does not know yet.

    The hook stages before committing, so it is safe — but a brand-new memory is
    the most common case, so it is proven here rather than assumed.
    """
    root = _init_repo(tmp_path, with_remote=True)
    before = _commit_count(root)
    f = _write_memory(root, "feedback-brand-new.md")

    r = _run({"tool_name": "Write", "tool_input": {"file_path": str(f)}}, root)

    assert r.returncode == 0
    assert _commit_count(root) == before + 1, "a brand-new memory must be committed"
    assert "05-Memoire/feedback-brand-new.md" in _paths_in_head(root)
    assert b"WARNING" not in r.stderr


def test_silent_on_empty_stdin(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"",
        capture_output=True,
        timeout=30,
        env={**os.environ, "SHINZO_DIR": str(root)},
    )
    assert r.returncode == 0


def test_silent_on_malformed_json(tmp_path):
    root = _init_repo(tmp_path, with_remote=True)
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"not json",
        capture_output=True,
        timeout=30,
        env={**os.environ, "SHINZO_DIR": str(root)},
    )
    assert r.returncode == 0
