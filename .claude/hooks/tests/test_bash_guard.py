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
