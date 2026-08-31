"""Tests for guards/post-bash-secret-alert.py — the fallback net.

pre-bash-secret-mask.py only wraps a fixed list of suspicious commands
(docker exec, docker compose config, ssh+docker, cat .env, printenv). Any
OTHER command can still print a secret Jay didn't expect. This hook cannot
redact what already ran (verified 2026-08-30: PostToolUse `updatedToolOutput`
is ignored on this build) — it can only warn loudly so the secret gets
rotated (brief §6, "la limite honnete").
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "post-bash-secret-alert.py"
_spec = importlib.util.spec_from_file_location("post_bash_secret_alert", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _data(stdout="", stderr=""):
    return {
        "tool_input": {"command": "some-command"},
        "tool_response": {"stdout": stdout, "stderr": stderr},
    }


def test_warns_when_secret_leaks_in_stdout():
    decision = mod.build_decision(_data(stdout="API_KEY=abcdefghijklmnopqrst1234"))
    assert decision is not None
    assert "rotate" in decision["hookSpecificOutput"]["systemMessage"].lower() \
        or "renouvel" in decision["hookSpecificOutput"]["systemMessage"].lower()


def test_warns_when_secret_leaks_in_stderr():
    decision = mod.build_decision(_data(stderr="DATABASE_URL: postgres://u:hunter2ProdPass@host/db"))
    assert decision is not None


def test_silent_on_clean_output():
    decision = mod.build_decision(_data(stdout="All good, 12 files changed"))
    assert decision is None


def test_silent_on_already_masked_output():
    decision = mod.build_decision(_data(stdout="POSTGRES_PASSWORD: <masque:27 car.>"))
    assert decision is None


def test_never_blocks_only_warns():
    # the hook must always exit 0 — a leak already happened, blocking now
    # protects nothing (brief §3, same principle as the pre-hook).
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input='{"tool_input":{"command":"x"},"tool_response":{"stdout":"API_KEY=abcdefghijklmnopqrst1234"}}',
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
