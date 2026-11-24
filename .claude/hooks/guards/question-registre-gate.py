#!/usr/bin/env python3
"""Question-registre gate — PreToolUse sur AskUserQuestion. On ne pose pas à Jay une décision déjà tranchée.

Jay 2026-11-24: « La plupart de ces questions, j'y ai déjà répondu. » La porte est AVANT la question: le geste est refusé, Jay ne
voit rien. Elle ne juge pas le sens, elle compare au registre des décisions (`lib/decisions.py`):
  1. la question nomme ou redit une décision tranchée ou remplacée : refusée, avec la réponse et sa source ;
  2. elle nomme une décision de Takumi (le comment) : refusée, ce n'est pas la question de Jay ;
  3. elle ne cite l'identifiant d'aucune décision OUVERTE de Jay : refusée, avec la commande qui l'enregistre d'abord ;
  4. sinon elle passe. Sans registre lisible, la porte s'ouvre (elle ne devine pas).
Limites écrites: citer l'identifiant d'une décision ouverte sans rapport avec la question la fait passer (elle garantit la forme
et l'absence d'une décision close redite, pas le sens). Elle ne voit que l'outil de question. Une question écrite en prose dans le chat n'est pas refusée avant que Jay
la lise (le garde de fin de message la signale après coup, voir decision-recoupee-check).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import decisions as dec  # noqa: E402
from common import block, pass_through, read_hook_input  # noqa: E402


def texte_des_questions(donnees: dict) -> str:
    entree = donnees.get("tool_input") or {}
    morceaux = []
    for q in entree.get("questions") or []:
        if isinstance(q, dict):
            morceaux += [str(q.get("question") or ""), str(q.get("header") or "")]
            morceaux += [f"{o.get('label', '')} {o.get('description', '')}" for o in q.get("options") or [] if isinstance(o, dict)]
    return "\n".join(morceaux)


_ARRET_NON_DECISION = re.compile(r"(?im)^[ \t>*\-\W]{0,12}\[ARR[E\u00ca]T\]\W{0,3}[ \t]*(?:secret|blocage|tiers|sortant)[ \t]*:[ \t]*\S+(?:[ \t]+\S+){2,}")


def _cites(texte: str, registre: list[dict]) -> set[str]:
    return set(dec._ID_DANS_TEXTE.findall(texte)) & {x["id"] for x in registre}


def verdict(texte: str, registre: list[dict]) -> str | None:
    """Le message de refus, ou None si la question peut etre posee."""
    trouvees = dec.trouver(texte, registre)
    citees = _cites(texte, registre)
    ouverte_citee = any(x["id"] in citees and x.get("qui") == "jay" and x.get("statut") in ("ouverte", "a_recouper") for x in registre)
    for x in trouvees:
        # un identifiant OUVERT cite l'emporte sur les mots d'une decision tranchee (collision lexicale, relecture du 2026-11-24):
        # seul l'identifiant explicite d'une tranchee refuse alors.
        if x.get("statut") in ("tranchee", "remplacee") and (x["id"] in citees or not ouverte_citee):
            return (f"Cette question est d\u00e9j\u00e0 tranch\u00e9e : {x['id']} ({x['date']}) \u2014 {x.get('reponse') or 'remplac\u00e9e par ' + str(x.get('remplace_par'))}. "
                    f"Source : {x['source']}. Ne la pose pas ; si tu crois que la d\u00e9cision a chang\u00e9, cite ce qui a chang\u00e9.")
    for x in trouvees:
        # meme precedence que pour les tranchees: les MOTS d'une decision de Takumi ne refusent pas une question qui cite
        # une decision ouverte de Jay ; seul l'identifiant explicite le fait (relecture 4116a6d, remarque 2)
        if x.get("qui") == "takumi" and (x["id"] in citees or not ouverte_citee):
            return (f"{x['id']} est une d\u00e9cision de Takumi (le comment), pas une question pour Jay : d\u00e9cide, \u00e9cris l'option \u00e9cart\u00e9e, "
                    "et rends compte. Seul le quoi est \u00e0 Jay.")
    if not ouverte_citee and _ARRET_NON_DECISION.search(texte):
        return None  # un secret, un blocage, un tiers, un acte sortant: un fait que Jay detient. Cette exemption ne leve QUE
        # l'obligation de citer une decision ouverte, jamais le refus d'une decision tranchee ou de Takumi (relecture 4116a6d, remarque 1)
    if not ouverte_citee:
        commande = f"python {dec.PROJETS_DIR / 'Kata' / 'scripts' / 'decisions.py'} ouvrir D-AAAA-MM-JJ-sujet --sujet \"...\" --qui jay --source <chemin>"
        return ("Une question \u00e0 Jay cite l'identifiant d'une d\u00e9cision OUVERTE du registre (D-AAAA-MM-JJ-...). Aucune n'est cit\u00e9e. "
                f"Si la question est nouvelle, enregistre-la d'abord : {commande} \u2014 puis cite son identifiant. Un secret, un blocage, un tiers "
                "ou un acte sortant se d\u00e9clarent par une ligne [ARRET] secret|blocage|tiers|sortant : <raison> dans la question.")
    return None


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("tool_name") != "AskUserQuestion":
        pass_through()
    registre = dec.charger()
    if not registre:
        pass_through()
    message = verdict(texte_des_questions(data), registre)
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a question
        print(f"[question-registre-gate] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
