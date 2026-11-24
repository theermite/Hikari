#!/usr/bin/env python3
"""Decision-recoupée check — Stop. Ne pas présenter à Jay comme « ouverte » une décision sans l'avoir recoupée.

Reproche de Jay (2026-11-24, deux fois dans la journée): « La plupart de ces questions, j'y ai déjà répondu. » J'avais repris la
liste « décisions à trancher » de la carte (un instantané du 19/11) sans la comparer à la reprise du 20/11, à la doctrine ni à
la mémoire, et je la lui avais redonnée comme à décider. Famille du défaut: affirmer depuis UNE source, sans la recouper
avec celles qui disent la suite (même famille que « la fiche dit non fusionné » le même jour). Un souvenir ne l'avait pas
empêché (trois existent): d'où ce garde.

Le garde ne juge pas le contenu. Il constate deux faits: la réponse présente des décisions ou des questions comme ouvertes pour
Jay, ET aucun outil du tour n'a lu une source de décisions (reprise, doctrine, mémoire, fiche, notes de Jay, confrontation).
Alors il laisse un rappel pour le tour suivant (jamais un refus: la réponse est déjà lue).
Limites écrites: lexical (une présentation tournée autrement passe); une lecture d'un fichier de décisions qui ne concerne pas
la question compte comme recoupement; il n'agit qu'après coup, il ne remplace pas le geste de recouper AVANT de poser la question.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import decisions as dec  # noqa: E402
from common import pass_through, rappel, read_hook_input  # noqa: E402
from turn_log import tool_runs  # noqa: E402

MESSAGE = (
    "Tu présentes à Jay des décisions ou des questions comme ouvertes, sans avoir recoupé dans ce tour ce qui est déjà "
    "décidé (reprise du projet, doctrine, mémoire, fiche, notes de Jay). Une liste de la carte ou d'un rapport est un "
    "instantané daté, pas l'état présent. Avant de lui poser une question, recoupe : si la réponse est déjà écrite, retire "
    "la question et dis où elle est tranchée. Le comment est à Takumi, seul le quoi est à Jay."
)

_OUVERTES = re.compile(
    r"(?i)\b(?:tes d[ée]cisions?|d[ée]cisions? (?:en attente|[àa] (?:prendre|trancher)|ouvertes?)|[àa] trancher|"
    r"questions? (?:ouvertes?|en attente)|reste(?:nt)? [àa] (?:toi|ta d[ée]cision)|(?:question|decision) Q\d)\b|(?<![\w])Q[1-9]\b(?!\s*20\d\d)"
)
_QUOTED = re.compile("«[^»]*»|“[^”]*”")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
# Une source qui dit ce qui est déjà décidé: chemin ou commande qui la nomme.
_SOURCE = re.compile(r"(?i)reprise|doctrine|d[ée]cision|05-m[ée]moire|memory\.md|notes-jay|confrontation|\bkata\.md\b|souvenir")


def presente_des_decisions_ouvertes(reply: str) -> bool:
    if not isinstance(reply, str):
        return False
    return bool(_OUVERTES.search(_QUOTED.sub(" ", _FENCE.sub(" ", reply))))


def a_recoupe(runs) -> bool:
    return any(_SOURCE.search(f"{r.path} {r.command}") for r in runs)


def ids_fermes_presentes_comme_ouvertes(reply: str, registre: list[dict]) -> list[str]:
    """Quand la réponse cite des identifiants du registre, le registre tranche: ceux qui sont déjà tranchés ou remplacés."""
    statuts = {x["id"]: x.get("statut") for x in registre}
    return sorted({i for i in dec._ID_DANS_TEXTE.findall(reply or "") if statuts.get(i) in ("tranchee", "remplacee")})


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    if not presente_des_decisions_ouvertes(reply):
        pass_through()
    fermes = ids_fermes_presentes_comme_ouvertes(reply, dec.charger())
    if fermes:
        rappel("decisions", f"Tu présentes comme à décider des décisions que le registre dit DÉJÀ tranchées : {', '.join(fermes)}. "
                            "Retire-les et dis où elles sont tranchées.")
    if not dec._ID_DANS_TEXTE.search(reply) and not a_recoupe(tool_runs(data.get("transcript_path") or "")):
        rappel("decisions", MESSAGE)  # sans identifiant, rien ne se vérifie par le registre: on exige le recoupement
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[decision-recoupee-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
