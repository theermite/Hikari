"""deploy/smoke-test-required.py — le rappel « mise en ligne sans test de fumée » ne prend pas une note pour une mise en ligne.

Relecture 7.7.0 (2026-11-01) : un fichier d'essai dont le texte contenait `ssh vps ... docker compose up` a
déclenché le rappel alors que rien n'avait été mis en ligne. Le garde lisait le texte brut de la commande ;
il lit maintenant les commandes réelles (lib/deploy_reader.py, partagé avec le garde d'audit).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "deploy" / "smoke-test-required.py"


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _bash(repo: Path, session: str, command: str) -> str:
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": session,
               "tool_input": {"command": command}, "tool_response": {}}
    done = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20, cwd=str(repo))
    return (done.stdout + done.stderr).decode("utf-8", "replace")


def _warned(repo: Path, session: str, first: str) -> bool:
    outputs = [_bash(repo, session, first)] + [_bash(repo, session, f"ls -la dossier{i}") for i in range(4)]
    return any("smoke test" in out for out in outputs)


def test_a_real_deploy_without_smoke_test_still_warns(tmp_path):
    assert _warned(_repo(tmp_path), "s-real", "docker compose up -d")
    assert _warned(_repo(tmp_path), "s-ctx", "docker --context vps compose up -d")


def test_a_note_that_only_quotes_a_deploy_does_not_warn(tmp_path):
    repo = _repo(tmp_path)
    assert not _warned(repo, "s-echo", "echo 'ssh vps docker compose up -d'")
    assert not _warned(repo, "s-commit", "git commit -m 'doc: docker compose up reste à documenter'")
    assert not _warned(repo, "s-heredoc", "cat > note.md <<'EOF'\nssh vps 'docker compose up -d'\nEOF")
