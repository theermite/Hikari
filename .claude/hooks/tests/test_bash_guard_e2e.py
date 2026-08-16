"""End-to-end tests for guards/bash-guard.py — the real payload shape.

Why this file exists (2026-08-16). `read_input()` read `data["command"]` at
the top level, while the harness nests it under `tool_input` (same defect
family as write-guard.py, fixed 2026-08-07, and post-write-guard.py, fixed
the same day as this file). `command` was therefore always `""` on every
real invocation.

Two checks kept working by accident: `check_secrets(raw)` and
`check_destructive(raw)` scan the FULL raw JSON text, so a command embedded
in it still matched. Every check that used the (broken) `command` variable
never fired: `--no-verify`, `git add -A`/`--all`/`.`, force-push to main
(the exact protection Independent-Review.md exists for), the warn-level
force-push, conventional-commit, Co-Authored-By, and the vitest OOM guard.

Unit tests on the check functions (test_bash_guard.py) could not catch this
— they call `check_git_add_broad("git add -A")` directly, bypassing
`read_input()` entirely. Only a subprocess test with the real nested
payload reproduces the failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "bash-guard.py"


def _run(command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )


def test_force_push_to_main_is_blocked():
    # Independent-Review.md: force-push is history you cannot get back.
    result = _run("git push --force origin main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_git_add_dash_a_is_blocked():
    result = _run("git add -A")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_no_verify_is_blocked():
    result = _run('git commit --no-verify -m "x"')
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_harmless_command_passes():
    result = _run("git status")
    assert result.returncode == 0, result.stderr


# --- Independent review, 2026-08-16 — force-push false positives -------------
#
# Reactivating check_force_push_main (fixed above) woke up a dormant defect
# of the same family: `\b(main|master)\b` searched the whole raw command, so
# it matched the substring inside a legitimate branch name and inside a
# command that only MENTIONS the phrase. Both reproduced live before the fix.


def test_force_push_to_branch_containing_main_substring_is_not_blocked():
    result = _run("git push --force origin feature/rename-main-module")
    assert result.returncode == 0, result.stderr


def test_echo_mentioning_force_push_main_is_not_blocked():
    result = _run("echo 'never git push --force origin main'")
    assert result.returncode == 0, result.stderr


def test_force_push_to_main_via_refspec_colon_is_blocked():
    result = _run("git push --force origin HEAD:main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


# --- Independent review #2, 2026-08-16 — the position-guessing fix went ------
# silent instead of blocking, on two different real force-pushes to main.
# Structural fix (not another positional patch): a force-push whose target
# can't be positively resolved now WARNS instead of staying silent.


def test_force_push_to_main_with_env_var_prefix_is_blocked():
    result = _run("GIT_DIR=/tmp/x git push --force origin main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_force_push_with_separated_push_option_is_blocked():
    # `-o ci.skip` used to shift "main" into the remote's position, reading
    # as a non-main push and downgrading BLOCK to a wrong WARN. Skipping the
    # option's separate-token value restores the correct branch position.
    result = _run("git push --force -o ci.skip origin main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_force_push_with_repo_equals_flag_at_least_warns():
    result = _run("git push --force --repo=origin main")
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr


def test_force_push_alone_at_least_warns():
    # `git push -f` alone pushes the current branch — genuinely ambiguous
    # from the command text (documented, not a regression), but silence is.
    result = _run("git push -f")
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr


# --- Independent review #3, 2026-08-16 — the `+refspec` force syntax --------
# git has TWO ways to say "force": the --force/-f flag, and a `+` prefix on
# the refspec. The flag-only detection missed the second entirely — a real
# force-push to main via `+refspec` went through in complete silence.


def test_force_push_to_main_via_plus_refspec_colon_is_blocked():
    result = _run("git push origin +feature:main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_force_push_to_main_via_bare_plus_refspec_is_blocked():
    result = _run("git push origin +main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_plus_refspec_to_non_main_branch_at_least_warns():
    result = _run("git push origin +feature:other-branch")
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr


# --- Independent review #4, 2026-08-16 — destructive push MODES --------------
# A third way to destroy main, with no force flag and no `+` anywhere:
# `--mirror` (makes the remote match the local exactly, deleting what is
# missing) and `--delete` / the empty-source refspec `:branch` (removes the
# remote branch outright). Verified live: all three left main gone or
# rewritten while the guard stayed completely silent.


def test_mirror_push_is_blocked():
    result = _run("git push --mirror origin")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_delete_of_main_is_blocked():
    result = _run("git push origin --delete main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_empty_source_refspec_deleting_main_is_blocked():
    result = _run("git push origin :main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_delete_of_a_feature_branch_is_not_blocked():
    # Deleting a merged feature branch is ordinary housekeeping.
    result = _run("git push origin --delete feature/done")
    assert result.returncode == 0, result.stderr


# --- Independent review #5, 2026-08-16 — SEVERAL branches in one push -------
# Rounds 1-4 each resolved ONE branch at ONE position. git accepts several
# refspecs in a single push, so main slipped through whenever it sat anywhere
# but the checked slot — and the WARNING then NAMED the wrong branch, which
# reads as "checked and safe". The resolver now returns every target.


def test_delete_of_main_among_several_branches_is_blocked():
    result = _run("git push origin --delete main feature/x")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_delete_of_main_first_of_many_is_blocked():
    result = _run("git push origin --delete main feature/x feature/y feature/z")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_force_push_of_several_refspecs_including_main_is_blocked():
    result = _run("git push --force origin feature/x main")
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_force_push_of_several_feature_branches_is_not_blocked():
    result = _run("git push --force origin feature/x feature/y")
    assert result.returncode == 0, result.stderr
