"""Sixth round (2026-10-18): the four points of the fourth review.

1. A quoted path with a SPACE ("D:/My Projects/app/.env") was taken for a sentence.
2. `source .env; echo $DB_PASSWORD` shows one loaded variable.
3. `node --env-file=.env -p process.env` was refused before the fifth round and passed after it.
4. The value of `-m` / `--notes` / `--title` was skipped for EVERY program (`git show -m HEAD:.env`).
Paths are invented; the hook only judges the text of the command.
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
    'cat "D:/My Projects/app/.env"', 'type "C:\\Users\\x\\OneDrive - Personal\\app\\.env"',
    'head -n 20 "/c/Users/x/OneDrive - Perso/site/.env.production"', "cat 'D:/Dev Projects/x/.ssh/id_ed25519'",
    'cat "My Apps/.env"',
    "source .env; echo $DB_PASSWORD", "source .env && echo $DATABASE_URL", "printf '%s\\n' \"$TOKEN\"; . .env",
    "set -a && source .env && set +a && echo $TOKEN",
    "node --env-file=.env -p process.env", 'node --env-file=.env -p "process.env.API_KEY"',
    "bun --env-file=.env -p process.env",
    "git show -m HEAD:.env", "less -m .env", "tail --notes .env", "grep -f .env other.txt",
]

ALLOWED = [
    "uv run --env-file .env pytest -p no:cacheprovider", "node --env-file=.env app.js",
    "git commit -m 'retire .env du depot'", "git tag -m 'sans .env' v1", "gh pr create --title t --body 'le .env reste hors git'",
    "source .env && npm test", "source .env && echo done", "set -a; source .env; set +a",
    'cat "D:/My Projects/app/README.md"', 'git commit -m "mise a jour de la doc"',
]


@pytest.mark.parametrize("command", REFUSED)
def test_the_four_points_are_refused(command):
    assert _bash(command) == 2, command


@pytest.mark.parametrize("command", ALLOWED)
def test_the_fixes_do_not_break_daily_work(command):
    assert _bash(command) == 0, command
