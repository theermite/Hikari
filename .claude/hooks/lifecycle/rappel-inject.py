#!/usr/bin/env python3
"""Rappel inject — UserPromptSubmit, compagnon de tous les gardes de fin de message (Stop).

Un garde de Stop ne refuse plus (Jay 2026-11-24: la réécriture lui montrait deux fois la même réponse): il garde un
rappel (`lib/rappels.py`), et CE crochet le dit au prochain message de Jay, une seule fois.

Sortie standard = contexte ajouté pour le modèle. Toute erreur: sortie 0 muette (jamais casser le message de Jay).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from common import read_hook_input  # noqa: E402
from rappels import a_dire  # noqa: E402


def main() -> None:
    try:
        _, data = read_hook_input()
        messages = a_dire(str(data.get("session_id") or "") or None)
        if messages:
            sys.stdout.write("[RAPPEL — TA DERNIÈRE FIN DE MESSAGE]\n" + "\n".join(f"- {m}" for m in messages)
                             + "\nNe réécris pas ta réponse précédente : applique cette règle dès ce tour.\n")
            sys.stdout.flush()
    except Exception:  # noqa: BLE001 — never break Jay's prompt
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
