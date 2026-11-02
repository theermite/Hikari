"""Onzième tour (2026-11-01) : un message qui exécute la lecture d'un fichier de secrets.

La limite écrite le 2026-10-19 (`git commit -m "$(cat .env)"` laissé passer) ne se ferme pas par une analyse
générale des substitutions : trois essais larges avaient bloqué des commits ordinaires. Elle se ferme sur
UNE condition étroite : la valeur du message contient à la fois une substitution vivante ET le nom d'un
fichier de secrets. Un message sans substitution, ou avec une substitution qui ne nomme aucun secret
(`$(date)`, `$(cat <<'EOF' ... EOF)`), reste libre.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "guards" / "secret-file-read-guard.py"


def _bash(command: str) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


REFUSED = [
    'git commit -m "$(cat .env)"',
    'git commit -q -m "fix: x" -m "$(cat .env.production)"',
    'gh pr create --title "$(head -1 .env)" --body x',
    'git commit -m "note `cat id_rsa`"',
    'git tag -m "$(cat server.key)" v1',
]

PASSED = [
    "git commit -m 'retire .env du depot'",
    'git commit -m "mise a jour du $(date +%F)"',
    "git commit -F - <<'EOF'\nfix(hooks): refuse -m \"$(cat .env)\"\nEOF",
    'gh pr create --title "fix: y" --body "$(cat <<\'EOF\'\n- notes\nEOF\n)"',
    "git commit -m \"$(cat <<'EOF'\nfix(config): read DATABASE_URL in dev\nEOF\n)\"",
]


@pytest.mark.parametrize("command", REFUSED)
def test_a_message_that_runs_a_read_of_a_secret_file_is_refused(command):
    assert _bash(command) == 2, command


@pytest.mark.parametrize("command", PASSED)
def test_ordinary_messages_stay_free(command):
    assert _bash(command) == 0, command
