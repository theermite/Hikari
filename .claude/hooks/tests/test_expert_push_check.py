"""expert-push-check.py — un commit sensible ou critique ne quitte pas la machine sans qu'un expert ait été lancé.

Pourquoi (Jay 2026-11-01) : 27 agents sur 32 n'étaient lancés dans aucun projet ; leurs noms n'étaient écrits que dans des
textes de commandes que personne ne tape. Le seul agent appelé en continu est celui qu'un garde-fou EXIGE. Ce garde juge
les commits réellement non poussés (git, pas la commande) et vérifie le journal des lancements d'agents.
Tests sur de vrais dépôts git, avec un dépôt distant.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "expert-push-check.py"
LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))

import agent_wiring  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return done.stdout


def _ecrire(repo: Path, nom: str, contenu: str = "x = 1\n") -> None:
    chemin = repo / nom
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


def _depot(tmp_path: Path) -> Path:
    """Un dépôt de travail dont la tête est déjà poussée vers un dépôt distant nu."""
    distant = tmp_path / "distant.git"
    travail = tmp_path / "travail"
    subprocess.run(["git", "init", "-q", "--bare", str(distant)], check=True, capture_output=True)
    travail.mkdir()
    _git(travail, "init", "-q", "-b", "main")
    _git(travail, "config", "user.email", "t@t")
    _git(travail, "config", "user.name", "t")
    _ecrire(travail, "src/a.py")
    _git(travail, "add", "-A")
    _git(travail, "commit", "-q", "-m", "init")
    _git(travail, "remote", "add", "origin", str(distant))
    _git(travail, "push", "-q", "-u", "origin", "main")
    return travail


def _commit(repo: Path, **fichiers: str) -> str:
    for nom, contenu in fichiers.items():
        _ecrire(repo, nom.replace("__", "/"), contenu)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    return _git(repo, "rev-parse", "HEAD").strip()


def _journal(repo: Path, *lancements: tuple[str, int]) -> None:
    """Chaque lancement : (agent, âge en minutes). Journal du dépôt, comme le hook de suivi des agents."""
    dossier = repo / ".claude" / "state"
    dossier.mkdir(parents=True, exist_ok=True)
    maintenant = datetime.now().astimezone()
    lignes = [json.dumps({"event": "SubagentStart", "agent": a, "at": (maintenant - timedelta(minutes=m)).isoformat()})
              for a, m in lancements]
    (dossier / "agent-invocations.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _lancer(repo: Path, commande: str = "git push"):
    entree = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(repo),
                         "tool_input": {"command": commande}})
    return subprocess.run([sys.executable, str(HOOK)], input=entree, capture_output=True, text=True, cwd=str(repo))


# ---------------------------------------------------------------- le registre

def test_a_payment_path_requires_the_payment_expert():
    assert agent_wiring.experts_for(["src/payment/webhook.ex"]) == {"Payment Master"}


def test_a_migration_requires_the_database_expert():
    assert agent_wiring.experts_for(["priv/repo/migrations/20261101_x.exs"]) == {"Database Master"}


def test_an_auth_path_requires_the_security_expert():
    assert agent_wiring.experts_for(["app/auth/session.ts"]) == {"Security Master"}


def test_rust_needs_an_expert_only_when_the_diff_adds_unsafe():
    assert agent_wiring.experts_for(["native/lib.rs"], diff="+fn safe() {}\n") == set()
    assert agent_wiring.experts_for(["native/lib.rs"], diff="+unsafe { *p = 1 }\n") == {"Rust Systems Master"}


def test_a_test_file_never_requires_an_expert():
    assert agent_wiring.experts_for(["tests/payment/test_webhook.py", "src/auth/session.test.ts"]) == set()


def test_ordinary_files_require_nothing():
    assert agent_wiring.experts_for(["src/a.py", "README.md", "docs/x.md"]) == set()


# ---------------------------------------------------------------- le garde sur de vrais dépôts

def test_push_without_sensitive_commits_passes(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__b="y = 2\n")
    assert _lancer(repo).returncode == 0


def test_push_of_a_payment_commit_without_the_expert_is_refused(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    fait = _lancer(repo)
    assert fait.returncode == 2 and "Payment Master" in fait.stderr and "EXPERT-OK" in fait.stderr


def test_push_passes_once_the_expert_was_launched_after_the_commit(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    _journal(repo, ("Payment Master", 0))
    assert _lancer(repo).returncode == 0


def test_an_expert_launched_long_before_the_commit_does_not_count(tmp_path):
    repo = _depot(tmp_path)
    _journal(repo, ("Payment Master", 600))
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo).returncode == 2


def test_the_wrong_expert_does_not_count(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    _journal(repo, ("Veille Master", 0))
    assert _lancer(repo).returncode == 2


def test_the_closed_list_of_excuses_lets_it_pass(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git push # EXPERT-OK: docs-only").returncode == 0


def test_an_excuse_outside_the_closed_list_is_refused(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git push # EXPERT-OK: because").returncode == 2


def test_a_command_that_is_not_a_push_is_ignored(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git status").returncode == 0
    assert _lancer(repo, 'echo "git push"').returncode == 0


def test_a_commit_message_quoting_a_push_is_not_a_push(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, 'git commit -m "docs: explain git push"').returncode == 0


def test_a_push_chained_after_other_commands_is_still_judged(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git add -A && git commit -m x; git push origin main").returncode == 2


def test_already_pushed_sensitive_commits_are_not_judged_again(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    _git(repo, "push", "-q")
    assert _lancer(repo).returncode == 0


def test_a_repository_without_upstream_judges_what_no_remote_holds(tmp_path):
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git push -u origin main").returncode == 2


def test_a_folder_that_is_not_a_repository_passes(tmp_path):
    dossier = tmp_path / "pas-un-depot"
    dossier.mkdir()
    assert _lancer(dossier).returncode == 0


# ---------------------------------------------------------------- remarques de la relecture indépendante (2026-11-01)

def _commit_ancien(repo: Path, minutes: int, **fichiers: str) -> None:
    import os
    date = (datetime.now().astimezone() - timedelta(minutes=minutes)).isoformat()
    for nom, contenu in fichiers.items():
        _ecrire(repo, nom.replace("__", "/"), contenu)
    _git(repo, "add", "-A")
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "change"], check=True, capture_output=True, env=env)


def test_an_amend_after_the_expert_ran_does_not_cancel_the_expert(tmp_path):
    """Remarque 1 : amend et rebase remettent l'heure du commiteur à maintenant ; l'heure d'auteur reste."""
    repo = _depot(tmp_path)
    _commit_ancien(repo, 180, src__payment__hook="p = 1\n")
    _journal(repo, ("Payment Master", 150))
    assert _lancer(repo).returncode == 0
    _git(repo, "commit", "-q", "--amend", "--no-edit")
    assert _lancer(repo).returncode == 0


