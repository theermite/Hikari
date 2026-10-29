#!/usr/bin/env python3
"""Sonde des capacités — SessionStart. Annonce, ne bloque jamais.

Une règle qui exige un outil absent produit une déclaration fausse. Au démarrage, la sonde dit ce qui
est déclaré, refusé ou non vérifiable parmi les capacités que les règles supposent (registre:
`.claude/rules-ondemand/capacites.json`), avec la dégradation à appliquer. Limite: elle ne voit pas les outils
réellement chargés — voir `lib/capacites.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

import capacites  # noqa: E402
from common import find_repo_root  # noqa: E402


def build_decision(racine: Path, home: Path) -> dict:
    registre = json.loads((racine / ".claude/rules-ondemand/capacites.json").read_text(encoding="utf-8")).get("capacites", [])
    commandes = {c for cap in registre for c in cap.get("preuve", {}).get("commandes", []) if shutil.which(c)}
    illisibles = capacites.configurations_illisibles(home, racine)
    diagnostic = capacites.diagnostiquer(registre, capacites.serveurs_mcp(home, racine),
                                         capacites.outils_refuses(home, racine), commandes, illisibles,
                                         entrypoint=os.environ.get("CLAUDE_CODE_ENTRYPOINT", ""))
    texte = capacites.resume(diagnostic, illisibles)
    return {"systemMessage": texte,
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texte}}


def main() -> None:
    try:
        print(json.dumps(build_decision(find_repo_root(), Path.home()), ensure_ascii=False))
    except Exception as erreur:  # noqa: BLE001 — une sonde ne casse jamais un démarrage
        print(f"[DEBUG][capacites-check] {type(erreur).__name__}: {erreur}", file=sys.stderr)
        print("{}")


if __name__ == "__main__":
    main()
