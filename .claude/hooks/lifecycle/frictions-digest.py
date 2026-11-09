#!/usr/bin/env python3
"""Les frictions remontent au démarrage de Kata — SessionStart. Annonce, ne bloque jamais.

Jay, 2026-11-09: quand un garde-fou refuse à tort, Takumi note une ligne (`scripts/friction-note.py`), et Jay
la retrouve en revenant dans Kata. Ce hook dit, une fois par ligne nouvelle, combien de refus et de notes
attendent et lesquels reviennent le plus. Il se tait s'il n'y a rien de neuf, et hors de Kata (ailleurs ce
serait du bruit, comme pour les notes globales).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

import friction_log  # noqa: E402
from common import find_repo_root  # noqa: E402

DEPOT_PORTEUR = "Kata"


def build_decision(journal: Path, vu: Path) -> dict:
    """{} sans nouveauté; sinon le résumé, et le nombre de lignes lues est mémorisé."""
    evenements = friction_log.lire(journal)
    try:
        deja = int(vu.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        deja = 0
    nouveaux = evenements[deja:] if deja <= len(evenements) else evenements
    if not nouveaux:
        return {}
    vu.parent.mkdir(parents=True, exist_ok=True)
    vu.write_text(str(len(evenements)), encoding="utf-8")
    texte = friction_log.resume(nouveaux)
    return {"systemMessage": texte, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texte}}


def main() -> None:
    try:
        racine = find_repo_root()
        if racine.name != DEPOT_PORTEUR:
            print("{}")
            return
        vu = racine / ".claude" / "state" / "frictions-vues"
        print(json.dumps(build_decision(friction_log.journal_path(), vu), ensure_ascii=False))
    except Exception as erreur:  # noqa: BLE001 — un rappel ne casse jamais un démarrage
        print(f"[DEBUG][frictions-digest] {type(erreur).__name__}: {erreur}", file=sys.stderr)
        print("{}")


if __name__ == "__main__":
    main()
