"""D1 — post-commit-push-check.py

Tests the PostToolUse Bash hook that auto-pushes after a `git commit`.

Behavior (since 2026-05-31):
- Auto-push when branch ahead of upstream by 1..5 commits.
- Skip + WARN when last commit message carries [WIP] or [NO-PUSH].
- Skip + WARN when ahead > 5 (suspicious accumulation).
- Silent when in sync, no upstream, detached HEAD, or non-commit command.

All paths exit 0 (never blocks).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "guards" / "post-commit-push-check.py"


def _load_hook_module():
    """Import the hyphenated hook file as a module for direct unit testing."""
    spec = importlib.util.spec_from_file_location("post_commit_push_check", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_hook = _load_hook_module()

# The git stub is a bash script with no extension. Windows cannot invoke it
# (PATHEXT does not include "no extension"). The stub-based tests run on
# Linux/macOS CI; the non-stub tests cover the trigger logic on every OS.
_SKIP_BASH_STUB = pytest.mark.skipif(
    sys.platform == "win32",
    reason="bash stub `git` is not invokable on Windows (no .cmd/.exe extension)",
)


# --- Test helpers ------------------------------------------------------------


_STUB_BODY = """#!/usr/bin/env bash
case "$1" in
  status)
    echo "${STUB_STATUS:-## main...origin/main}"
    ;;
  rev-parse)
    if [ "$2" = "--abbrev-ref" ]; then
      echo "${STUB_BRANCH:-main}"
    elif [ "$2" = "--show-toplevel" ]; then
      echo "/tmp/fake-repo"
    fi
    ;;
  log)
    echo "${STUB_LOG_MSG:-feat: foo}"
    ;;
  push)
    if [ "${STUB_PUSH_FAIL:-0}" = "1" ]; then
      echo "remote rejected" >&2
      exit 1
    fi
    exit 0
    ;;
esac
"""


def _make_stub_git(tmp_path: Path) -> Path:
    """Write a bash stub `git` that dispatches on subcommand. Return its dir."""
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "git"
    stub.write_text(_STUB_BODY)
    stub.chmod(0o755)
    return stub_dir


def _run(payload: dict, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook with stdin JSON and an optional env overlay."""
    env = {**os.environ, **(env_overrides or {})}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
        env=env,
    )


def _run_with_stub(payload: dict, stub_dir: Path, stub_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}
    if stub_env:
        env.update(stub_env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
        env=env,
    )


# --- Auto-push path ----------------------------------------------------------


@_SKIP_BASH_STUB
def test_auto_pushes_when_ahead(tmp_path):
    """Branch ahead by 1 commit, clean message → auto-push, stderr summary."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'feat: foo'"},
        "tool_response": {"stdout": "[main abc1234] feat: foo\n"},
    }
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main [ahead 1]",
        "STUB_BRANCH": "main",
        "STUB_LOG_MSG": "feat: foo",
    })
    assert r.returncode == 0, f"hook must never block; got exit {r.returncode}"
    assert b"[auto-push]" in r.stderr, f"expected auto-push marker, got: {r.stderr!r}"
    assert b"main" in r.stderr


@_SKIP_BASH_STUB
def test_auto_push_failure_surfaces_warning(tmp_path):
    """If `git push` fails, the hook still exits 0 but emits a WARNING."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main [ahead 1]",
        "STUB_BRANCH": "main",
        "STUB_LOG_MSG": "feat: foo",
        "STUB_PUSH_FAIL": "1",
    })
    assert r.returncode == 0
    assert b"WARNING" in r.stderr
    assert b"auto-push failed" in r.stderr


# --- Skip conditions ---------------------------------------------------------


@_SKIP_BASH_STUB
def test_skips_on_wip_marker(tmp_path):
    """Commit message containing [WIP] → no push, WARN explaining why."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'wip: foo [WIP]'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main [ahead 1]",
        "STUB_BRANCH": "main",
        "STUB_LOG_MSG": "wip: foo [WIP]",
    })
    assert r.returncode == 0
    assert b"WIP" in r.stderr or b"NO-PUSH" in r.stderr
    assert b"[auto-push]" not in r.stderr


@_SKIP_BASH_STUB
def test_skips_on_no_push_marker(tmp_path):
    """Commit message with [NO-PUSH] → no push."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo [NO-PUSH]'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main [ahead 1]",
        "STUB_BRANCH": "main",
        "STUB_LOG_MSG": "feat: foo [NO-PUSH]",
    })
    assert r.returncode == 0
    assert b"[auto-push]" not in r.stderr


@_SKIP_BASH_STUB
def test_warns_when_ahead_exceeds_threshold(tmp_path):
    """ahead > 5 → no push, WARN about accumulation."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main [ahead 10]",
        "STUB_BRANCH": "main",
        "STUB_LOG_MSG": "feat: foo",
    })
    assert r.returncode == 0
    assert b"WARNING" in r.stderr
    assert b"ahead" in r.stderr.lower()
    assert b"[auto-push]" not in r.stderr


@_SKIP_BASH_STUB
def test_silent_when_pushed(tmp_path):
    """HEAD matches upstream → silent (nothing to push)."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main...origin/main",
        "STUB_BRANCH": "main",
    })
    assert r.returncode == 0
    assert r.stderr == b""


@_SKIP_BASH_STUB
def test_silent_when_no_upstream(tmp_path):
    """Branch without upstream → silent (cannot push)."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## main",
        "STUB_BRANCH": "main",
    })
    assert r.returncode == 0
    assert r.stderr == b""


@_SKIP_BASH_STUB
def test_silent_on_detached_head(tmp_path):
    """Detached HEAD → silent (no branch to push)."""
    stub_dir = _make_stub_git(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'feat: foo'"}}
    r = _run_with_stub(payload, stub_dir, {
        "STUB_STATUS": "## HEAD (no branch)",
        "STUB_BRANCH": "HEAD",
    })
    assert r.returncode == 0
    assert r.stderr == b""


# --- Non-triggers (must be silent, no git invoked) ---------------------------


def test_silent_on_non_commit_command():
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    r = _run(payload)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_git_status():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
    r = _run(payload)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_amend():
    """`git commit --amend` is intentional rewrite → skip."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit --amend --no-edit"}}
    r = _run(payload)
    assert r.returncode == 0
    assert r.stderr == b""


@pytest.mark.parametrize("cmd", [
    "git commit --amend --no-edit",
    "git commit --amend",
    "git commit --amend -m 'x'",
    "git commit --no-edit --amend",
    "git commit -m 'msg' --amend",
])
def test_looks_like_commit_false_on_amend(cmd):
    """--amend rewrites must be excluded — else the hook auto-pushes them
    and the amend silent-test flakes on the real repo's ahead count."""
    assert _hook._looks_like_commit(cmd) is False


@pytest.mark.parametrize("cmd", [
    "git commit -m 'feat: foo'",
    "git commit",
    "git commit -a -m 'x'",
])
def test_looks_like_commit_true_on_real_commit(cmd):
    assert _hook._looks_like_commit(cmd) is True


@pytest.mark.parametrize("cmd", [
    "git status",
    "ls -la",
    "git push",
    "git log --oneline",
])
def test_looks_like_commit_false_on_non_commit(cmd):
    assert _hook._looks_like_commit(cmd) is False


def test_silent_on_empty_stdin():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0


def test_silent_on_malformed_json():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"not json at all",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0
