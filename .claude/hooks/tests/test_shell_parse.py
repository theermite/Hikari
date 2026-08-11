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
