"""deploy/post-deploy-fact.py — PostToolUse: le fait « mise en ligne non contrôlée » arrive dès la mise en ligne, avant que Takumi écrive.

Jay 2026-11-24 (audit réactif/anticipatif, conversion n°3): `online-claim-check` (Stop) attrape « c'est en ligne » après que Jay l'a lu. Le
fait existe plus tôt: dès que la commande de mise en ligne s'est exécutée. Ce hook le dépose dans le contexte juste après le résultat de
la commande, donc avant la phrase suivante. Mêmes commandes, même verdict. Le garde de fin de message reste le filet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "deploy" / "post-deploy-fact.py"


def _lancer(commande: str, tmp_path: Path, outil: str = "Bash", evenement: str = "PostToolUse"):
    charge = {"hook_event_name": evenement, "tool_name": outil, "session_id": "s", "tool_input": {"command": commande},
              "tool_response": {"stdout": "ok"}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(charge).encode(), capture_output=True, timeout=30, cwd=tmp_path)


def _contexte(r) -> str:
    for ligne in r.stdout.decode("utf-8", "replace").splitlines():
        try:
            return json.loads(ligne)["hookSpecificOutput"]["additionalContext"]
        except (ValueError, KeyError, TypeError):
            continue
    return ""


def test_une_mise_en_ligne_depose_le_fait_non_controle(tmp_path):
    for commande in ("ssh vps 'cd /home/ubuntu/apps/Kobo && docker compose up -d'", "docker compose up -d --build", "./deploy.sh"):
        r = _lancer(commande, tmp_path)
        texte = _contexte(r)
        assert r.returncode == 0 and "NON CONTRÔLÉE" in texte and "web_check" in texte, commande
        assert "ne dis pas" in texte.lower()


def test_une_commande_ordinaire_ne_depose_rien(tmp_path):
    for commande in ("ls -la", "git status", "python -m pytest -q", 'git commit -m "docs: noter docker compose up"'):
        assert _contexte(_lancer(commande, tmp_path)) == "", commande


def test_un_autre_outil_ou_un_autre_evenement_ne_depose_rien(tmp_path):
    assert _contexte(_lancer("docker compose up -d", tmp_path, outil="Read")) == ""


def test_une_entree_illisible_ne_casse_rien(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=30, cwd=tmp_path)
    assert r.returncode == 0