def test_the_repository_named_with_dash_C_is_the_one_judged(tmp_path):
    """Remarque 2 : le dépôt jugé est celui qu'on pousse, pas celui du dossier courant."""
    propre = _depot(tmp_path / "a")
    sensible = _depot(tmp_path / "b")
    _commit(sensible, src__payment__hook="p = 1\n")
    assert _lancer(propre, f'git -C "{sensible}" push').returncode == 2


def test_a_cd_before_the_push_changes_the_repository_judged(tmp_path):
    propre = _depot(tmp_path / "a")
    sensible = _depot(tmp_path / "b")
    _commit(sensible, src__payment__hook="p = 1\n")
    assert _lancer(propre, f'cd "{sensible}" && git push').returncode == 2


def test_a_dash_C_to_a_clean_repository_ignores_the_sensitive_current_one(tmp_path):
    propre = _depot(tmp_path / "a")
    sensible = _depot(tmp_path / "b")
    _commit(sensible, src__payment__hook="p = 1\n")
    assert _lancer(sensible, f'git -C "{propre}" push').returncode == 0


def test_real_paths_the_first_registry_missed_are_caught_and_ordinary_ones_are_not():
    assert agent_wiring.experts_for(["src/login.ts"]) == {"Security Master"}
    assert agent_wiring.experts_for(["src/middleware/authenticate.ts"]) == {"Security Master"}
    assert agent_wiring.experts_for(["db/schema.prisma"]) == {"Database Master"}
    assert agent_wiring.experts_for(["src/author.py", "lib/secret_store.py"]) == set()
    assert agent_wiring.experts_for(["docs/auth-flow.md", ".claude/agents/payment-master.md"]) == set()


def test_wrapped_push_forms_are_still_pushes(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    for forme in ("command git push", "env GIT_X=1 git push", "(git push)", "git --no-pager push", "GIT_SSH_COMMAND=ssh git push"):
        assert _lancer(repo, forme).returncode == 2, forme


def test_a_dry_run_or_a_branch_deletion_ships_nothing(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, "git push --dry-run").returncode == 0
    assert _lancer(repo, "git push origin --delete old-branch").returncode == 0


def test_an_excuse_quoted_in_a_message_is_not_an_excuse(tmp_path):
    repo = _depot(tmp_path)
    _commit(repo, src__payment__hook="p = 1\n")
    assert _lancer(repo, 'git commit -m "# EXPERT-OK: docs-only" && git push').returncode == 2
