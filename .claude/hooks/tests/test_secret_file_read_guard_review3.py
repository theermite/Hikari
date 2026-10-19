"""Third independent review (2026-10-18): the read guard was lexical and the bypasses were cheap.

Each command below DISPLAYS a secret file by a form the first version did not see. Paths are
invented; nothing is read (the hook only judges the text of the command).
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


def _read(path: str) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


REFUSED_COMMANDS = [
    "cat .en?", "cat .en*", "cat .[e]nv", "cat .e''nv", "head -c 400 .env*",
    "sudo cat .env", "env -i cat .env", "command cat .env", "busybox cat .env", "nohup cat .env",
    "f=.env; cat \"$f\"", "f=.env && cat ${f}",
    "dd if=.env", "git show HEAD:.env", "git diff --no-index /dev/null .env", "diff .env other",
    "vim -es .env", "openssl rsa -in server.key -text", "ssh-keygen -y -f id_ed25519",
    "powershell -c 'gc .env'", "pwsh -Command \"Get-Content .env\"", "cmd /c type .env",
    "cat ~/.kube/config", "cat .envrc", "cat .env-prod", "cat .env_local",
    "cat secrets.json", "cat service-account.json", "cat terraform.tfstate", "cat app.env.bak",
    "cat server.key.bak", "cat .env~",
]

ALLOWED_COMMANDS = [
    "cat .env.example", "ls -la .env", "docker compose --env-file .env up -d", "source .env",
    "cp .env.example .env", "grep -q TOKEN .env", "git show HEAD:README.md", "diff a.txt b.txt",
    "sudo systemctl restart nginx", "env -i python3 script.py", "bash -c 'echo hello'",
    "cat .envrc.example", "cat package.json",
]


@pytest.mark.parametrize("command", REFUSED_COMMANDS)
def test_the_command_that_displays_a_secret_is_refused(command):
    assert _bash(command) == 2, command


@pytest.mark.parametrize("command", ALLOWED_COMMANDS)
def test_the_command_that_only_uses_or_names_it_passes(command):
    assert _bash(command) == 0, command


@pytest.mark.parametrize("path", [
    "/repo/.envrc", "/repo/.env-prod", "/repo/.env_local", "/repo/app.env.bak", "/x/server.key.bak",
    "/repo/.env~", "/repo/.env.", "/repo/.env::$DATA", "/home/u/.kube/config", "/x/secrets.json",
    "/x/service-account.json", "/x/terraform.tfstate",
])
def test_the_neighbour_file_names_are_refused_on_read(path):
    assert _read(path) == 2, path


@pytest.mark.parametrize("path", ["/repo/.envrc.example", "/home/u/.ssh/config", "/repo/package.json"])
def test_unrelated_names_stay_readable(path):
    assert _read(path) == 0, path
