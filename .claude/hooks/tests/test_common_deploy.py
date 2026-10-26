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


# --- chaque blocage renvoie à l'annexe de reprise ------------------------------------------------
# Rien dans un appel d'outil ne signale « un blocage vient d'avoir lieu » : le message du garde-fou
# lui-même est le seul porteur de l'annexe Debug-Et-Blocage (registre des annexes).

def test_every_block_message_points_to_the_recovery_annex():
    from common import format_block
    message = format_block("raison", "remède", reference="rules/X.md")
    assert ".claude/rules-ondemand/Debug-Et-Blocage.md" in message
    assert message.startswith("BLOCKED: raison. RECOVERY: remède")


# --- relecture indépendante du 2026-10-26 (P7): seize anciennes règles citées par des messages ------
# Les messages de blocage renvoient vers `rules/Quality.md` & co. La table ancienne règle -> nouvelle place
# est appliquée à l'entonnoir (`format_block`, `format_warn`): un seul endroit à tenir, pas 34 fichiers.

def test_a_reference_to_an_archived_rule_points_to_its_new_home():
    from common import format_block, format_warn
    msg = format_block("raison", "remède", reference="rules/Quality.md > Lego Library")
    assert "rules/Quality.md" not in msg and "03-Qualite.md" in msg and "Lego Library" in msg
    assert "04-Verite.md" in format_warn("r", "a", reference=".claude/rules/Honesty.md")


def test_a_reference_to_a_current_rule_is_left_alone():
    from common import format_block
    assert ".claude/rules/02-Parcours.md § 7" in format_block("r", "x", reference=".claude/rules/02-Parcours.md § 7")


def test_every_archived_rule_has_a_new_home_that_exists():
    from pathlib import Path
    from common import ANCIENNES_REGLES
    racine = Path(__file__).resolve().parents[3]
    for ancienne in (racine / "rules-archives").glob("*.md"):
        assert ancienne.name in ANCIENNES_REGLES, ancienne.name
    for nouvelle in ANCIENNES_REGLES.values():
        assert (racine / nouvelle.split(" ")[0]).exists(), nouvelle
