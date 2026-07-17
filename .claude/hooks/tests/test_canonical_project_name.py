"""canonical_project_name() — stable project name inside a git worktree.

Bug (2026-06-23): the obsidian-mandatory-read gate derived the project name
from find_repo_root().name. Inside a linked git worktree that name is the
worktree directory (branch-named), NOT the project. The Obsidian note
`01-Projets/<project>.md` then never matched the required pattern and the
gate blocked forever, unsatisfiable.

canonical_project_name resolves the *main* repo name via
`git rev-parse --git-common-dir` (which points at <project>/.git regardless
of which worktree we sit in), and falls back to the local dir name when git
is unavailable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

from common import canonical_project_name  # noqa: E402


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProjectMain"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_name_in_main_tree(main_repo: Path) -> None:
    assert canonical_project_name(main_repo) == "ProjectMain"


def test_name_in_worktree(main_repo: Path, tmp_path: Path) -> None:
    wt = tmp_path / "ProjectMain-feature"
    _git(["worktree", "add", "-b", "feature", str(wt)], main_repo)
    # Inside the worktree the canonical name must still be the main project,
    # not the branch-named worktree directory.
    assert canonical_project_name(wt) == "ProjectMain"


def test_fallback_outside_git(tmp_path: Path) -> None:
    lone = tmp_path / "LoneDir"
    lone.mkdir()
    # Not a git repo -> falls back to the directory name, never crashes.
    assert canonical_project_name(lone) == "LoneDir"
