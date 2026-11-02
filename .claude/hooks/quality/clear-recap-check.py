#!/usr/bin/env python3
"""Clear-recap check — Stop hook. Ce que Takumi dit à Jay se comprend sans avoir vu le code.

Reproche de Jay (2026-11-01) : « les récapitulatifs et les rapports sont encore bien trop techniques, ça
m'embrouille. Quand il a des questions à me poser, il me parle comme si j'avais le contexte de ce qu'il vient de
coder, alors que c'est noyé dans toutes les commandes. Je veux des récaps et des questions claires, avec le
contexte en langage simple, l'impact, et ce que ça apporte ou non. »

Trois contrôles de FORME (lib/clear_language.py), jamais de justesse :
- une question à Jay s'ouvre sur « L'essentiel », « Pour toi », « Gains et limites » ;
- un long compte rendu s'ouvre sur « L'essentiel » et « Pour toi » ;
- le vocabulaire que Jay n'a pas ne s'accumule pas (trois termes distincts, ou un numéro de commit en plus).

Une fois par tour (stop_hook_active), lit last_assistant_message, ouvre la porte sur tout ce qui est illisible.
Limite écrite : un texte peut porter les trois titres et rester obscur ; le garde ne lit pas le sens, il oblige à
écrire le contexte et refuse le jargon courant. Jay juge le reste (il le dit, la cause se corrige).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from clear_language import TEMPLATE, problems  # noqa: E402
from common import block, pass_through, read_hook_input  # noqa: E402


def message(found: list[tuple[str, str]]) -> str:
    details = " ; ".join(detail for _, detail in found)
    return (
        "Jay n'a pas le contexte de ce que tu viens de faire : il n'a pas vu les commandes, il ne connaît pas ton "
        f"vocabulaire. Ce qui manque : {details}. Réécris ta réponse sous cette forme :\n{TEMPLATE}\n"
        "Pas de nom de fichier, de commande ni de numéro de commit dans ces lignes : ils vont dans le rapport."
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
