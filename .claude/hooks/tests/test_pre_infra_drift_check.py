"""D3-infra — pre-infra-drift-check.py

Tests the PreToolUse Bash hook that runs the Shinkofa-Infra registry
`check-drift.py` before any infra-affecting (deploy-class) command, and
BLOCKS when the registry has drifted from the live VPS.

Why a hook (not just the /deploy skill step): deploys done by hand (`ssh vps
... docker ...`) bypass the skill. This hook makes the drift check automatic
on every deploy-class command, wherever it is issued.

The hook locates `<workspace>/Shinkofa-Infra/registry/scripts/check-drift.py`
as a sibling of the current repo. The tests stand up a fake workspace with a
fake check-drift script whose exit code we control (0 = clean, 1 = drift,
2 = probe failed), so no real SSH is involved.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-infra-drift-check.py"


def _make_workspace(tmp_path: Path, *, has_infra: bool, drift_exit: int) -> Path:
    """Create <ws>/repo (git) + <ws>/Shinkofa-Infra/registry/scripts/check-drift.py.

    `drift_exit` controls the fake check-drift exit code. Returns the repo dir
    (the hook runs with cwd=repo and walks up to find the sibling infra repo).
    """
    ws = tmp_path / "workspace"
    repo = ws / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    if has_infra:
        scripts = ws / "Shinkofa-Infra" / "registry" / "scripts"
        scripts.mkdir(parents=True)
        fake = scripts / "check-drift.py"
        # Print sentinel lines so the hook can surface them in its report.
        fake.write_text(
            "import sys\n"
            "print('DRIFT DETECTED (1):' if "
            f"{drift_exit} == 1 else 'No drift. Registry matches VPS.')\n"
            f"sys.exit({drift_exit})\n",
            encoding="utf-8",
        )
    return repo


def _run(payload: dict, *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=20,
        cwd=str(cwd),
    )


# --- Non-triggers ------------------------------------------------------------


def test_silent_on_non_deploy_command(tmp_path):
    repo = _make_workspace(tmp_path, has_infra=True, drift_exit=1)
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_empty_stdin():
    r = subprocess.run([sys.executable, str(HOOK)], input=b"", capture_output=True, timeout=10)
    assert r.returncode == 0


def test_silent_when_no_infra_repo(tmp_path):
    """No sibling Shinkofa-Infra → not opted in → pass through."""
    repo = _make_workspace(tmp_path, has_infra=False, drift_exit=1)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0
    assert r.stderr == b""


def test_pass_when_no_drift(tmp_path):
    """check-drift exits 0 → registry matches VPS → pass through."""
    repo = _make_workspace(tmp_path, has_infra=True, drift_exit=0)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0


# --- Triggers (BLOCK) --------------------------------------------------------


def test_blocks_on_drift(tmp_path):
    """check-drift exits 1 → drift → BLOCK the deploy."""
    repo = _make_workspace(tmp_path, has_infra=True, drift_exit=1)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 2, f"expected BLOCK exit 2, got {r.returncode}, stderr={r.stderr!r}"
    assert b"BLOCKED" in r.stderr
    assert b"drift" in r.stderr.lower()


def test_blocks_on_ssh_systemctl_restart(tmp_path):
    """Manual `ssh vps systemctl restart` also triggers the drift check."""
    repo = _make_workspace(tmp_path, has_infra=True, drift_exit=1)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ssh vps systemctl restart kobo-api"},
    }
    r = _run(payload, cwd=repo)
    assert r.returncode == 2


# --- Probe failure → WARN, do not block --------------------------------------


def test_warns_but_passes_on_probe_failure(tmp_path):
    """check-drift exits 2 (VPS unreachable) → WARN, but do NOT block ops."""
    repo = _make_workspace(tmp_path, has_infra=True, drift_exit=2)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0, f"probe failure must not block, got {r.returncode}"
    assert b"WARNING" in r.stderr


# --- Crash (exit 1 with traceback, no drift report) = inconclusive -----------
# (Jay 2026-06-13, session 004 — check-drift crashed on a missing Python dep
#  such as PyYAML: ImportError -> Python exit 1 -> wrapper read it as DRIFT and
#  hard-blocked the deploy. A tool crash is not drift; it is inconclusive.)


def _make_crashing_infra(tmp_path: Path) -> Path:
    """Fake check-drift that crashes like an uncaught ImportError: a traceback on
    stderr, empty stdout, exit 1."""
    ws = tmp_path / "workspace"
    repo = ws / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    scripts = ws / "Shinkofa-Infra" / "registry" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "check-drift.py").write_text(
        "import sys\n"
        "print('Traceback (most recent call last):', file=sys.stderr)\n"
        "print(\"ModuleNotFoundError: No module named 'yaml'\", file=sys.stderr)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    return repo


def test_import_crash_exit1_is_inconclusive_not_drift(tmp_path):
    repo = _make_crashing_infra(tmp_path)
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0, f"a tool crash must not hard-block the deploy: {r.stderr!r}"
    assert b"WARNING" in r.stderr


def test_empty_stdout_exit1_is_inconclusive(tmp_path):
    """exit 1 with no drift report on stdout (and no recognizable crash text)
    is still inconclusive — never fabricate drift from a silent failure."""
    ws = tmp_path / "workspace"
    repo = ws / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    scripts = ws / "Shinkofa-Infra" / "registry" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "check-drift.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}
    r = _run(payload, cwd=repo)
    assert r.returncode == 0, f"empty-stdout exit 1 must not block: {r.stderr!r}"
    assert b"WARNING" in r.stderr
