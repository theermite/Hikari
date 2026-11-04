"""lib/turn_log.py — lire le tour en cours dans le journal de séance : appels d'outil appariés à leur résultat.

Piège connu (garde `logs-first`) : un résultat d'outil est une entrée « user » du journal ; seul un VRAI message de
Jay (texte, sans résultat d'outil) ouvre un nouveau tour.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import turn_log as tl  # noqa: E402
from transcript_builder import Journal  # noqa: E402


def _runs(journal: Journal, tmp_path: Path):
    return tl.tool_runs(journal.write_to(tmp_path / "t.jsonl"))


def test_runs_are_paired_with_their_result_in_order(tmp_path):
    j = Journal().user("fais le travail").bash("ls", "a b").tool("Read", {"file_path": "/x"}, "contenu").bash("pytest", "boum", True)
    runs = _runs(j, tmp_path)
    assert [(r.name, r.output, r.is_error) for r in runs] == [("Bash", "a b", False), ("Read", "contenu", False), ("Bash", "boum", True)]
    assert runs[0].command == "ls" and runs[1].command == ""


def test_only_the_current_turn_is_read(tmp_path):
    j = Journal().user("tour 1").bash("old", "x").user("tour 2").bash("new", "y")
    assert [r.command for r in _runs(j, tmp_path)] == ["new"]


def test_a_tool_result_does_not_open_a_new_turn(tmp_path):
    j = Journal().user("tour").bash("a", "1").bash("b", "2").bash("c", "3")
    assert [r.command for r in _runs(j, tmp_path)] == ["a", "b", "c"]


def test_a_user_message_with_a_text_block_list_opens_a_turn(tmp_path):
    j = Journal().bash("old", "x")
    j.entries.append({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "nouveau tour"}]}})
    j.bash("new", "y")
    assert [r.command for r in _runs(j, tmp_path)] == ["new"]


def test_a_result_made_of_blocks_is_flattened_to_text(tmp_path):
    j = Journal().user("t")
    j.entries.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "z", "name": "Bash", "input": {"command": "c"}}]}})
    j.entries.append({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "z", "content": [{"type": "text", "text": "ligne 1"}, {"type": "text", "text": "ligne 2"}]}]}})
    assert _runs(j, tmp_path)[0].output == "ligne 1\nligne 2"


def test_a_call_without_a_result_yet_is_kept_with_an_empty_output(tmp_path):
    j = Journal().user("t")
    j.entries.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "q", "name": "Bash", "input": {"command": "pending"}}]}})
    runs = _runs(j, tmp_path)
    assert runs[0].command == "pending" and runs[0].output == "" and runs[0].is_error is False


def test_a_missing_or_broken_journal_gives_no_runs(tmp_path):
    assert tl.tool_runs(str(tmp_path / "absent.jsonl")) == []
    (tmp_path / "bad.jsonl").write_text("pas du json\n{\n", encoding="utf-8")
    assert tl.tool_runs(str(tmp_path / "bad.jsonl")) == []
    assert tl.tool_runs("") == []


def test_test_runs_are_recognised_by_their_command():
    for cmd in ("python3 -m pytest tests -q", "pytest -x", "mix test", "cd web && pnpm test", "npm run test", "cargo test --all",
                "go test ./...", "vitest run", "make test", "mix coveralls"):
        assert tl.is_test_command(cmd), cmd
    for cmd in ("ls tests", "git commit -m 'add pytest'", "echo pytest", "cat test_x.py", "pip install pytest"):
        assert not tl.is_test_command(cmd), cmd


def test_red_output_is_recognised_and_green_output_is_not():
    for out in ("3 failed, 40 passed in 2s", "FAILED tests/x.py::t - assert 1 == 2", "Traceback (most recent call last):\n  File",
                "== 1 error in 0.1s ==", "Tests: 2 failed, 5 passed", "1) test addition (M.Test)\n  1 failure", "error: could not compile"):
        assert tl.looks_red(out), out
    for out in ("40 passed in 2s", "0 failures, 12 tests", "Tests: 7 passed", "ok", "", "0 failed, 5 passed"):
        assert not tl.looks_red(out), out


def test_a_tool_result_carrying_an_extra_text_block_does_not_open_a_turn(tmp_path):
    """Un crochet peut ajouter un bloc texte à côté du résultat d'outil : ce n'est pas un message de Jay."""
    j = Journal().user("tour").bash("a", "1")
    j.entries[-1]["message"]["content"].append({"type": "text", "text": "contexte ajouté par un crochet"})
    j.bash("b", "2")
    assert [r.command for r in _runs(j, tmp_path)] == ["a", "b"]


# --- relecture 1 (FAIL) : le verdict est la DERNIÈRE ligne de résumé, pas les mots rouges de toute la sortie ----------


def test_the_last_summary_line_decides_not_the_earlier_red_words():
    mutation = "commit non reconnu -> 1 failed, 47 passed in 1.5s\nréel -> 48 passed in 1.4s\n232 passed in 8.5s"
    assert not tl.looks_red(mutation)
    assert tl.looks_red("232 passed in 8.5s\nautre suite\n3 failed, 10 passed in 1s")


def test_a_full_pytest_output_is_judged_by_its_final_line():
    red = "FAILED tests/a.py::t - assert 1 == 2\nE   assert 1 == 2\n=== 1 failed, 40 passed in 2.1s ==="
    green = "tests/a.py ....\n=== 41 passed, 2 skipped in 2.1s ==="
    assert tl.looks_red(red) and not tl.looks_red(green)


def test_other_runners_summaries():
    assert not tl.looks_red("test result: ok. 12 passed; 0 failed; 0 ignored")
    assert tl.looks_red("test result: FAILED. 11 passed; 1 failed; 0 ignored")
    assert not tl.looks_red("ok  \tgithub.com/x/y\t0.012s")
    assert tl.looks_red("FAIL\tgithub.com/x/y\t0.012s")
    assert not tl.looks_red("Test Files  3 passed (3)\n     Tests  21 passed (21)")
    assert tl.looks_red("Tests:       1 failed, 20 passed, 21 total")
    assert not tl.looks_red("Finished in 0.5 seconds\n12 tests, 0 failures")
    assert tl.looks_red("Finished in 0.5 seconds\n12 tests, 2 failures")


def test_a_commit_line_that_cites_FAIL_is_not_a_red_run():
    assert not tl.looks_red("41 passed in 2s\n[main abc1234] fix(hooks): garde (relecture FAIL)")


def test_an_error_flag_with_no_summary_is_red_but_with_a_green_summary_it_is_not():
    assert tl.looks_red("bash: pytest: command not found", is_error=True)
    assert not tl.looks_red("41 passed in 2s", is_error=True)  # the failing part was another command


def test_meta_messages_do_not_open_a_turn(tmp_path):
    j = Journal().user("tour").bash("a", "1")
    j.entries.append({"type": "user", "isMeta": True, "message": {"role": "user", "content": "Stop hook feedback: pousse"}})
    j.entries.append({"type": "user", "message": {"role": "user", "content": "[SYSTEM NOTIFICATION - NOT USER INPUT]\nsubagent finished"}})
    j.entries.append({"type": "user", "message": {"role": "user", "content": "Another Claude session sent a message:\n<agent-message>"}})
    j.bash("b", "2")
    assert [r.command for r in _runs(j, tmp_path)] == ["a", "b"]


def test_more_forms_of_a_test_command():
    for cmd in ("PYTHONPATH=. pytest -q", "MIX_ENV=test mix coveralls", "timeout 300 pytest", "uv run pytest", "npx vitest run",
                "scripts/ci-local.sh", "cd x && MIX_ENV=test mix test", "python3 -m pytest .claude/hooks/tests -q -p no:cacheprovider"):
        assert tl.is_test_command(cmd), cmd


def test_labelled_probe_lines_with_an_arrow_are_not_the_verdict():
    """Les scripts de mutation affichent « nom -> N failed » exprès : la dernière ligne peut être rouge sans que la suite le soit."""
    out = "20 passed in 2.03s\nmutant -> 1 failed, 19 passed in 2.13s\n249 lib/run_resume.py"
    assert not tl.looks_red(out)
    assert not tl.looks_red("réel -> 19 passed in 1.7s\nordre non exigé -> 1 failed, 18 passed in 1.7s")
    assert tl.looks_red("mutant -> 1 failed, 19 passed\n3 failed, 10 passed in 1s")


def test_an_entry_flagged_meta_never_opens_a_turn_whatever_its_text(tmp_path):
    j = Journal().user("tour").bash("a", "1")
    j.entries.append({"type": "user", "isMeta": True, "message": {"role": "user", "content": "texte quelconque sans préfixe connu"}})
    j.bash("b", "2")
    assert [r.command for r in _runs(j, tmp_path)] == ["a", "b"]
