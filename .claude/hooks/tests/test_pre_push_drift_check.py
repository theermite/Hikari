"""Tests for guards/pre-push-drift-check.py — D1 brick 2.

Fix (2026-06-27): _drifted_files used find_repo_root().name to detect whether
the current dir is the canonical source. Inside a git worktree that name is the
worktree directory (branch-named), not the project name, so the check silently
failed. Now uses canonical_project_name() which resolves via
`git rev-parse --git-common-dir`.

PreToolUse Bash guard: when about to `git push` from a propagated project, warn
(never block) if any received methodology file has drifted from the Kata
canonical source. Degrades silently when the source is not reachable (e.g. VPS).

The hook locates the canonical source as a sibling directory named "Kata"
(all repos live side by side: D:/30-Dev-Projects/* locally, ~/apps/* on VPS),
overridable via the MNK_GORIN_SRC env var.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-push-drift-check.py"


# --- Helpers ----------------------------------------------------------------


def _write(base: Path, rel: str, content: str) -> None:
    p = base / ".claude" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _make_repo(base: Path) -> Path:
    (base / ".git").mkdir(parents=True, exist_ok=True)
    return base


def _run(cwd: Path, command: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"command": command}}
    env = None
    if env_extra is not None:
        import os
        env = {**os.environ, **env_extra}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(cwd),
        env=env,
    )


def _src_and_project(tmp_path: Path):
    """Create a sibling source 'Kata' and a project repo under tmp_path."""
    src = _make_repo(tmp_path / "Kata")
    proj = _make_repo(tmp_path / "Kobo")
    return src, proj


# --- Tests ------------------------------------------------------------------


def test_warns_on_drift_before_push(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write(src, "rules/Quality.md", "canonical body\n")
    _write(proj, "rules/Quality.md", "EDITED IN PROJECT\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0  # WARN, never block
    assert b"WARNING" in res.stderr
    assert b"rules/Quality.md" in res.stderr


def test_silent_when_no_drift(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write(src, "rules/Quality.md", "same\n")
    _write(proj, "rules/Quality.md", "same\n")
    res = _run(proj, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_silent_on_non_push_command(tmp_path):
    src, proj = _src_and_project(tmp_path)
    _write(src, "rules/Quality.md", "canonical\n")
    _write(proj, "rules/Quality.md", "edited\n")  # drift exists...
    res = _run(proj, "git status")  # ...but command is not a push
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_silent_when_source_missing(tmp_path):
    # A lone project with no sibling Kata and no env override.
    proj = _make_repo(tmp_path / "Kobo")
    _write(proj, "rules/Quality.md", "whatever\n")
    res = _run(proj, "git push")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_pass_when_cwd_is_canonical_source(tmp_path):
    # Editing files in Kata itself is legitimate — never warn there.
    src = _make_repo(tmp_path / "Kata")
    _write(src, "rules/Quality.md", "canonical\n")
    res = _run(src, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr


def test_env_override_locates_source(tmp_path):
    # Source not a sibling, but MNK_GORIN_SRC points to it.
    src = _make_repo(tmp_path / "elsewhere" / "canonical")
    proj = _make_repo(tmp_path / "projects" / "Kobo")
    _write(src, "rules/Quality.md", "canonical\n")
    _write(proj, "rules/Quality.md", "drifted\n")
    res = _run(proj, "git push", env_extra={"MNK_GORIN_SRC": str(src)})
    assert res.returncode == 0
    assert b"WARNING" in res.stderr
    assert b"rules/Quality.md" in res.stderr


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _real_repo(path: Path, name: str = "Kata") -> Path:
    """Create a real git repo (not just a .git dir) needed for worktree tests."""
    repo = path / name
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@test.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_no_warn_from_canonical_worktree(tmp_path):
    # Bug: inside a worktree of Kata (dir named e.g. "Kata-feature"), the old
    # find_repo_root().name check returned "Kata-feature" != "Kata" and the hook
    # would warn about drift even when running from the canonical source itself.
    src = _real_repo(tmp_path, "Kata")
    _write(src, "rules/Quality.md", "canonical\n")
    wt = tmp_path / "Kata-feature"
    _git(["worktree", "add", "-b", "feature", str(wt)], src)
    _write(wt, "rules/Quality.md", "canonical\n")
    res = _run(wt, "git push origin main")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr, (
        "hook should not warn when running from a worktree of the canonical source"
    )


def test_missing_file_does_not_warn(tmp_path):
    # An under-propagated (missing) file is not a local edit -> no push warning.
    src, proj = _src_and_project(tmp_path)
    _write(src, "rules/Quality.md", "canonical\n")
    _write(src, "rules/NewRule.md", "added to source\n")
    _write(proj, "rules/Quality.md", "canonical\n")  # NewRule.md absent in project
    res = _run(proj, "git push")
    assert res.returncode == 0
    assert b"WARNING" not in res.stderr
