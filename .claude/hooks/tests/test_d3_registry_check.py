"""D3 — pre-deploy-registry-check.py

Tests the PreToolUse Bash hook that blocks deploys when `docs/registry/` has
uncommitted changes (proxy for "registry desync vs code").

Why this proxy: the original spec says "run /update-registry then git diff
docs/registry/", but a hook cannot invoke Claude Code skills. The observable
equivalent is: if `git status --porcelain docs/registry/` reports anything,
the registry was regenerated and not committed (or never committed at all).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-registry-check.py"


def _make_repo_with_git(tmp_path: Path, *, has_registry: bool,
                       registry_dirty: bool) -> Path:
    """Create a real (tiny) git repo so `git status --porcelain` is meaningful."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)

    (repo / "README.md").write_text("# fake\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    if has_registry:
        reg = repo / "docs" / "registry"
        reg.mkdir(parents=True)
        (reg / "functions.json").write_text('{"items": []}\n')
        subprocess.run(["git", "add", "docs/registry/"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "registry"], cwd=repo, check=True)

        if registry_dirty:
            (reg / "functions.json").write_text('{"items": [{"name":"x"}]}\n')
            # Leave uncommitted.

    return repo


def _run(payload: dict, *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=15,
        cwd=str(cwd),
    )


# --- Non-triggers ------------------------------------------------------------


def test_silent_on_non_deploy_command(tmp_path):
    repo = _make_repo_with_git(tmp_path, has_registry=True, registry_dirty=True)
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_empty_stdin():
    r = subprocess.run([sys.executable, str(HOOK)], input=b"", capture_output=True, timeout=10)
    assert r.returncode == 0


def test_silent_when_no_registry_dir(tmp_path):
    """No docs/registry/ → project not opted in → pass through."""
    repo = _make_repo_with_git(tmp_path, has_registry=False, registry_dirty=False)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_when_registry_clean(tmp_path):
    """Registry exists, committed, nothing pending → pass through."""
    repo = _make_repo_with_git(tmp_path, has_registry=True, registry_dirty=False)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0
    assert r.stderr == b""


# --- Triggers (BLOCK) --------------------------------------------------------


def test_blocks_when_registry_dirty(tmp_path):
    """Registry has uncommitted modifications → BLOCK."""
    repo = _make_repo_with_git(tmp_path, has_registry=True, registry_dirty=True)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 2, f"expected BLOCK exit 2, got {r.returncode}, stderr={r.stderr!r}"
    assert b"BLOCKED" in r.stderr
    assert b"registry" in r.stderr.lower()


def test_blocks_on_systemctl_restart(tmp_path):
    """Deploy variant `systemctl restart` also triggers the check."""
    repo = _make_repo_with_git(tmp_path, has_registry=True, registry_dirty=True)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ssh vps systemctl restart kobo"},
    }
    r = _run(payload, cwd=repo)
    assert r.returncode == 2
