#!/usr/bin/env python3
"""Plan-incomplet check — Stop. « J'annonce sans faire » lu sur un FAIT: la liste de tâches du tour a des étapes ouvertes.

Jay 2026-11-24 (audit réactif/anticipatif): le garde `announce-without-doing-check` devine à partir de mots du futur. Ici le fait est dans le
journal: la liste tenue pendant le tour (`lib/plan_tour.py`) a des étapes non terminées, le tour finit sans `wrap_up`, et la réponse ne
demande rien à Jay. Alors un rappel pour le tour suivant (jamais un refus: la réponse est déjà lue). Limites écrites: il ne voit que les
tours qui tiennent une liste de tâches ; le garde lexical reste le filet des autres tours tant qu'une mesure ne prouve pas qu'il est inutile.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import pass_through, rappel, read_hook_input  # noqa: E402
from plan_tour import plan_du_tour, tour_incomplet  # noqa: E402


def message(restantes: list[str]) -> str:
    etapes = " ; ".join(f"« {e} »" for e in restantes[:5])
    return (f"Ton tour s'est terminé alors que ta liste de tâches a encore {len(restantes)} étape(s) ouverte(s) : {etapes}, sans wrap_up. "
            "Si l'étape est à toi, fais-la dans ce tour et clos la liste ; si elle attend un événement ou Jay, dis lequel dans la réponse.")


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reponse = data.get("last_assistant_message")
    plan = plan_du_tour(str(data.get("transcript_path") or ""))
    if isinstance(reponse, str) and tour_incomplet(plan, reponse):
        rappel("plan", message(plan.restantes))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[plan-incomplet-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
