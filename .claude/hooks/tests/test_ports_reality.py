"""ports_registry — le registre contre la realite du serveur, et la recherche du registre depuis une copie de travail.

Mesure 2026-10-31 (lecture seule sur le serveur): 12 ports ecoutent sans figurer dans aucune des deux
listes (dont 8446-8449 et 5442/5443) — la cause racine d'une seance qui prend un port « libre » qui ne
l'est pas. Et depuis une copie de travail (git worktree), `repo.parent / "Shinkofa-Infra"` ne trouve rien:
le garde de port et la mesure hebdomadaire laissaient passer en silence.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import ports_registry as pr  # noqa: E402


def test_listeners_missing_from_the_registry_are_reported():
    owners = {3001: "app", 8445: "console"}
    assert pr.unregistered_listeners({3001, 8445, 8446, 5442}, owners) == [5442, 8446]


def test_system_and_ephemeral_ports_are_not_registry_business():
    assert pr.unregistered_listeners({22, 53, 80, 443, 32768, 36105, 64738}, {64738: "mumble"}) == []


def test_nothing_is_reported_when_the_registry_is_unreadable():
    assert pr.unregistered_listeners({8446}, {}) == []


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def test_the_registry_is_found_from_a_worktree(tmp_path):
    infra = tmp_path / "Shinkofa-Infra"
    (infra / "registry").mkdir(parents=True)
    kata = tmp_path / "Kata"
    kata.mkdir()
    _git(kata, "init", "-q")
    _git(kata, "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
    worktree = kata / ".claude" / "worktrees" / "w"
    _git(kata, "worktree", "add", "-q", str(worktree), "-b", "w")
    assert pr.find_infra_root(worktree) == infra


def test_the_registry_is_found_beside_a_plain_repo(tmp_path):
    infra = tmp_path / "Shinkofa-Infra"
    (infra / "registry").mkdir(parents=True)
    repo = tmp_path / "Kata"
    repo.mkdir()
    assert pr.find_infra_root(repo) == infra


def test_no_registry_is_none(tmp_path):
    repo = tmp_path / "Kata"
    repo.mkdir()
    assert pr.find_infra_root(repo, home=tmp_path / "nowhere") is None
