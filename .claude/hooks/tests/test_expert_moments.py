"""expert-moment-reminder.py — les experts qui n'ont pas de fichier à eux sont rappelés au bon MOMENT : commit, mise en ligne.

Reprise Kata 7.8.0 : 27 agents sur 32 n'étaient lancés nulle part. Les experts de matière (Elixir, interface…) sont rappelés
par le fichier qu'on touche ; ceux du contrôle (qualité du code, tests, sécurité, débogage, refonte, déploiement…) n'ont
pas de fichier : leur déclencheur est un geste. Rappel seulement (jamais de blocage), tracé dans le même journal que les
rappels par fichier, donc mesuré chaque semaine par le garde hebdomadaire.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "expert-moment-reminder.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import agent_moments  # noqa: E402
from agent_wiring import load_registry  # noqa: E402

REG = load_registry()


# ---------------------------------------------------------------- la logique pure

def _agents(found) -> set[str]:
    return {agent for agent, _ in found}


def test_a_big_commit_reminds_code_quality():
    files = [f"src/m{i}.py" for i in range(6)]
    assert "Code Quality Master" in _agents(agent_moments.commit_moments(files, "feat", set(), REG))


def test_a_small_commit_reminds_nobody():
    assert agent_moments.commit_moments(["src/a.py"], "feat", set(), REG) == []


def test_a_commit_with_tests_and_code_reminds_the_test_auditor():
    assert "Test Auditor Master" in _agents(agent_moments.commit_moments(["src/a.py", "tests/test_a.py"], "feat", set(), REG))


def test_a_refactor_commit_reminds_the_refactor_expert():
    assert "Refactor Safe Master" in _agents(agent_moments.commit_moments(["src/a.py"], "refactor", set(), REG))


def test_a_second_fix_on_the_same_file_reminds_debug_rebuild_and_research():
    found = _agents(agent_moments.commit_moments(["src/a.py"], "fix", {"src/a.py"}, REG))
    assert {"Debug Investigator Master", "Rebuild Arbiter Master", "Deep Research Master"} <= found


def test_a_first_fix_reminds_nobody():
    assert agent_moments.commit_moments(["src/a.py"], "fix", set(), REG) == []


def test_documents_alone_remind_nobody():
    files = [f"docs/n{i}.md" for i in range(8)]
    assert agent_moments.commit_moments(files, "docs", set(), REG) == []


def test_a_deploy_reminds_security_compliance_performance_deploy_and_monitoring():
    found = _agents(agent_moments.deploy_moments(REG))
    assert {"Security Master", "Compliance Auditor Master", "Performance Master", "Build Deploy Test Master",
            "Monitoring Master"} <= found


HEREDOC = "git commit -m \"$(cat <<'EOF'\nfix(garde): le cd relatif\n\nCorps du message.\nEOF\n)\""


def _kind(command: str):
    found = agent_moments.parse_commit(command)
    return None if found is None else found["kind"]


def test_the_commit_type_is_read_from_the_message():
    assert _kind('git commit -m "fix(guard): le cd relatif"') == "fix"
    assert _kind('git commit -m "Refactor!: x"') == "refactor"
    assert _kind('git commit -m "mise à jour"') is None


def test_the_usual_heredoc_commit_is_seen():
    """La forme la plus courante de Claude Code : 55 commits sur 92 dans trois jours de journaux."""
    assert _kind(HEREDOC) == "fix"


def test_options_before_the_subcommand_are_skipped():
    assert _kind('git -C D:/x commit -m "fix: y"') == "fix"
    assert agent_moments.parse_commit('git -C D:/x commit -m "fix: y"')["directory"] == "D:/x"
    assert _kind('git -c user.name=a commit -m "feat: z"') == "feat"


def test_wrappers_before_git_are_skipped():
    assert _kind('sudo -u x git commit -m "refactor: a"') == "refactor"
    assert _kind('GIT_AUTHOR_NAME=a env git commit -m "fix: b"') == "fix"
    assert _kind('cd x && git add . && git commit -m "feat: c"') == "feat"


def test_short_and_long_message_forms_are_read():
    assert _kind('git commit -am "fix: z"') == "fix"
    assert agent_moments.parse_commit('git commit -am "fix: z"')["everything"] is True
    assert _kind('git commit --message="refactor: a"') == "refactor"
    assert agent_moments.parse_commit('git commit -m "fix: z"')["everything"] is False


def test_a_commit_without_a_conventional_message_is_still_a_commit():
    found = agent_moments.parse_commit("git commit")
    assert found is not None and found["kind"] is None


def test_words_that_only_mention_a_commit_are_not_commits():
    for command in ('echo "git commit -m x"', 'grep "git commit" notes.txt', "git status", "git log --oneline",
                    "git commit-tree abc", "ls git-commit.txt"):
        assert agent_moments.parse_commit(command) is None, command


# ---------------------------------------------------------------- le hook sur un vrai dépôt

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True)


def _depot(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


def _lancer(repo: Path, commande: str, session: str = "s1"):
    entree = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": session, "cwd": str(repo),
                         "tool_input": {"command": commande}})
    return subprocess.run([sys.executable, str(HOOK)], input=entree, capture_output=True, text=True, cwd=str(repo))


def _contexte(fait) -> str:
    return json.loads(fait.stdout)["hookSpecificOutput"]["additionalContext"] if fait.stdout.strip() else ""


def _rappels(repo: Path) -> list[dict]:
    chemin = repo / ".claude" / "state" / "expert-reminders.jsonl"
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines()] if chemin.exists() else []


def _stage(repo: Path, noms: list[str]) -> None:
    for nom in noms:
        (repo / nom).parent.mkdir(parents=True, exist_ok=True)
        (repo / nom).write_text(f"contenu {nom}\n", encoding="utf-8")
    _git(repo, "add", "--", *noms)


def test_committing_many_files_reminds_and_leaves_a_trace(tmp_path):
    repo = _depot(tmp_path)
    _stage(repo, [f"src/m{i}.py" for i in range(6)])
    fait = _lancer(repo, 'git commit -m "feat: beaucoup"')
    assert fait.returncode == 0 and "Code Quality Master" in _contexte(fait)
    assert [t["agent"] for t in _rappels(repo)] == ["Code Quality Master"]


def test_the_reminder_never_blocks_and_comes_once_per_session(tmp_path):
    repo = _depot(tmp_path)
    _stage(repo, [f"src/m{i}.py" for i in range(6)])
    assert _contexte(_lancer(repo, 'git commit -m "feat: a"')) != ""
    assert _contexte(_lancer(repo, 'git commit -m "feat: b"')) == ""
    assert _contexte(_lancer(repo, 'git commit -m "feat: c"', session="s2")) != ""


def test_a_second_fix_on_the_same_file_is_seen_in_git_history(tmp_path):
    repo = _depot(tmp_path)
    _stage(repo, ["src/a.py"])
    _git(repo, "commit", "-qm", "fix: première correction")
    (repo / "src/a.py").write_text("autre contenu\n", encoding="utf-8")
    _git(repo, "add", "--", "src/a.py")
    contexte = _contexte(_lancer(repo, 'git commit -m "fix: deuxième correction"'))
    assert "Debug Investigator Master" in contexte and "Rebuild Arbiter Master" in contexte


def test_a_deploy_command_reminds_the_deploy_experts(tmp_path):
    repo = _depot(tmp_path)
    contexte = _contexte(_lancer(repo, "docker compose up -d"))
    assert "Security Master" in contexte and "Build Deploy Test Master" in contexte


def test_other_commands_say_nothing(tmp_path):
    repo = _depot(tmp_path)
    for commande in ("git status", "ls -la", "git log --oneline -3", "grep deploy README.md"):
        fait = _lancer(repo, commande)
        assert fait.returncode == 0 and fait.stdout.strip() == ""


def test_outside_a_repository_nothing_is_written(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    _lancer(plain, "docker compose up -d")
    assert not (plain / ".claude").exists()


def test_a_heredoc_commit_reminds_in_a_real_repository(tmp_path):
    repo = _depot(tmp_path)
    _stage(repo, [f"src/m{i}.py" for i in range(6)])
    contexte = _contexte(_lancer(repo, "git commit -m \"$(cat <<'EOF'\nfeat: beaucoup\n\nCorps.\nEOF\n)\""))
    assert "Code Quality Master" in contexte


def test_git_dash_c_judges_the_named_repository(tmp_path):
    ailleurs = _depot(tmp_path / "ailleurs")
    _stage(ailleurs, [f"src/m{i}.py" for i in range(6)])
    ici = _depot(tmp_path / "ici")
    contexte = _contexte(_lancer(ici, f'git -C "{ailleurs}" commit -m "feat: x"'))
    assert "Code Quality Master" in contexte


def test_a_commit_line_inside_another_tools_heredoc_is_not_a_commit():
    """Relecture 2026-11-02 : le corps d'un heredoc d'un autre outil n'est pas une commande."""
    for command in ("python - <<'EOF'\nprint(1)\ngit commit -m 'fix: x'\nEOF",
                    "cat > f.sh <<EOF\ngit commit -m \"fix: y\"\nEOF",
                    "gh pr create --body \"$(cat <<EOF\nrun:\ngit commit -m 'fix: zz'\nEOF\n)\""):
        assert agent_moments.parse_commit(command) is None, command


def test_a_dash_a_inside_the_message_or_after_the_commit_is_not_the_all_flag():
    assert agent_moments.parse_commit('git commit -m "docs: mention -a flag"')["everything"] is False
    assert agent_moments.parse_commit('git commit -m "chore: x"; git push -a')["everything"] is False
    assert agent_moments.parse_commit('git commit -a -m "chore: x"')["everything"] is True


def test_a_message_glued_to_dash_m_is_read():
    assert _kind('git commit -m"fix: collé"') == "fix"


def test_a_note_that_only_quotes_a_deploy_command_is_not_a_deploy(tmp_path):
    """Constaté le 2026-11-02 : un fichier de test écrit par `cat > f <<EOF` et citant `docker compose up` déclenchait le rappel."""
    repo = _depot(tmp_path)
    commande = "cat > notes.txt <<'EOF'\ndocker compose up -d\nEOF"
    fait = _lancer(repo, commande)
    assert fait.returncode == 0 and fait.stdout.strip() == ""
