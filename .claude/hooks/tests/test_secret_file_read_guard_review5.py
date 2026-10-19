"""Fifth round (2026-10-18): the exemptions judged the TOKEN, not what reaches standard output.

`echo "$(cat .env)"` passed (a space inside the substitution made it "prose"), `cp .env /dev/stdout`
displays in one step, `source .env; env` dumps what was loaded, `--env-file` was granted whatever the
program prints. Also the daily false positives: a grep/rg/jq PATTERN is not a path. Paths are invented.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "guards" / "secret-file-read-guard.py"


def _run(tool: str, tool_input: dict) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


def _bash(command: str) -> int:
    return _run("Bash", {"command": command})


REFUSED = [
    'echo "$(cat .env)"', 'echo "`cat .env`"', "printf '%s' \"$(cat .env)\"", 'printf "%s\\n" "$(< .env)"',
    "cp .env /dev/stdout", "cp .env /dev/stderr", "mv .env /dev/stdout", "cp .env /proc/self/fd/1", "cp .env CON",
    "source .env; env", "source .env && printenv", ". .env; set", "source .env; export -p",
    "docker run --env-file .env alpine env", "docker compose --env-file .env run app env",
    "docker compose --env-file .env config", "docker compose --env-file .env exec app sh",
    "uv run --env-file .env python -c \"import os;print(os.environ)\"",
    "xargs -a .env echo", "git add -f .env", "git commit -m x .env", "git stash push .env",
    "sops -d secrets.sops.yaml", "sops decrypt .env.enc", "gpg -d .env.gpg", "age -d -i key.txt secrets.age",
    "cat ~/.codex/auth.json", "cat ~/.config/gcloud/application_default_credentials.json",
    "cat .vault-token", "cat .dockercfg", "cat ~/.claude.json", "cat .netrc_old", "cat my.env.backup1",
    "bun -e \"console.log(require('fs').readFileSync('.env','utf8'))\"",
    "bash -c \"sh -c 'bash -c \\\"cat .env\\\"'\"",
]

ALLOWED = [
    'grep -rn "process.env" src/', "rg process.env src", 'rg -n "\\.env" .', 'grep -n ".env" .gitignore',
    "jq .env package.json", "jq .scripts.env package.json", "grep -A 3 process.env src/app.js",
    'node -e "const x = process.env; console.log(Object.keys(x).length)"',
    "cat src/.env.js", "cat src/.env.mjs", "gh issue create --title .env-loading",
    "docker compose --env-file .env up -d", "docker compose --env-file .env build",
    "docker compose --env-file=.env down", "sudo docker compose --env-file .env up -d",
    "set -a; source .env; set +a", "source .env && npm test", "node --env-file=.env app.js",
    "uv run --env-file .env pytest", "git rm --cached .env", "git commit -m 'retire .env du depot'",
    "echo .env >> .gitignore", "grep -c API_KEY .env", "grep -q API_KEY .env && echo present",
    "ls -la .env", "cp .env.example .env", "cp .env .env.disabled",
]


@pytest.mark.parametrize("command", REFUSED)
def test_a_form_that_shows_or_ships_the_secret_is_refused(command):
    assert _bash(command) == 2, command


@pytest.mark.parametrize("command", ALLOWED)
def test_daily_work_and_listed_uses_still_pass(command):
    assert _bash(command) == 0, command
