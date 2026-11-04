#!/usr/bin/env python3
"""Clear-recap check — Stop hook. Ce que Takumi dit à Jay se comprend sans avoir vu le code.

Reproche de Jay (2026-11-01) : « les récapitulatifs et les rapports sont encore bien trop techniques, ça
m'embrouille. » Décision de Jay (2026-11-04) : le gabarit imposé (L'essentiel / Pour toi / Gains et limites /
Ta question) faisait réécrire chaque réponse refusée et alourdissait les réponses simples. La forme est libre.

Un seul contrôle (lib/clear_language.py) : le vocabulaire que Jay n'a pas ne s'accumule pas (trois termes
internes distincts, ou un numéro de commit). Une fois par tour (stop_hook_active), lit last_assistant_message.
Limite écrite : le garde ne lit pas le sens ; Jay juge le reste (il le dit, la cause se corrige).
Le début du message de refus est lu par scripts/garde_lib/journaux.py (MARQUE_REECRITURE) : ne pas le changer.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from clear_language import problems  # noqa: E402
from common import block, pass_through, read_hook_input  # noqa: E402


def message(found: list[tuple[str, str]]) -> str:
    details = " ; ".join(detail for _, detail in found)
    return (
        "Jay n'a pas le contexte de ce que tu viens de faire : il n'a pas vu les commandes, il ne connaît pas ton "
        f"vocabulaire. Ce qui manque : {details}. Reformule en mots de tous les jours, court, sans nom de commande "
        "ni numéro de commit : ils vont dans le rapport. La forme est libre (liste, tableau, emojis mesurés)."
    )


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    found = problems(reply) if isinstance(reply, str) else []
    if found:
        block(message(found))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[clear-recap-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
