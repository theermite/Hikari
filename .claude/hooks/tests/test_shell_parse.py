"""Tests for lib/shell_parse.py — the single command reader shared by Bash guards.

Born 2026-08-10 from four bypasses of the same family, found by three independent
reviews in one evening. Each guard had its own hand-rolled parsing; each fix
reopened an adjacent hole. These tests pin the grammar once, for both.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from shell_parse import simple_commands  # noqa: E402


# --- separators --------------------------------------------------------------


def test_a_single_command_is_one_segment():
    assert simple_commands("git status") == [["git", "status"]]


@pytest.mark.parametrize("separator", ["&&", "||", ";", "|"])
def test_each_separator_splits(separator):
    assert len(simple_commands(f"ls {separator} pwd")) == 2


def test_a_newline_separates_like_an_operator():
    assert simple_commands("ls\npwd") == [["ls"], ["pwd"]]


# --- quotes ------------------------------------------------------------------


def test_a_quoted_string_stays_one_token():
    assert simple_commands("echo 'git push'") == [["echo", "git push"]]


def test_a_command_passed_to_a_shell_with_dash_c_is_read_as_code():
    """`bash -c '...'` runs its argument — the same way a heredoc body does."""
    assert ["git", "push"] in simple_commands("bash -c 'git push'")


def test_a_dash_c_argument_of_a_non_shell_stays_data():
    """`python -c 'print(...)'` is Python source, not shell."""
    assert simple_commands("python -c 'print(1)'") == [["python", "-c", "print(1)"]]


def test_a_commit_wrapped_in_bash_c_is_visible():
    assert ["git", "commit", "-m", "x"] in simple_commands('bash -c "git commit -m x"')


def test_what_ssh_runs_remotely_is_code():
    assert ["systemctl", "restart", "app"] in simple_commands(
        "ssh vps 'systemctl restart app'"
    )


def test_ssh_with_options_still_finds_the_remote_command():
    assert ["systemctl", "restart", "app"] in simple_commands(
        "ssh -p 2222 vps 'systemctl restart app'"
    )


def test_ssh_without_a_command_is_just_a_session():
    assert simple_commands("ssh vps") == [["ssh", "vps"]]


def test_a_quoted_path_with_spaces_survives():
    assert simple_commands('git -C "D:/My Repo" status') == [
        ["git", "-C", "D:/My Repo", "status"]
    ]


def test_a_windows_backslash_path_is_kept_whole():
    assert simple_commands(r"git -C D:\Dev\Shinzo status") == [
        ["git", "-C", r"D:\Dev\Shinzo", "status"]
    ]


def test_an_unbalanced_quote_raises_rather_than_lying():
    """The caller decides how to fail — silently returning nothing hides risk."""
    with pytest.raises(ValueError):
        simple_commands('echo "oops')


# --- heredocs ----------------------------------------------------------------


def test_a_heredoc_body_is_not_a_command():
    command = "cat <<EOF\nrm -rf /\nEOF"
    assert simple_commands(command) == [["cat"]]


def test_a_command_after_a_heredoc_is_still_read():
    command = "cat > s.sh <<EOF\nhello\nEOF\ndocker compose up -d"
    assert ["docker", "compose", "up", "-d"] in simple_commands(command)


def test_a_quoted_heredoc_delimiter_is_understood():
    command = "python - <<'PY'\nprint(1)\nPY\nls"
    assert simple_commands(command) == [["python", "-"], ["ls"]]


def test_a_heredoc_marker_inside_quotes_is_just_text():
    segments = simple_commands('echo "note <<EOF" ; ls')
    assert ["ls"] in segments


def test_an_arithmetic_shift_is_not_a_heredoc():
    assert ["ls"] in simple_commands("R=$((5 << 2))\nls")


# --- comments ----------------------------------------------------------------


def test_a_comment_ends_the_line_as_the_shell_does():
    assert simple_commands("ls # rm -rf /") == [["ls"]]


# --- empties -----------------------------------------------------------------


def test_an_empty_command_yields_nothing():
    assert simple_commands("") == []


# --- 4th review (2026-08-10): three ways a real command hid from the parser ---


def test_a_line_continuation_keeps_one_command_together():
    """`git \\` then `add -A` is ONE command, not two."""
    assert simple_commands("git \\\nadd -A") == [["git", "add", "-A"]]


def test_a_heredoc_fed_to_a_shell_is_code_not_data():
    command = "bash <<EOF\ndocker compose up -d\nEOF"
    assert ["docker", "compose", "up", "-d"] in simple_commands(command)


def test_a_heredoc_fed_to_a_remote_shell_is_code_too():
    command = "ssh vps bash <<EOF\nsystemctl restart app\nEOF"
    assert ["systemctl", "restart", "app"] in simple_commands(command)


def test_a_windows_shell_executable_is_recognised():
    """`bash.exe` is how bash is actually invoked here (5th review, 2026-08-10)."""
    command = "bash.exe <<EOF\ndocker compose up -d\nEOF"
    assert ["docker", "compose", "up", "-d"] in simple_commands(command)


def test_an_uppercase_shell_name_is_recognised():
    command = "BASH <<EOF\ndocker compose up -d\nEOF"
    assert ["docker", "compose", "up", "-d"] in simple_commands(command)


def test_a_full_path_to_the_shell_is_recognised():
    command = r"C:\Program Files\Git\bin\bash.exe <<EOF" + "\nrm -rf /\nEOF"
    assert ["rm", "-rf", "/"] in simple_commands(command)


def test_deeply_nested_heredocs_fail_closed_rather_than_crash():
    """A crash exits 1, which the hook contract reads as 'warning', not 'block'."""
    command = "bash <<A\n" * 400 + "rm -rf /\n" + "A\n" * 400
    with pytest.raises(ValueError):
        simple_commands(command)


def test_a_heredoc_fed_to_python_stays_data():
    """Python source is not shell: reading it as commands invents commands."""
    command = "python - <<PY\nprint('docker compose up -d')\nPY"
    assert simple_commands(command) == [["python", "-"]]


def test_none_is_tolerated():
    assert simple_commands(None) == []


# --- a quoted string may span several lines (every multi-line commit message) ---------------------------------


def test_a_multiline_quoted_message_is_one_argument():
    command = "git commit -q -m 'feat: x\n\nsecond paragraph with docker compose up\n\nCo-Authored-By: A'"
    segments = simple_commands(command)
    assert len(segments) == 1 and segments[0][:3] == ["git", "commit", "-q"]
    assert "docker compose up" in segments[0][-1]


def test_a_multiline_message_after_a_heredoc_does_not_break_the_parse():
    command = "python - <<'EOF'\nprint('docker compose up')\nEOF\ngit add a && git commit -q -m 'note\n\nsuite\n'"
    segments = simple_commands(command)
    assert segments[0] == ["python", "-"]
    assert ["git", "add", "a"] in segments
    assert any(s[:2] == ["git", "commit"] and "suite" in s[-1] for s in segments)


def test_two_multiline_strings_in_one_command():
    command = "echo 'a\nb' && echo \"c\nd\""
    assert simple_commands(command) == [["echo", "a\nb"], ["echo", "c\nd"]]


def test_a_quote_that_never_closes_still_fails_closed():
    import pytest
    with pytest.raises(ValueError):
        simple_commands("git commit -m 'never closed\nsecond line")


# --- a multi-line string with a LIVE command substitution is code, not text (regression found 2026-11-01) ------


def test_a_multiline_double_quoted_string_with_a_substitution_fails_closed():
    for command in ("git commit -m \"$(cat <<'EOF'\nmsg\nEOF\ncat .env\nEOF\n)\"",
                    "echo \"line one\n$(cat .env)\"",
                    "echo \"line one\n`cat .env`\""):
        with pytest.raises(ValueError):
            simple_commands(command)


def test_a_multiline_single_quoted_string_may_hold_substitution_text_as_data():
    command = "git commit -q -m 'note\n\nle garde lit `docker compose up` et $(date) comme du texte\n'"
    segments = simple_commands(command)
    assert len(segments) == 1 and "docker compose up" in segments[0][-1]


# --- the two readings of the quotes must agree before lines are joined (relecture 7.7.0, 2026-11-01) --------------


@pytest.mark.parametrize("command", [
    # bash closes the string after `b"`, then runs the push; the tokenizer thinks the quote is still open
    'echo "a\\" b"; git push --force origin main\necho "ok\\""',
    # one escaped quote per line: a secret read hides between two searches
    'grep -n "\\"name" package.json\ncat .env\ngrep -n "\\"version" package.json',
])
def test_a_line_whose_escaped_quotes_split_the_two_readings_fails_closed(command):
    with pytest.raises(ValueError):
        simple_commands(command)


def test_a_string_bash_keeps_open_but_the_tokenizer_closes_fails_closed():
    """`\\"` keeps bash inside the string, so the next line is TEXT for bash; the tokenizer would run it as a command."""
    with pytest.raises(ValueError):
        simple_commands('echo "a\\"\nls -la')


def test_a_multiline_message_holding_escaped_quotes_fails_closed():
    """Prudence: once lines are joined, the tokenizer cannot be trusted on `\\"` inside the string."""
    with pytest.raises(ValueError):
        simple_commands('git commit -m "title\nsays \\"hello\\" there"')


def test_an_escaped_quote_on_a_single_line_still_parses_when_the_readings_agree():
    assert simple_commands('echo "a\\"b\\"c"; ls') == [["echo", "a\\b\\c"], ["ls"]]


@pytest.mark.parametrize("command", [
    # relecture 7.7.0: les deux lectures finissent dans le même état mais coupent les chaînes ailleurs
    'echo "a\\" "; cat notes.txt; echo "\\""',
    "echo \\' ; git push --force ; echo \\'",
    'echo "x\\" y"; git push --force origin main; echo "\\" z"',
])
def test_escaped_quotes_that_move_a_command_boundary_fail_closed(command):
    with pytest.raises(ValueError):
        simple_commands(command)


@pytest.mark.parametrize("command, expected", [
    ("find . -name x -exec rm {} \\;", [["find", ".", "-name", "x", "-exec", "rm", "{}", "\\"], []]),
    ('git commit -m "fix \\"x\\" ok"; git push', [["git", "commit", "-m", "fix \\x\\ ok"], ["git", "push"]]),
    ("cd C:\\Git\\bin && ls", [["cd", "C:\\Git\\bin"], ["ls"]]),
])
def test_legitimate_backslashes_are_not_refused(command, expected):
    assert [s for s in simple_commands(command) if s] == [s for s in expected if s]


@pytest.mark.parametrize("opener", ["cat <<-EOF", "cat <<- EOF", "cat <<-'EOF'", "cat <<- 'EOF'", 'cat <<-"EOF"'])
def test_a_heredoc_with_tabs_ends_at_its_delimiter_and_the_next_command_is_seen(opener):
    """`<<-` (fiche Kata) : le délimiteur était lu « -EOF », donc tout ce qui suit passait pour du corps."""
    segments = simple_commands(f"{opener}\n\tcorps; ls\n\tEOF\npwd")
    assert segments == [["cat"], ["pwd"]]


def test_a_heredoc_fed_to_a_shell_with_tabs_is_still_read_as_code():
    segments = simple_commands("bash <<-EOF\n\tgit push --force origin main\n\tEOF\npwd")
    assert ["git", "push", "--force", "origin", "main"] in segments and ["pwd"] in segments


def test_an_escaped_quote_inside_double_quotes_does_not_hide_a_live_substitution():
    """Relecture 2026-11-01: bash reads \\" as a literal quote and stays in double quotes; an apostrophe after it
    must not make the reader think it is in single quotes, with a command substitution behind."""
    command = 'echo "A\\"\' $(cat .env) \'"\necho \\"'
    with pytest.raises(ValueError):
        simple_commands(command)


def test_pipe_and_stderr_is_a_command_separator():
    """`|&` (relecture 7.8.0) : la commande placée juste après n'était pas lue comme une commande."""
    assert simple_commands("ls |& cat notes.txt") == [["ls"], ["cat", "notes.txt"]]
