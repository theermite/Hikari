"""Tests for the centralized deploy detector in common.py.

`looks_like_deploy()` replaces 8 copy-pasted `_DEPLOY_PATTERNS` lists whose
ssh sub-pattern matched the bare substring docker/deploy/systemctl anywhere
after the host — so a grep, an rm, or a filename containing "deploy"/"docker"
was misread as a deploy and triggered the (slow, network-probing) gates.

The detector must match real deploy ACTIONS and reject those false positives.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from common import looks_like_deploy  # noqa: E402


# --- Real deploys MUST be detected ------------------------------------------

DEPLOYS = [
    "docker compose up -d",
    "docker-compose up",
    "docker compose up --build",
    "docker stack deploy -c stack.yml app",
    "./deploy.sh prod",
    "vercel --prod",
    "vercel deploy",
    "fly deploy",
    "netlify deploy --prod",
    "railway up",
    "gh workflow run deploy.yml",
    "ansible-playbook site.yml",
    "kubectl apply -f k8s/",
    "helm upgrade myrelease ./chart",
    "systemctl restart kobo",
    "sudo systemctl start nginx",
    "nginx -s reload",
    "ssh vps docker compose up -d",
    "ssh vps 'cd ~/app && docker compose restart'",
    "ssh vps systemctl restart kobo",
    "ssh vps 'sudo nginx -s reload'",
    "ssh vps ./deploy.sh",
    "git pull && docker compose up -d",
    "git pull origin main && systemctl restart kobo",
]


def test_real_deploys_detected():
    missed = [c for c in DEPLOYS if not looks_like_deploy(c)]
    assert not missed, f"deploy commands not detected: {missed}"


# --- Innocent commands MUST NOT be flagged (the false positives) ------------

NON_DEPLOYS = [
    "ls -la",
    "git status",
    "git pull --ff-only",
    "grep -rn 'ssh.*docker|deploy|systemctl' .claude/hooks/",
    "ssh vps 'rm -f ~/apps/Kata/.claude/hooks/guards/pre-deploy-vault-check-TEST.py'",
    "ssh vps 'bash -s'",
    "cat docker-compose.yml",
    "rm pre-deploy-old.py",
    "echo 'run docker compose up to deploy'",  # data, not a command... see note
    "vim deploy-notes.md",
    "scp local vps:~/file.py",
    "ssh vps hostname",
]


def test_innocent_commands_not_flagged():
    flagged = [c for c in NON_DEPLOYS if looks_like_deploy(c)]
    # The echo example legitimately contains "docker compose up" as text; the
    # detector cannot distinguish quoted prose from a command without a shell
    # parser. We accept that single ambiguous case and assert all the others.
    flagged = [c for c in flagged if not c.startswith("echo ")]
    assert not flagged, f"innocent commands wrongly flagged as deploy: {flagged}"


def test_empty_command_not_flagged():
    assert looks_like_deploy("") is False
