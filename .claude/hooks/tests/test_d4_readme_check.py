"""D4 — pre-session-end-readme-check.py

Tests the UserPromptSubmit hook that fires on `/session-end` invocation and
warns when README is stale relative to the session's changes.

Trigger criteria (≥1 match + README unchanged ⇒ WARN):
1. New public command/feature shipped (new file in commands/ or .claude/commands/)
2. Install/run steps changed (package.json deps, .env*, ports in compose/config)
3. Major stack/version bump (manifest version field)
4. Breaking change (commit subject contains `!:` or body has `BREAKING CHANGE:`)
5. (subjective — out of scope for the hook)

Behavior is non-blocking (exit 0 silent OR exit 1 warn).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-session-end-readme-check.py"

import pytest  # noqa: E402

# Linux-only integration suite. These tests stub `git` via a PATH stub to drive
# the hook's diff logic. On Windows, subprocess cannot intercept a bare `git`
# call through a PATH stub (no PATHEXT match, CreateProcess won't run .cmd/.bat
# for a list-form call), so the hook falls back to the real `git` in an empty
# tmp repo: no commits, no criteria, silent pass — the assertions then fail for
# an environment reason, not a logic bug. The hook itself is cross-platform
# Python. Proven green on Linux (VPS) 2026-06-12: 19 passed.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX `git` stub not interceptable via PATH on Windows; "
    "Linux-only integration suite. Hook is cross-platform; proven green on Linux VPS.",
)


def _make_git_stub(stub_dir: Path, *, since_commit: str = "abc123",
                   changed_files: str = "", commit_log: str = "") -> None:
    """Create a `git` stub script that returns canned answers.

    `changed_files` may contain real newlines (one path per line). They are
    emitted verbatim via `printf '%s\\n'` to avoid bash echo backslash quirks.
    """
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "git"
    # Use printf so embedded newlines survive. Single-quote-safe by replacing.
    files_q = changed_files.replace("'", "'\"'\"'")
    log_q = commit_log.replace("'", "'\"'\"'")
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = 'rev-parse' ] && [ \"$2\" = '--show-toplevel' ]; then\n"
        "  echo '/tmp/fake-repo'; exit 0\n"
        "fi\n"
        "if [ \"$1\" = 'log' ] && [[ \"$2\" == --since=* ]]; then\n"
        f"  printf '%s\\n' '{since_commit}'; exit 0\n"
        "fi\n"
        "if [ \"$1\" = 'rev-list' ]; then\n"
        f"  printf '%s\\n' '{since_commit}'; exit 0\n"
        "fi\n"
        "if [ \"$1\" = 'diff' ] && [ \"$2\" = '--name-only' ]; then\n"
        f"  printf '%s' '{files_q}'; printf '\\n'; exit 0\n"
        "fi\n"
        "if [ \"$1\" = 'log' ] && [ \"$2\" = '--pretty=format:%B' ]; then\n"
        f"  printf '%s' '{log_q}'; exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    stub.chmod(0o755)


def _run(payload: dict, env_path: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ}
    if env_path:
        env["PATH"] = env_path
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
        env=env,
    )


# --- Non-triggers (must pass through silent) ---------------------------------


def test_silent_on_non_session_end_prompt():
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/dev refactor the auth module",
    }
    r = _run(payload)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_empty_prompt():
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "sid-A", "prompt": ""}
    r = _run(payload)
    assert r.returncode == 0


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
        input=b"not json",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0


# --- Triggers (must WARN exit 1) ---------------------------------------------


def test_warns_when_new_command_shipped_and_readme_unchanged(tmp_path):
    """A new file under .claude/commands/ + README unchanged → WARN."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files=".claude/commands/foo.md\nkobo_api/lib/foo.ex",
        commit_log="feat(commands): add /foo command",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 1, f"expected WARN exit 1, got {r.returncode}, stderr={r.stderr!r}"
    assert b"README" in r.stderr


def test_warns_on_breaking_change_and_readme_unchanged(tmp_path):
    """Commit with `feat!:` subject → WARN."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files="kobo_api/lib/auth.ex",
        commit_log="feat!: drop legacy auth",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 1
    assert b"README" in r.stderr


def test_warns_on_breaking_change_in_body(tmp_path):
    """Commit body with `BREAKING CHANGE:` → WARN."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files="kobo_api/lib/x.ex",
        commit_log="feat(x): redesign\n\nBREAKING CHANGE: API changed",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 1


def test_warns_when_package_json_changed(tmp_path):
    """Changes to a dependency manifest → WARN."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files="kobo-web/package.json",
        commit_log="chore(deps): bump react to 19",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 1


def test_warns_when_compose_changed(tmp_path):
    """Changes to docker-compose / .env → WARN."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files="docker-compose.yml\n.env.example",
        commit_log="feat(infra): add new service on port 5006",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 1


# --- README updated → silent (criteria match but README also touched) --------


def test_silent_when_readme_updated_alongside_changes(tmp_path):
    """If README.md is in the diff → silent even when criteria match."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files=".claude/commands/foo.md\nREADME.md",
        commit_log="feat(commands): add /foo + doc",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 0
    assert r.stderr == b""


# --- No criteria → silent ----------------------------------------------------


def test_silent_when_no_criteria_match(tmp_path):
    """Internal refactor only → no criterion matches → silent."""
    stub_dir = tmp_path / "bin"
    _make_git_stub(
        stub_dir,
        changed_files="kobo_api/lib/internal.ex",
        commit_log="refactor(internal): rename helper",
    )
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sid-A",
        "prompt": "/session-end",
    }
    env_path = f"{stub_dir}:{os.environ['PATH']}"
    r = _run(payload, env_path=env_path)
    assert r.returncode == 0
    assert r.stderr == b""
