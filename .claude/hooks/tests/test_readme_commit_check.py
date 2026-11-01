"""readme-commit-check.py — le commit FAIT porte son README quand il change la mise en route ou les commandes.

Historique (2026-10-30) : premiere version = garde AVANT la commande, qui devinait le contenu du commit en lisant la
commande. Deux relectures independantes de suite l'ont mise en defaut (le `git add` de la meme commande, puis la
forme `-m "$(cat <<'EOF' ...)"` que le decoupeur de commande ne sait pas lire) : changer de methode, pas ajouter
une forme de plus. Le garde juge maintenant le commit REEL, apres coup : ce que le depot dit du dernier commit ne
depend d'aucune lecture de shell. Tests sur de vrais depots git.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "readme-commit-check.py"
HEREDOC = 'git add -A && git commit -m "$(cat <<\'EOF\'\nfeat: x\n\nCorps du message\nEOF\n)"'


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = None
    if date:
        import os
        env = {**os.environ, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _depot(tmp_path: Path, *, readme: bool = True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _ecrire(tmp_path, "src/a.py", "x = 1\n")
    _ecrire(tmp_path, "docker-compose.yml", "services: {}\n")
    _ecrire(tmp_path, "commands/old.sh", "echo old\n")
    if readme:
        _ecrire(tmp_path, "README.md", "# demo\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init", date="2020-01-01T00:00:00")   # ancien : ne compte pas
    return tmp_path


def _ecrire(repo: Path, nom: str, contenu: str = "changed\n") -> None:
    chemin = repo / nom
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


def _commit(repo: Path, **fichiers: str) -> None:
    """Un vrai commit, fait maintenant, avec ces fichiers (nom avec `__` pour `/`)."""
    for nom, contenu in fichiers.items():
        _ecrire(repo, nom.replace("__", "/"), contenu)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")


def _lancer(repo: Path, commande: str = 'git commit -m "feat: x"', cwd: Path | None = None):
    entree = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                         "tool_input": {"command": commande}, "cwd": str(cwd or repo)})
    return subprocess.run([sys.executable, str(HOOK)], input=entree, capture_output=True, text=True,
                          cwd=str(cwd or repo), timeout=30)


def test_refuses_a_commit_that_changed_compose_without_the_readme(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    sortie = _lancer(repo)
    assert sortie.returncode == 2 and "README" in sortie.stderr and "README-OK" in sortie.stderr
    assert "docker-compose.yml" in sortie.stderr


def test_passes_when_the_readme_is_in_the_same_commit(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n", "README.md": "# demo\nlancer avec compose\n"})
    assert _lancer(repo).returncode == 0


def test_the_default_heredoc_commit_form_is_judged_like_any_other(tmp_path):
    """La forme que Claude Code ecrit par defaut : le decoupeur de commande ne la lit pas, le commit reel si."""
    repo = _depot(tmp_path)
    _commit(repo, **{"Dockerfile": "FROM node:20\n"})
    assert _lancer(repo, HEREDOC).returncode == 2


def test_every_way_of_writing_the_command_gives_the_same_verdict(tmp_path):
    commandes = (HEREDOC, "git commit -am x", "(git add Dockerfile && git commit -m x)", "git rm -q old && git commit -m x",
                 "git commit -m x -- Dockerfile", "cd sub && git add . && git commit -m x",
                 "git add -A; git commit -F - <<'EOF'\nx\nEOF")
    for i, commande in enumerate(commandes):
        repo = _depot(tmp_path / f"r{i}")          # un commit neuf par ecriture : chaque commit n'est juge qu'une fois
        _commit(repo, **{"Dockerfile": "FROM node:20\n"})
        assert _lancer(repo, commande).returncode == 2, commande


def test_a_deleted_dockerfile_changes_how_the_project_runs(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, Dockerfile="FROM node:20\n")
    _git(repo, "rm", "-q", "Dockerfile")
    _git(repo, "commit", "-q", "-m", "retire")
    assert _lancer(repo).returncode == 2


def test_a_closed_motif_in_the_command_lets_it_through(tmp_path):
    for i, (motif, attendu) in enumerate((("no-user-visible-change", 0), ("readme-already-current", 0),
                                          ("pas le temps", 2), ("internal-tool", 2))):
        repo = _depot(tmp_path / f"m{i}")
        _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
        assert _lancer(repo, f'git commit -m "x" # README-OK: {motif}').returncode == attendu, motif


def test_a_plain_source_commit_is_not_gated(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"src__a.py": "x = 2\n"})
    assert _lancer(repo).returncode == 0


def test_lockfiles_alone_are_not_gated(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"pnpm-lock.yaml": "lock\n"})
    assert _lancer(repo).returncode == 0


def test_env_example_and_dockerfiles_are_gated(tmp_path):
    for i, nom in enumerate((".env.example", "api__Dockerfile", "api__Dockerfile.prod")):
        repo = _depot(tmp_path / f"d{i}")
        _commit(repo, **{nom: "x\n"})
        assert _lancer(repo).returncode == 2, nom


def test_a_new_command_is_gated_but_editing_an_old_one_is_not(tmp_path):
    repo = _depot(tmp_path / "a")
    _commit(repo, **{"commands__old.sh": "echo changed\n"})
    assert _lancer(repo).returncode == 0
    repo = _depot(tmp_path / "b")
    _commit(repo, **{"commands__new.sh": "echo new\n"})
    assert _lancer(repo).returncode == 2


def test_a_repo_without_a_root_readme_has_nothing_to_update(tmp_path):
    repo = _depot(tmp_path, readme=False)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert _lancer(repo).returncode == 0


def test_a_root_readme_in_lower_case_counts(tmp_path):
    repo = _depot(tmp_path, readme=False)
    _commit(repo, **{"readme.md": "# demo\n"})
    time.sleep(0.01)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n", "readme.md": "# demo\nport\n"})
    assert _lancer(repo).returncode == 0


def test_only_a_commit_made_now_is_judged(tmp_path):
    """Une commande qui n'a pas fait de commit ne juge pas le dernier commit, ancien, qui ne l'a pas respecte."""
    repo = _depot(tmp_path)
    _ecrire(repo, "docker-compose.yml", "services: {old: {}}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ancien", date="2021-01-01T00:00:00")
    assert _lancer(repo, 'git commit -m "rien a commiter"').returncode == 0


def test_a_command_without_git_commit_is_ignored(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    for commande in ("git status", "git log --oneline", "echo 'ce commit change le compose'", "ls"):
        assert _lancer(repo, commande).returncode == 0, commande


def test_a_commit_in_another_repository_is_judged_there(tmp_path):
    ailleurs = tmp_path / "ailleurs"
    ailleurs.mkdir()
    for nom, forme in (("avec-C", 'git -C "{r}" commit -m x'), ("avec-cd", 'cd "{r}" && git commit -m x')):
        repo = _depot(tmp_path / nom)
        _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
        assert _lancer(repo, forme.format(r=repo), cwd=ailleurs).returncode == 2, nom


def test_an_unreadable_situation_does_not_block(tmp_path):
    vide = tmp_path / "pas-un-depot"
    vide.mkdir()
    assert _lancer(vide, 'git commit -m "x"').returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input="pas du json", capture_output=True, text=True,
                          cwd=str(vide), timeout=30).returncode == 0


# --- 3e relecture independante : le jugement porte sur un COMMIT, il ne doit pas etre rejoue par une commande ---

def test_an_excused_commit_is_not_rejudged_by_the_next_command(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert _lancer(repo, 'git commit -m x # README-OK: no-user-visible-change').returncode == 0
    assert _lancer(repo, 'git commit -m "rien a commiter"').returncode == 0
    assert _lancer(repo, "git log --oneline -3 && echo commit").returncode == 0


def test_a_commit_in_another_repository_does_not_rejudge_the_session_repository(tmp_path):
    repo = _depot(tmp_path / "a")
    autre = _depot(tmp_path / "b")
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert _lancer(repo, 'git commit -m x # README-OK: no-user-visible-change').returncode == 0
    _commit(autre, **{"src__a.py": "x = 2\n"})
    assert _lancer(repo, f'git -C "{autre}" commit -m autre', cwd=repo).returncode == 0


def test_a_refusal_is_said_once_per_commit_and_again_for_the_amended_one(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert _lancer(repo).returncode == 2
    assert _lancer(repo, 'git commit -m "rien"').returncode == 0          # deja dit : pas de boucle
    _ecrire(repo, "docker-compose.yml", "services: {web: {}, db: {}}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--amend", "-m", "encore sans README")     # un NOUVEAU commit, toujours fautif
    assert _lancer(repo, "git commit --amend").returncode == 2
    _ecrire(repo, "README.md", "# demo\nport\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--amend", "-m", "avec README")
    assert _lancer(repo, "git commit --amend").returncode == 0


# --- 4e relecture independante (PASS, 5 remarques) -----------------------------------------------------------

def test_the_guard_leaves_no_file_in_the_working_tree_of_a_repo_that_ignores_nothing(tmp_path):
    repo = _depot(tmp_path)                                  # aucun .gitignore
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    _lancer(repo, 'git commit -m x # README-OK: no-user-visible-change')
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert status.strip() == "" and not (repo / ".claude").exists()


def test_it_remembers_several_judged_commits_not_only_the_last(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert _lancer(repo, 'git commit -m x # README-OK: no-user-visible-change').returncode == 0
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, **{"src__a.py": "x = 3\n"})
    assert _lancer(repo, 'git commit -m code').returncode == 0
    _git(repo, "checkout", "-q", "-")
    assert _lancer(repo, 'git commit -m "rien a commiter"').returncode == 0      # le commit excuse n'est pas rejuge


def test_the_refusal_says_an_amended_commit_is_judged_again(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    assert "amended" in _lancer(repo).stderr


def test_a_revert_is_judged_too(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    _lancer(repo, 'git commit -m x # README-OK: no-user-visible-change')   # juge (et excuse) le commit de depart
    _git(repo, "revert", "--no-edit", "HEAD")                              # le retrait du compose, sans README
    assert _lancer(repo, "git revert --no-edit HEAD").returncode == 2


def test_a_cherry_pick_is_judged_too(tmp_path):
    repo = _depot(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat")
    _commit(repo, **{"Dockerfile": "FROM node:20\n"})
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    _git(repo, "checkout", "-q", "-")
    _git(repo, "cherry-pick", sha)
    assert _lancer(repo, f"git cherry-pick {sha}").returncode == 2


def test_the_refusal_says_how_to_correct_without_rewriting_a_pushed_history(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, **{"docker-compose.yml": "services: {web: {}}\n"})
    message = _lancer(repo).stderr
    assert "RECOVERY" in message and "amend" in message and "follow-up" in message
