#!/usr/bin/env python3
"""Sonde d'entretien — SessionStart. Annonce quand la passe hebdomadaire manque, ne bloque jamais.

POURQUOI ELLE EXISTE. La doctrine (§ 8) promet qu'un contrôle échoue quand le dernier compte
d'entretien a plus de huit jours. `scripts/check-entretien-frais.py` est ce contrôle ; sans
branchement, il ne tourne que si quelqu'un y pense — et la boucle d'entretien n'existe pas.

CE QU'ELLE FAIT. Lance le contrôle au démarrage. À jour : elle se tait (pas de bruit à chaque
session). En retard, sans compte, ou contrôle absent : elle le dit, et nomme la commande.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

from common import find_repo_root  # type: ignore # noqa: E402

CONTROLE = Path("scripts") / "check-entretien-frais.py"


def _annonce(texte: str) -> dict:
    return {
        "systemMessage": texte,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texte},
    }


def build_decision(racine: Path) -> dict:
    """{} quand l'entretien est à jour ; une annonce sinon. Jamais de blocage."""
    script = racine / CONTROLE
    if not script.exists():
        return _annonce(f"[ENTRETIEN] contrôle absent ({CONTROLE.as_posix()}) : la boucle ne garde rien.")
    resultat = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=20
    )
    if resultat.returncode == 0:
        return {}
    return _annonce("[ENTRETIEN] " + resultat.stdout.strip().replace("\n", " "))


def main() -> None:
    try:
        print(json.dumps(build_decision(find_repo_root()), ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — une sonde ne casse jamais un démarrage
        print(f"[DEBUG][entretien-frais-check] {type(error).__name__}: {error}", file=sys.stderr)
        print("{}")


if __name__ == "__main__":
    main()
