"""quality/tests-before-commit-check.py — PreToolUse Bash : pas de commit sur des tests rouges dont on n'a pas lu la sortie.

Cas observé (journal Compendium, 2026-11-04) : Takumi commite une suite de tests dont la dernière ligne était une trace
d'erreur, sans avoir lu le résultat ; il l'avoue ensuite (« j'ai commité trop vite »). Retour de Jay : le mandat n'est
pas respecté, Takumi écrit sans vérifier. Le garde refuse un `git commit` quand, dans le tour : (1) la dernière
exécution de tests est rouge ou en erreur et aucune exécution verte ne la suit ; (2) tests et commit sont enchaînés
par `;`, `||` ou un retour à la ligne (le commit part même si les tests échouent). Un commit de documentation
(`docs…`, `chore…`) ne dépend pas des tests. Sortie voulue : `# TESTS-ROUGES-OK: <raison>`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "tests-before-commit-check.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transcript_builder import Journal  # noqa: E402

RED = "FAILED tests/test_x.py::test_a - assert 1 == 2\n1 failed, 40 passed in 2.1s"
GREEN = "41 passed in 2.3s"


def _run(tmp_path: Path, journal: Journal, command: str, **extra):
    path = journal.write_to(tmp_path / "t.jsonl")
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command},
               "transcript_path": path, "session_id": "s", **extra}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=20)


def _commit(msg="feat(x): ajoute y") -> str:
    return f'git commit -m "{msg}"'


def test_a_commit_after_a_red_test_run_is_refused(tmp_path):
    out = _run(tmp_path, Journal().user("go").bash("python3 -m pytest -q", RED), _commit())
    assert out.returncode == 2 and b"tests" in out.stderr


def test_a_commit_after_an_error_without_failure_words_is_refused(tmp_path):
    out = _run(tmp_path, Journal().user("go").bash("pytest -q", "bash: pytest: command not found", True), _commit())
    assert out.returncode == 2


def test_a_green_run_after_the_red_one_lets_the_commit_through(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED).tool("Edit", {"file_path": "/x.py"}, "ok").bash("pytest -q", GREEN)
    assert _run(tmp_path, j, _commit()).returncode == 0


def test_only_the_last_run_counts(tmp_path):
    j = Journal().user("go").bash("pytest -q", GREEN).bash("pytest tests/b -q", RED)
    assert _run(tmp_path, j, _commit()).returncode == 2


def test_no_test_run_in_the_turn_is_not_this_guards_business(tmp_path):
    assert _run(tmp_path, Journal().user("go").bash("ls", "a"), _commit()).returncode == 0


def test_a_red_run_of_a_previous_turn_does_not_count(tmp_path):
    j = Journal().user("ancien tour").bash("pytest -q", RED).user("nouveau tour").bash("ls", "a")
    assert _run(tmp_path, j, _commit()).returncode == 0


def test_tests_chained_with_semicolon_or_newline_to_the_commit_are_refused(tmp_path):
    for cmd in (f"pytest -q ; {_commit()}", f"pytest -q\n{_commit()}", f"pytest -q || {_commit()}", f"cd x && pytest ; {_commit()}"):
        assert _run(tmp_path, Journal().user("go"), cmd).returncode == 2, cmd


def test_tests_chained_with_and_are_fine(tmp_path):
    assert _run(tmp_path, Journal().user("go"), f"pytest -q && {_commit()}").returncode == 0


def test_a_commit_message_that_merely_cites_pytest_is_fine(tmp_path):
    assert _run(tmp_path, Journal().user("go"), _commit("test: ajoute pytest en dépendance")).returncode == 0


def test_a_docs_or_chore_commit_does_not_depend_on_tests(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    for msg in ("docs(session): rapport du jour", "chore(autonomie): nettoyage", "docs: note"):
        assert _run(tmp_path, j, _commit(msg)).returncode == 0, msg


def test_the_explicit_marker_lets_a_red_commit_through(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    assert _run(tmp_path, j, _commit() + "  # TESTS-ROUGES-OK: phase rouge du cycle test d'abord").returncode == 0
    assert _run(tmp_path, j, _commit() + "  # TESTS-ROUGES-OK: x").returncode == 2  # a reason of three words, not a gesture


def test_a_command_that_is_not_a_commit_is_untouched(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    assert _run(tmp_path, j, "git status").returncode == 0
    assert _run(tmp_path, j, "git log --oneline -3").returncode == 0


def test_the_guard_fails_open_on_a_missing_journal_or_garbage(tmp_path):
    assert _run(tmp_path, Journal(), _commit(), transcript_path="").returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"garbage", capture_output=True).returncode == 0


def test_the_message_says_what_to_do(tmp_path):
    out = _run(tmp_path, Journal().user("go").bash("pytest -q", RED), _commit())
    text = out.stderr.decode("utf-8")
    assert "lis la sortie" in text.lower() and "TESTS-ROUGES-OK" in text


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/tests-before-commit-check.py" in settings


def test_a_pipe_that_hides_the_exit_code_of_the_tests_is_refused(tmp_path):
    for cmd in (f"pytest -q | tail -3 && {_commit()}", f"python3 -m pytest -q 2>&1 | tail -1 && {_commit()}"):
        assert _run(tmp_path, Journal().user("go"), cmd).returncode == 2, cmd


# --- relecture 1 (FAIL) : faux refus de gestes imposés par la méthode, et manques --------------------------------------


MUTATION = "commit non reconnu -> 1 failed, 47 passed\nréel -> 48 passed\n232 passed in 8s"


def test_a_mutation_script_whose_last_summary_is_green_does_not_block_the_commit(tmp_path):
    assert _run(tmp_path, Journal().user("go").bash("python3 - <<EOF\nmutants\nEOF\npytest -q", MUTATION), _commit()).returncode == 0


def test_a_commit_subject_citing_FAIL_does_not_make_the_next_commit_red(tmp_path):
    j = Journal().user("go").bash('pytest -q && git commit -q -m "fix: garde (relecture FAIL)"', "41 passed in 2s\n[main abc] fix: garde (relecture FAIL)")
    assert _run(tmp_path, j, _commit()).returncode == 0


def test_a_green_run_through_another_form_after_a_red_one_clears_it(tmp_path):
    for green_cmd in ("uv run pytest -q", "PYTHONPATH=src pytest", "scripts/ci-local.sh", "timeout 300 pytest"):
        j = Journal().user("go").bash("pytest -q", RED).bash(green_cmd, GREEN)
        assert _run(tmp_path, j, _commit()).returncode == 0, green_cmd


def test_and_and_across_lines_or_with_a_continuation_is_a_safe_chain(tmp_path):
    for cmd in (f"cd x &&\n pytest -q &&\n {_commit()}", f"pytest -q && \\\n {_commit()}", f"set -e; pytest -q; {_commit()}",
                f"if pytest -q; then {_commit()}; fi"):
        assert _run(tmp_path, Journal().user("go"), cmd).returncode == 0, cmd


def test_the_subject_is_read_from_the_commit_not_from_an_earlier_heredoc_or_dash_m(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    before = "cat > r.md <<'EOF'\n# Rapport\nEOF\npython3 -m pytest -m \"not slow\" -q ; true\n"
    assert _run(tmp_path, j, before + "git commit -q -F - <<'EOF'\ndocs(session): rapport\n\nCorps\nEOF").returncode == 0
    assert _run(tmp_path, j, "git commit -am \"docs: note\"").returncode == 0
    assert _run(tmp_path, j, before + "git commit -q -F - <<'EOF'\nfeat(x): y\nEOF").returncode == 2


def test_test_words_inside_a_written_file_are_not_a_chain(tmp_path):
    cmd = "cat > notes.md <<'EOF'\nlance pytest -q puis plus tard\nEOF\ngit commit -q -m \"feat(x): note\""
    assert _run(tmp_path, Journal().user("go"), cmd).returncode == 0


def test_tests_run_inside_the_commit_command_itself_are_the_current_run(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED).bash("pytest -q && git commit -m x", "")
    assert _run(tmp_path, j, "pytest -q && git commit -m x").returncode == 0


def test_the_words_git_commit_inside_a_script_that_writes_a_file_are_not_a_commit(tmp_path):
    """Rejeu du vrai journal : 10 faux refus venaient de scripts qui citaient « git commit » dans leur texte."""
    j = Journal().user("go").bash("pytest -q", RED)
    script = "python3 - <<'EOF'\nprint('exemple : pytest -q ; git commit -m x')\nEOF"
    assert _run(tmp_path, j, script).returncode == 0
    assert _run(tmp_path, j, "cat >> notes.md <<'EOF'\nvoici git commit -m \"feat\"\nEOF").returncode == 0


def test_a_real_commit_after_a_script_that_cites_one_is_still_judged(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    script = "python3 - <<'EOF'\nprint('git commit -m docs')\nEOF\ngit commit -q -m \"feat(x): y\""
    assert _run(tmp_path, j, script).returncode == 2


def test_a_test_line_inside_a_written_file_followed_by_a_separator_is_not_a_chain(tmp_path):
    cmd = "cat > run.sh <<'EOF'\npytest -q ; echo fini\nEOF\ngit commit -q -m \"feat(x): script\""
    assert _run(tmp_path, Journal().user("go"), cmd).returncode == 0


def test_the_pending_commit_call_is_not_counted_as_a_green_test_run(tmp_path):
    """Le journal contient déjà l'appel en cours (sans résultat) quand le crochet lit : il ne doit pas masquer un rouge."""
    red = Journal().user("go").bash("pytest -q", RED)
    red.entries.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "cur", "name": "Bash",
                        "input": {"command": 'git commit -q -m "feat(x): y (pytest -q ; vert)"'}}]}})
    assert _run(tmp_path, red, 'git commit -q -m "feat(x): y (pytest -q ; vert)"').returncode == 2


def test_tests_chained_with_and_in_the_same_command_cover_the_commit_even_after_a_red_run(tmp_path):
    j = Journal().user("go").bash("pytest -q", RED)
    assert _run(tmp_path, j, f"pytest -q && {_commit()}").returncode == 0
