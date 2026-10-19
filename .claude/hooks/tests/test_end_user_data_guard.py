"""Tests for guards/end-user-data-guard.py and lib/end_user_identifiers.py.

Why this guard exists (2026-10-10, Shizen). The pseudo of a real end user, given
by Jay in conversation for a yes/no check, was copied into a published planning
document by Takumi. The Confidentiality rule (Gate C) forbade it in writing; the
writing did not hold. Jay: "vraiment, énormément agaçant". A rule that depends on
remembering it fails at the most ordinary moment — drafting a document — so the
gate is now code.

What it does: identifiers of end users (usernames, e-mail local parts, names)
are stored OUTSIDE every repository as salted SHA-256 fingerprints, never in
clear. Before a Write/Edit/MultiEdit, and before a `git commit` (message + added
lines), every word and every pair of words is fingerprinted and compared. A match
blocks, and the message never repeats the matched word.

These tests run the hook as a subprocess with the real payload shape: a unit
test on a helper cannot catch a guard that dies before calling it (write-guard,
2026-08-07). All identifiers below are fabricated.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
GUARD = HOOKS / "guards" / "end-user-data-guard.py"
LIB = HOOKS / "lib" / "end_user_identifiers.py"


def _env(store: Path) -> dict:
    env = dict(os.environ)
    env["EUI_STORE_DIR"] = str(store)
    return env


def _cli(store: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LIB), *args], input=stdin, capture_output=True, text=True, env=_env(store)
    )


def _guard(store: Path, payload: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(store),
        cwd=str(cwd) if cwd else None,
    )


def _write(path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def _seed(store: Path, *values: str) -> None:
    result = _cli(store, "rebuild", stdin="\n".join(values) + "\n")
    assert result.returncode == 0, result.stderr


# --- the store -------------------------------------------------------------


def test_store_never_contains_a_value_in_clear(tmp_path):
    _seed(tmp_path, "Zorvexa", "Quillamir Brandoux", "zorvexa.fake@example.invalid")
    blob = "".join(p.read_text(encoding="utf-8") for p in tmp_path.iterdir()).lower()
    for clear in ("zorvexa", "quillamir", "brandoux", "example"):
        assert clear not in blob


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no POSIX file modes; the 0600 promise is proven on the VPS (Linux)")
def test_store_files_are_private(tmp_path):
    _seed(tmp_path, "Zorvexa")
    for p in tmp_path.iterdir():
        assert oct(p.stat().st_mode & 0o777) == "0o600", p.name


def test_rebuild_replaces_and_add_appends(tmp_path):
    _seed(tmp_path, "Zorvexa")
    _cli(tmp_path, "add", stdin="Quillamir\n")
    assert _guard(tmp_path, _write("/r/doc.md", "Zorvexa")).returncode == 2
    assert _guard(tmp_path, _write("/r/doc.md", "Quillamir")).returncode == 2
    _seed(tmp_path, "Brandoux")
    # A rebuild replaces the database-derived list but keeps manual additions.
    assert _guard(tmp_path, _write("/r/doc.md", "Zorvexa")).returncode == 0
    assert _guard(tmp_path, _write("/r/doc.md", "Quillamir")).returncode == 2


def test_check_command_answers_without_echoing(tmp_path):
    _seed(tmp_path, "Zorvexa")
    result = _cli(tmp_path, "check", stdin="Zorvexa\n")
    assert result.returncode == 1
    assert "zorvexa" not in (result.stdout + result.stderr).lower()
    assert _cli(tmp_path, "check", stdin="Personne\n").returncode == 0


# --- the guard on Write / Edit / MultiEdit -----------------------------------


def test_blocks_a_username_in_a_document(tmp_path):
    _seed(tmp_path, "Zorvexa")
    result = _guard(tmp_path, _write("/repo/docs/PET.md", "Prévenir Zorvexa avant la bascule."))
    assert result.returncode == 2
    assert "zorvexa" not in result.stderr.lower()
    assert "utilisateur" in result.stderr.lower()


def test_match_ignores_case_and_accents(tmp_path):
    _seed(tmp_path, "Éloïse")
    assert _guard(tmp_path, _write("/r/a.md", "eloise a écrit")).returncode == 2
    assert _guard(tmp_path, _write("/r/a.md", "ELOÏSE")).returncode == 2


def test_blocks_a_full_name_written_as_two_words(tmp_path):
    _seed(tmp_path, "Quillamir Brandoux")
    assert _guard(tmp_path, _write("/r/a.md", "contact : Quillamir  Brandoux.")).returncode == 2


def test_blocks_an_email_local_part(tmp_path):
    _seed(tmp_path, "zorvexa.fake@example.invalid")
    assert _guard(tmp_path, _write("/r/a.py", 'OWNER = "zorvexa.fake"')).returncode == 2


def test_a_word_containing_the_identifier_is_not_a_match(tmp_path):
    _seed(tmp_path, "ange")
    assert _guard(tmp_path, _write("/r/a.md", "Il faut que ça change et que ça mange.")).returncode == 0


def test_edit_and_multiedit_are_checked(tmp_path):
    _seed(tmp_path, "Zorvexa")
    edit = {"tool_name": "Edit", "tool_input": {"file_path": "/r/a.md", "old_string": "x", "new_string": "y Zorvexa"}}
    multi = {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": "/r/a.md", "edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "c", "new_string": "Zorvexa"}]},
    }
    assert _guard(tmp_path, edit).returncode == 2
    assert _guard(tmp_path, multi).returncode == 2


def test_removing_an_identifier_is_allowed(tmp_path):
    """Editing the identifier OUT of a file must stay possible — only new text is checked."""
    _seed(tmp_path, "Zorvexa")
    edit = {"tool_name": "Edit", "tool_input": {"file_path": "/r/a.md", "old_string": "Zorvexa", "new_string": "la personne"}}
    assert _guard(tmp_path, edit).returncode == 0


def test_clean_text_passes(tmp_path):
    _seed(tmp_path, "Zorvexa")
    assert _guard(tmp_path, _write("/r/a.md", "L'utilisatrice principale a été prévenue.")).returncode == 0


def test_no_store_means_no_block_but_says_so_once(tmp_path):
    missing = tmp_path / "absent"
    result = _guard(missing, _write("/r/a.md", "Zorvexa"))
    assert result.returncode == 0


def test_malformed_payload_never_crashes_into_a_block(tmp_path):
    _seed(tmp_path, "Zorvexa")
    result = subprocess.run(
        [sys.executable, str(GUARD)], input="not json", capture_output=True, text=True, env=_env(tmp_path)
    )
    assert result.returncode == 0


# --- the guard on git commit -------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    return repo


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_blocks_a_commit_whose_staged_lines_contain_an_identifier(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    repo = _repo(tmp_path)
    (repo / "notes.md").write_text("Prévenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    assert _guard(store, _bash('git commit -m "docs: notes"'), cwd=repo).returncode == 2


def test_blocks_a_commit_message_with_an_identifier(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    repo = _repo(tmp_path)
    (repo / "notes.md").write_text("propre\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    assert _guard(store, _bash('git commit -m "docs: prévenu Zorvexa"'), cwd=repo).returncode == 2


def test_a_commit_that_removes_an_identifier_passes(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    repo = _repo(tmp_path)
    (repo / "notes.md").write_text("Prévenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "seed")
    (repo / "notes.md").write_text("Prévenir la personne\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    assert _guard(store, _bash('git commit -m "docs: retrait"'), cwd=repo).returncode == 0


def test_other_bash_commands_are_not_scanned(tmp_path):
    """A read-only query may need the word (a yes/no check asked by Jay): only commits are gated."""
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    assert _guard(store, _bash("echo Zorvexa | wc -c"), cwd=tmp_path).returncode == 0


# --- relecture croisee 2026-10-10 (Fable 5.1, FAIL) : chaque trou a son test ---


def _commit_repo(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    repo = _repo(tmp_path)
    (repo / "base.md").write_text("propre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    _git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "seed")
    return store, repo


def test_commit_all_reads_unstaged_tracked_changes(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    assert _guard(store, _bash('git commit -a -m "ok"'), cwd=repo).returncode == 2
    assert _guard(store, _bash('git commit --all -m "ok"'), cwd=repo).returncode == 2


def test_commit_with_pathspec_reads_those_files(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    assert _guard(store, _bash('git commit -m "ok" base.md'), cwd=repo).returncode == 2


def test_identifier_in_a_written_file_path_is_blocked(tmp_path):
    _seed(tmp_path, "Zorvexa")
    assert _guard(tmp_path, _write("/repo/docs/Zorvexa-plan.md", "contenu neutre")).returncode == 2


def test_identifier_in_a_committed_file_name_is_blocked(tmp_path):
    store, repo = _commit_repo(tmp_path)
    _git(repo, "mv", "base.md", "Zorvexa.md")
    assert _guard(store, _bash('git commit -m "renomme"'), cwd=repo).returncode == 2


def test_commit_message_read_from_a_file_is_checked(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("autre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    (tmp_path / "msg.txt").write_text("docs: prevenir Zorvexa\n", encoding="utf-8")
    msg = (tmp_path / "msg.txt").as_posix()  # bash reads a bare backslash as an escape
    assert _guard(store, _bash(f"git commit -F {msg}"), cwd=repo).returncode == 2
    (tmp_path / "msg.txt").write_text("docs: propre\n", encoding="utf-8")
    assert _guard(store, _bash(f"git commit -F {msg}"), cwd=repo).returncode == 0  # refusal was the identifier, not a lost path


def test_message_split_by_shell_quotes_is_checked(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("autre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    assert _guard(store, _bash("git commit -m 'Zor'\"vexa\""), cwd=repo).returncode == 2


def test_message_built_by_command_substitution_is_refused(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("autre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    assert _guard(store, _bash('git commit -m "$(cat /tmp/x)"'), cwd=repo).returncode == 2


def test_heredoc_message_on_stdin_still_works(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("autre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    ok = "git commit -F - <<'EOF'\ndocs: propre\nEOF"
    bad = "git commit -F - <<'EOF'\ndocs: prevenir Zorvexa\nEOF"
    assert _guard(store, _bash(ok), cwd=repo).returncode == 0
    assert _guard(store, _bash(bad), cwd=repo).returncode == 2


def test_subshell_cd_is_followed(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    command = f'(cd {repo.as_posix()} && git commit -m "ok")'
    assert _guard(store, _bash(command), cwd=tmp_path).returncode == 2
    (repo / "base.md").write_text("propre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    assert _guard(store, _bash(command), cwd=tmp_path).returncode == 0  # refusal was the identifier, not a lost path


def test_quoted_git_dash_c_with_space_is_followed(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    repo = tmp_path / "a b"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "n.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "n.md")
    assert _guard(store, _bash(f'git -C "{repo}" commit -m "ok"'), cwd=tmp_path).returncode == 2


def test_dash_c_is_relative_to_the_preceding_cd(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    command = f'cd {tmp_path.as_posix()} && git -C repo commit -m "ok"'
    assert _guard(store, _bash(command), cwd="/").returncode == 2
    (repo / "base.md").write_text("propre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    assert _guard(store, _bash(command), cwd="/").returncode == 0  # refusal was the identifier, not a lost path


def test_unresolvable_repository_fails_closed(tmp_path):
    store = tmp_path / "store"
    _seed(store, "Zorvexa")
    result = _guard(store, _bash('cd /nexiste/pas && git commit -m "ok"'), cwd=tmp_path)
    assert result.returncode == 2
    assert "depot" in result.stderr.lower() or "dépôt" in result.stderr.lower()


def test_grep_for_git_commit_is_not_a_commit(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("Prevenir Zorvexa\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    assert _guard(store, _bash("grep -rn 'git commit' ."), cwd=repo).returncode == 0


def test_markup_and_invisible_characters_do_not_hide_the_word(tmp_path):
    _seed(tmp_path, "Zorvexa")
    for text in ("Zor**vexa**", "Zor\u200cvexa", "`Zorvexa`", "user_zorvexa", "docs/zorvexa.md"):
        assert _guard(tmp_path, _write("/r/a.md", text)).returncode == 2, repr(text)


def test_full_name_in_reverse_order_or_hyphenated_is_blocked(tmp_path):
    _seed(tmp_path, "Quillamir Brandoux")
    assert _guard(tmp_path, _write("/r/a.md", "Brandoux Quillamir")).returncode == 2
    assert _guard(tmp_path, _write("/r/a.md", "Quillamir-Brandoux")).returncode == 2


def test_rebuild_refuses_an_abnormally_small_list(tmp_path):
    _seed(tmp_path, *[f"compte{i:03d}" for i in range(40)])
    shrunk = _cli(tmp_path, "rebuild", stdin="seul\n")
    assert shrunk.returncode != 0
    assert _guard(tmp_path, _write("/r/a.md", "compte007")).returncode == 2
    forced = _cli(tmp_path, "rebuild", "--force", stdin="seul\n")
    assert forced.returncode == 0


def test_non_dict_tool_input_never_crashes(tmp_path):
    _seed(tmp_path, "Zorvexa")
    result = _guard(tmp_path, {"tool_name": "Write", "tool_input": "texte"})
    assert result.returncode == 0
    assert "Traceback" not in result.stderr


# --- seconde relecture 2026-10-10 : fail-closed trop large, mots-cles shell ---


def _staged(tmp_path):
    store, repo = _commit_repo(tmp_path)
    (repo / "base.md").write_text("autre\n", encoding="utf-8")
    _git(repo, "add", "base.md")
    return store, repo


def test_standard_cat_heredoc_message_form_is_accepted(tmp_path):
    store, repo = _staged(tmp_path)
    ok = "git commit -m \"$(cat <<'EOF'\nfeat: propre\n\nCo-Authored-By: X <x@example.invalid>\nEOF\n)\""
    bad = "git commit -m \"$(cat <<'EOF'\nfeat: prevenir Zorvexa\nEOF\n)\""
    assert _guard(store, _bash(ok), cwd=repo).returncode == 0
    assert _guard(store, _bash(bad), cwd=repo).returncode == 2


def test_backticks_in_single_quotes_are_literal_and_accepted(tmp_path):
    store, repo = _staged(tmp_path)
    assert _guard(store, _bash("git commit -m 'fix: gerer `null`'"), cwd=repo).returncode == 0


def test_backticks_in_double_quotes_run_a_command_and_are_refused(tmp_path):
    """Bash executes `x` inside double quotes: the message is not what is written."""
    store, repo = _staged(tmp_path)
    assert _guard(store, _bash('git commit -m "fix: gerer `null`"'), cwd=repo).returncode == 2


def test_commit_behind_shell_keywords_is_detected(tmp_path):
    store, repo = _staged(tmp_path)
    for cmd in ('if true; then git commit -m "Zorvexa"; fi', 'time git commit -m "Zorvexa"', 'command git commit -m "Zorvexa"'):
        assert _guard(store, _bash(cmd), cwd=repo).returncode == 2, cmd


# --- troisieme relecture 2026-10-10 : substitutions reelles qui passaient ---


def test_real_expansions_in_a_commit_are_refused(tmp_path):
    store, repo = _staged(tmp_path)
    (tmp_path / "f").write_text("Zorvexa", encoding="utf-8")
    f = tmp_path / "f"
    for cmd in (
        f'M=$(cat {f}); git commit -m "$M"',
        f'git commit -m "$(cat <<EOF\n$(cat {f})\nEOF\n)"',
        f'git commit -m "a"$(cat {f})"b"',
        f'git commit -m"$(cat {f})"',
        f"git commit -F - <<EOF\n$(cat {f})\nEOF",
        'git commit -m "${M}"',
    ):
        assert _guard(store, _bash(cmd), cwd=repo).returncode == 2, cmd


def test_literal_dollars_and_quoted_heredocs_stay_accepted(tmp_path):
    store, repo = _staged(tmp_path)
    for cmd in (
        "git commit -m 'prix : 5 $ et `code`'",
        "git commit -F - <<'EOF'\nfix: $HOME et `x` restent litteraux\nEOF",
        "git commit -m \"$(cat <<'EOF'\nfeat: prix 5 $ litteral\nEOF\n)\"",
        'git commit -m "prix : 5 \\$ echappe"',
        "cd ~ && cd " + repo.as_posix() + ' && git commit -m "ok"',
    ):
        assert _guard(store, _bash(cmd), cwd=repo).returncode == 0, cmd


# --- quatrieme relecture 2026-10-10 : $(...) entre guillemets plus tot dans la commande ---


def test_quoted_substitution_earlier_does_not_hide_a_later_commit(tmp_path):
    store, repo = _staged(tmp_path)
    for cmd in ('M="$(cat /tmp/f)"; git commit -m "$M"', 'echo "$(date)"; git commit -m "$M"'):
        assert _guard(store, _bash(cmd), cwd=repo).returncode == 2, cmd


# --- cinquieme relecture 2026-10-10 : commit enveloppe dans des backquotes ---


def test_commit_wrapped_in_backticks_is_refused(tmp_path):
    store, repo = _staged(tmp_path)
    for cmd in ("`git commit --allow-empty -m Zorvexa`", 'git commit -m ok; `git commit -m "$M"`'):
        assert _guard(store, _bash(cmd), cwd=repo).returncode == 2, cmd


def test_nested_parentheses_inside_substitution_are_not_ambiguous(tmp_path):
    store, repo = _staged(tmp_path)
    assert _guard(store, _bash('echo $( (true) ); git commit -m "ok"'), cwd=repo).returncode == 0
