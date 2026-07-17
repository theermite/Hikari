"""D2 — pre-deploy-vault-check.py

Tests the PreToolUse Bash hook that blocks deploys when a Vault-mapped env var
is missing from the project's generated env file.

Targets the real Shinkofa-Vault (SOPS/age): `mappings/<project>.yaml` declares
`ENV_VAR_NAME: secret_key`, `envs/<project>.env` is the generated injection
source. The hook checks that every mapped ENV_VAR_NAME is a key in the env file.
It reads key NAMES only, never secret values (Confidentiality.md).

Cross-platform: the hook reads files (no CLI shelled out), so this suite runs on
Windows and Linux alike — no PATH stub, no skipif.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-deploy-vault-check.py"

DEPLOY = {"tool_name": "Bash", "tool_input": {"command": "docker compose up -d"}}


def _make_repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    return repo


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "Shinkofa-Vault"
    (vault / "mappings").mkdir(parents=True)
    (vault / "envs").mkdir(parents=True)
    return vault


def _mapping(vault: Path, stem: str, env_vars: list[str]) -> None:
    body = "# comment line\n" + "".join(f"{v}: {v.lower()}_key\n" for v in env_vars)
    (vault / "mappings" / f"{stem}.yaml").write_text(body, encoding="utf-8")


def _env(vault: Path, stem: str, keys: list[str]) -> None:
    body = "# generated\n" + "".join(f"{k}=somevalue-{k}\n" for k in keys)
    (vault / "envs" / f"{stem}.env").write_text(body, encoding="utf-8")


def _run(payload: dict, *, cwd: Path, vault: Path | None, project: str | None = None):
    env = {**os.environ}
    if vault is not None:
        env["SHINKOFA_VAULT_DIR"] = str(vault)
    if project is not None:
        env["SHINKOFA_PROJECT"] = project
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
        cwd=str(cwd),
        env=env,
    )


# --- Non-triggers (silent) ---------------------------------------------------


def test_silent_on_non_deploy_command(tmp_path):
    repo = _make_repo(tmp_path, "kobo")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL"])
    _env(vault, "kobo", [])  # missing, but command is not a deploy
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    r = _run(payload, cwd=repo, vault=vault, project="kobo")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_empty_stdin():
    r = subprocess.run([sys.executable, str(HOOK)], input=b"", capture_output=True, timeout=10)
    assert r.returncode == 0


def test_silent_when_vault_absent(tmp_path):
    repo = _make_repo(tmp_path, "kobo")
    r = _run(DEPLOY, cwd=repo, vault=tmp_path / "nonexistent", project="kobo")
    assert r.returncode == 0


def test_silent_when_no_mapping_for_project(tmp_path):
    """Project not vault-mapped (covered-via-Infra / clean) → pass."""
    repo = _make_repo(tmp_path, "michi-shinkofa")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL"])  # different project
    r = _run(DEPLOY, cwd=repo, vault=vault, project="michi-shinkofa")
    assert r.returncode == 0


def test_silent_when_mapping_but_no_env_generated(tmp_path):
    """Mapping exists but no envs/<stem>.env (covered-via-Infra) → pass."""
    repo = _make_repo(tmp_path, "koshin")
    vault = _make_vault(tmp_path)
    _mapping(vault, "koshin", ["DEEPSEEK_API_KEY"])  # no koshin.env generated
    r = _run(DEPLOY, cwd=repo, vault=vault, project="koshin")
    assert r.returncode == 0


# --- Triggers (BLOCK on missing) --------------------------------------------


def test_blocks_when_mapped_var_missing_from_env(tmp_path):
    repo = _make_repo(tmp_path, "kobo")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL", "STRIPE_KEY"])
    _env(vault, "kobo", ["DATABASE_URL"])  # STRIPE_KEY absent
    r = _run(DEPLOY, cwd=repo, vault=vault, project="kobo")
    assert r.returncode == 2, f"expected BLOCK, got {r.returncode}, stderr={r.stderr!r}"
    assert b"STRIPE_KEY" in r.stderr
    assert b"BLOCKED" in r.stderr


def test_passes_when_all_mapped_vars_present(tmp_path):
    repo = _make_repo(tmp_path, "kobo")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL", "REDIS_URL"])
    _env(vault, "kobo", ["DATABASE_URL", "REDIS_URL"])
    r = _run(DEPLOY, cwd=repo, vault=vault, project="kobo")
    assert r.returncode == 0
    assert r.stderr == b""


def test_blocks_on_systemctl_restart(tmp_path):
    repo = _make_repo(tmp_path, "kobo")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["API_TOKEN"])
    _env(vault, "kobo", [])
    payload = {"tool_name": "Bash", "tool_input": {"command": "ssh vps systemctl restart kobo"}}
    r = _run(payload, cwd=repo, vault=vault, project="kobo")
    assert r.returncode == 2
    assert b"API_TOKEN" in r.stderr


def test_multi_service_repo_checks_all_mappings(tmp_path):
    """A repo with several service mappings (michi-niwa-bot/-web) checks each."""
    repo = _make_repo(tmp_path, "michi-niwa")
    vault = _make_vault(tmp_path)
    _mapping(vault, "michi-niwa-bot", ["BOT_TOKEN"])
    _env(vault, "michi-niwa-bot", ["BOT_TOKEN"])
    _mapping(vault, "michi-niwa-web", ["WEB_SECRET"])
    _env(vault, "michi-niwa-web", [])  # WEB_SECRET missing
    r = _run(DEPLOY, cwd=repo, vault=vault, project="michi-niwa")
    assert r.returncode == 2
    assert b"WEB_SECRET" in r.stderr


def test_prefix_match_does_not_overreach(tmp_path):
    """Project 'michi-shinkofa' must not match 'michi-niwa-*' mappings."""
    repo = _make_repo(tmp_path, "michi-shinkofa")
    vault = _make_vault(tmp_path)
    _mapping(vault, "michi-niwa-bot", ["BOT_TOKEN"])
    _env(vault, "michi-niwa-bot", [])  # would block if wrongly matched
    _mapping(vault, "michi-shinkofa", ["APP_KEY"])
    _env(vault, "michi-shinkofa", ["APP_KEY"])
    r = _run(DEPLOY, cwd=repo, vault=vault, project="michi-shinkofa")
    assert r.returncode == 0, f"overreach into michi-niwa, stderr={r.stderr!r}"


def test_project_resolved_from_repo_dir_name(tmp_path):
    """Without SHINKOFA_PROJECT, project = repo dir name lowercased."""
    repo = _make_repo(tmp_path, "Kobo")
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL"])
    _env(vault, "kobo", [])
    r = _run(DEPLOY, cwd=repo, vault=vault, project=None)
    assert r.returncode == 2
    assert b"DATABASE_URL" in r.stderr


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _real_repo(path: Path, name: str) -> Path:
    """Create a real git repo needed for worktree tests."""
    repo = path / name
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@test.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_project_name_stable_in_worktree(tmp_path):
    # Bug (pre-fix): find_repo_root().name returned the worktree dir name
    # ("Kobo-feature") instead of the main repo name ("Kobo"), so the hook
    # looked for a mapping named "kobo-feature" that never existed and silently
    # passed through — leaving the deploy unguarded.
    repo = _real_repo(tmp_path, "Kobo")
    wt = tmp_path / "Kobo-feature"
    _git(["worktree", "add", "-b", "feature", str(wt)], repo)
    vault = _make_vault(tmp_path)
    _mapping(vault, "kobo", ["DATABASE_URL"])
    _env(vault, "kobo", [])  # missing → should BLOCK even from worktree
    r = _run(DEPLOY, cwd=wt, vault=vault, project=None)
    assert r.returncode == 2, (
        "hook must resolve 'kobo' (main repo) not 'kobo-feature' (worktree dir)"
    )
    assert b"DATABASE_URL" in r.stderr
