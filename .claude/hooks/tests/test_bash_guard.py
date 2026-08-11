"""Tests for guards/bash-guard.py — check_destructive() + RM-OK token.

The RM-OK token (Jay 2026-06-14) lifts the rm -rf block for ONE command,
only after Jay's explicit authorization, and never for catastrophic targets
(root, home, project/.git, system roots). A non-empty reason is mandatory.

Loaded by file path (hyphen in name -> not importable as a module).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "bash-guard.py"
_spec = importlib.util.spec_from_file_location("bash_guard", HOOK)
bg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bg)


# --- Regression: existing behaviour preserved -------------------------------


def test_rm_rf_non_cache_blocked_without_token():
    assert bg.check_destructive("rm -rf /srv/foo") is not None


def test_rm_rf_cache_dir_allowed():
    assert bg.check_destructive("rm -rf node_modules") is None


def test_normal_command_passes():
    assert bg.check_destructive("ls -la /srv") is None


def test_destructive_sql_still_blocked():
    assert bg.check_destructive("DROP TABLE users") is not None


# --- RM-OK token grants a single deletion -----------------------------------


def test_rm_rf_with_token_and_reason_allowed():
    cmd = "rm -rf /srv/tools.theermite.com  # RM-OK: cleanup VPS tool, Jay authorized"
    assert bg.check_destructive(cmd) is None


def test_rm_rf_subdir_under_var_allowed_with_token():
    assert bg.check_destructive("rm -rf /var/www/old # RM-OK: stale deploy") is None


def test_rm_rf_token_without_reason_blocked():
    assert bg.check_destructive("rm -rf /srv/foo # RM-OK:") is not None


# --- Catastrophic targets: token NEVER overrides ----------------------------


def _is_catastrophic_block(msg: str) -> bool:
    return msg is not None and "catastroph" in msg.lower()


def test_rm_rf_root_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf / # RM-OK: x"))


def test_rm_rf_home_tilde_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf ~ # RM-OK: x"))


def test_rm_rf_home_var_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf $HOME # RM-OK: x"))


def test_rm_rf_dot_git_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf .git # RM-OK: x"))


def test_rm_rf_glob_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf * # RM-OK: x"))


def test_rm_rf_system_root_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf /etc # RM-OK: x"))


def test_rm_rf_dot_blocked_even_with_token():
    assert _is_catastrophic_block(bg.check_destructive("rm -rf . # RM-OK: x"))


# --- check_git_add_broad: existing behaviour, previously untested ------------
#
# The function shipped in April 2026 with no test. These pin what it already
# does, before extending it (2026-08-10).


def test_git_add_all_flag_blocked():
    assert bg.check_git_add_broad("git add -A") is not None


def test_git_add_dot_blocked():
    assert bg.check_git_add_broad("git add .") is not None


def test_git_add_long_all_flag_blocked():
    assert bg.check_git_add_broad("git add --all") is not None


def test_git_add_explicit_file_passes():
    assert bg.check_git_add_broad("git add -- src/main.py") is None


def test_unrelated_command_passes():
    assert bg.check_git_add_broad("git status --porcelain") is None


# --- check_git_add_broad: a bare directory on a shared repo ------------------
#
# Shinzo is written by several sessions at once. Staging a whole directory
# there carries away another session's work under your commit message
# (observed 2026-08-10). Elsewhere, `git add src/` is legitimate daily work —
# so the block is scoped to the shared repo, never global.


def test_directory_pathspec_on_shinzo_blocked():
    assert bg.check_git_add_broad("git -C D:/30-Dev-Projects/Shinzo add 02-Projets/") is not None


def test_directory_pathspec_on_shinzo_blocked_via_cd():
    assert bg.check_git_add_broad("cd ~/Shinzo && git add 05-Memoire/") is not None


def test_directory_pathspec_elsewhere_passes():
    assert bg.check_git_add_broad("git add src/") is None


def test_explicit_file_on_shinzo_passes():
    assert bg.check_git_add_broad("git -C D:/30-Dev-Projects/Shinzo add -- 02-Projets/Kata.md") is None


def test_several_explicit_files_on_shinzo_pass():
    assert (
        bg.check_git_add_broad(
            "git -C ~/Shinzo add -- 02-Projets/Kata.md 02-Projets/_Cross-Project.md"
        )
        is None
    )


def test_broad_flag_on_shinzo_still_blocked():
    assert bg.check_git_add_broad("git -C ~/Shinzo add -A") is not None


# --- no false blocks ---------------------------------------------------------
#
# A guard that blocks the documentation of its own rule is a process failure
# (same class as the false block found on 2026-07-30).


def test_commit_message_quoting_the_forbidden_command_passes():
    assert (
        bg.check_git_add_broad('git commit -m "regle Shinzo: jamais git add 02-Projets/"')
        is None
    )


def test_commit_message_quoting_the_broad_flag_passes():
    assert bg.check_git_add_broad("git commit -m 'ne jamais faire git add -A'") is None


def test_shared_repo_name_mentioned_elsewhere_does_not_block():
    assert bg.check_git_add_broad("echo shinzo && git add lib/") is None


def test_directory_after_double_dash_on_shared_repo_blocked():
    assert bg.check_git_add_broad("git -C ~/Shinzo add -- 05-Memoire/") is not None


# --- adversarial cases found by independent review (2026-08-10) --------------
#
# A regex over a shell line is fragile: quotes, `-c key=val`, a missing trailing
# slash and a heredoc all slipped through or blocked wrongly. These pin the
# behaviour the guard must hold whatever the surface form.


def test_shared_repo_path_with_spaces_still_blocked():
    assert bg.check_git_add_broad('git -C "D:/Shinzo dir" add -A') is not None


def test_directory_with_trailing_slash_on_an_unresolvable_shared_path_blocked():
    """When the path cannot be resolved, only the explicit trailing slash counts."""
    assert bg.check_git_add_broad("git -C ~/Shinzo add 02-Projets/") is not None


def test_inline_config_before_add_still_blocked():
    assert bg.check_git_add_broad("git -c user.name=x -c user.email=y add -A") is not None


def test_repo_whose_name_merely_contains_shinzo_is_not_shared():
    assert bg.check_git_add_broad("git -C ~/shinzoku-project add src/") is None


def test_cd_to_an_unrelated_directory_is_not_shared():
    assert bg.check_git_add_broad("cd /tmp/not-shinzo-related && git add lib/") is None


def test_heredoc_body_quoting_the_rule_does_not_block():
    command = 'git commit -F - <<EOF\nregle Shinzo: jamais git add -A\nEOF'
    assert bg.check_git_add_broad(command) is None


def test_broad_add_after_a_commit_message_is_still_blocked():
    command = 'git commit -m "regle: jamais git add -A" && git add -A'
    assert bg.check_git_add_broad(command) is not None


# --- 2nd review (2026-08-10): a guard must fail closed ----------------------
#
# Three holes the shlex rewrite opened, none of them exercised by the tests that
# came with it: a newline is a command separator too, an unbalanced quote must
# not disable the guard, and the disk must decide both ways on "is it a folder".


def test_broad_add_on_a_following_line_is_blocked():
    assert bg.check_git_add_broad("git status\ngit add -A") is not None


def test_directory_on_shared_repo_on_a_following_line_is_blocked(tmp_path):
    repo = tmp_path / "Shinzo"
    (repo / "02-Projets").mkdir(parents=True)
    assert bg.check_git_add_broad(f"cd {repo}\ngit add 02-Projets") is not None


def test_unbalanced_quote_does_not_disable_the_guard():
    assert bg.check_git_add_broad('git add -A "') is not None


def test_real_file_without_extension_on_shared_repo_passes(tmp_path):
    repo = tmp_path / "Shinzo"
    repo.mkdir()
    (repo / "LICENSE").write_text("x", encoding="utf-8")
    assert bg.check_git_add_broad(f"git -C {repo} add LICENSE") is None


def test_real_directory_without_trailing_slash_on_shared_repo_blocked(tmp_path):
    repo = tmp_path / "Shinzo"
    (repo / "02-Projets").mkdir(parents=True)
    assert bg.check_git_add_broad(f"git -C {repo} add 02-Projets") is not None


def test_heredoc_body_is_never_read_as_a_command():
    command = "git commit -F - <<EOF\ngit add -A\nEOF\ngit status"
    assert bg.check_git_add_broad(command) is None


def test_command_after_a_heredoc_is_still_checked():
    command = "git commit -F - <<EOF\nmessage\nEOF\ngit add -A"
    assert bg.check_git_add_broad(command) is not None


def test_windows_backslash_repo_path_is_understood():
    assert bg.check_git_add_broad(r"git -C D:\30-Dev-Projects\Shinzo add -A") is not None


def test_windows_backslash_explicit_file_passes():
    command = r"git -C D:\30-Dev-Projects\Shinzo add -- 02-Projets\Kata.md"
    assert bg.check_git_add_broad(command) is None
