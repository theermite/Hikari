#!/usr/bin/env python3
"""Demande de lecture des annexes — SessionStart. Annonce, ne bloque jamais, n'inscrit rien.

Jay, 2026-11-09: 54 refus d'annexe en 18 séances, chacun coûtant un aller-retour en plein geste. Ce hook nomme
les annexes que presque toute séance requiert (le socle, et celles du code si le projet en est un) et demande de
les lire TOUT DE SUITE, en un seul tour, avant le premier travail.

Il ne livre pas leur texte et n'inscrit rien comme lu. Relecture indépendante du 2026-11-09, confirmée par la
documentation de Claude Code: la sortie d'un hook est plafonnée à 10 000 caractères; au-delà, le modèle ne reçoit
qu'un aperçu d'environ 2 000 caractères et le chemin d'un fichier. Livrer 40 Ko puis inscrire « lu » aurait laissé
passer une règle jamais lue. Le garde des annexes, qui voit les vraies lectures, reste seul juge: si la demande est
ignorée, il refuse comme avant.

Registre: clé `au_demarrage` de `.claude/rules-ondemand/annexes.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

import annexes  # noqa: E402
from common import find_repo_root  # noqa: E402

PLAFOND_HOOK = 10_000  # caractères qu'un hook peut livrer au modèle (documentation Claude Code, 2026-11)


def build_decision(racine: Path, session: str = "") -> dict:
    """La demande de lecture; {} si le registre ne prévoit rien."""
    fichiers = [a["fichier"] for a in annexes.a_precharger(annexes.charger(racine), racine)
                if (Path(racine) / a["fichier"]).is_file()]
    if not fichiers:
        return {}
    texte = ("[ANNEXES À LIRE D'ENTRÉE] Avant le premier travail, lis ces annexes d'un seul coup (appels Read en "
             "parallèle). Le garde des annexes refuserait sinon l'écriture au premier geste:\n"
             + "\n".join(f"- {f}" for f in fichiers))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texte}}


def main() -> None:
    try:
        print(json.dumps(build_decision(find_repo_root()), ensure_ascii=False))
    except Exception as erreur:  # noqa: BLE001 — une demande de lecture ne casse jamais un démarrage
        print(f"[DEBUG][annexes-preload] {type(erreur).__name__}: {erreur}", file=sys.stderr)
        print("{}")


if __name__ == "__main__":
    main()
