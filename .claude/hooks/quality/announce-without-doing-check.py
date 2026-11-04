#!/usr/bin/env python3
"""Announce-without-doing check — Stop hook. Annoncer la suite au lieu de la faire est un tour perdu.

Retour de Jay (2026-11-04) : « systématiquement, pendant qu'on travaille, Takumi s'arrête et me dit : la prochaine chose
que je vais faire, c'est ça, sauf qu'il ne se met pas à le faire ». Jay doit relancer : c'est du va-et-vient pur.

Le garde lit la FIN du message (les ~400 derniers caractères, hors citations et blocs de code). Si elle annonce une
action de Takumi à la première personne, sans condition ni question, il garde le tour ouvert une fois : fais-le maintenant.
Il laisse passer :
  - une question à Jay (une vraie décision) ;
  - une attente d'un événement extérieur (« dès que », « quand », « une fois que », « si », « en attendant »…) ;
  - du travail lancé en arrière-plan dans le tour (Agent, Monitor, Workflow) : s'arrêter est alors correct ;
  - une déclaration `[ARRET] …` ou le marqueur `[ANNONCE-OK] <raison>` (Jay a demandé le plan, pas l'exécution).
Limites écrites : lexical (une annonce tournée autrement passe) ; une réponse légitime à « que comptes-tu faire ? » est
arrêtée une fois (le marqueur la libère). Échec ouvert, une fois par tour (stop_hook_active).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402
from turn_log import tool_runs  # noqa: E402

_TAIL = 400
_FUTURE = re.compile(
    r"(?i)\b(?:je vais|je m['’]apprête à|je passe (?:maintenant |ensuite )?(?:à|au|aux)|je commence (?:maintenant |ensuite )?(?:par|à)|"
    r"j['’]enchaîne|(?:ensuite|puis|après (?:cela|ça|ce point)),? (?:je|j['’])(?! ?(?:ai|avais|n['’]ai|l['’]ai|suis|y suis|me suis|m['’]\w+ suis|n['’]étais)\b)|"
    r"il me reste à|reste à faire\s*:|je m['’]en occupe (?:maintenant|ensuite)|"
    r"je (?:m['’]en )?occupe (?:maintenant |ensuite )?(?:de|du|des|d['’])|je lance (?:maintenant|ensuite)|"
    r"je traite (?:maintenant|ensuite)|prochaine (?:étape|chose(?: à faire)?|action|brique)\s*:\s*(?:je|j['’]))"
)
_CONDITION = re.compile(
    r"(?i)\b(?:dès (?:que|qu['’])|quand|lorsque|lorsqu['’]|une fois (?:que|qu['’]|la|le|les)|si |tant que|en attendant|pendant que|"
    r"(?:je vais|je dois|je peux)\s+(?:attendre|patienter)|attends?\b|j['’]attends|"
    r"après (?:le|la|les) (?:verdict|retour|relecture|réponse)|avec ton accord|si tu|selon ta réponse)"
)
_OK = re.compile(r"(?im)^\W{0,6}\[ANNONCE-OK\]\W*\S+(?:\s+\S+){1,}|^\W{0,12}\[ARR[EÊ]T\]")
_QUOTED = re.compile("«[^»]*»|“[^”]*”")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")
_BACKGROUND = {"Agent", "Monitor", "Workflow", "Task", "TaskCreate"}
_COLON_THEN_CONTENT = re.compile(r":\s*\n\s*\S")

MESSAGE = (
    "Tu termines ton tour en ANNONÇANT une action que tu peux faire seul (« ensuite je… », « prochaine étape : je… »). "
    "Jay devrait te relancer : c'est du va-et-vient. Fais-le maintenant, dans ce tour, puis rends compte (fait, vérifié "
    "avec la commande et sa sortie, fils ouverts). Si tu attends un événement extérieur, dis lequel (« dès que la "
    "relecture revient »). Si c'est une vraie décision de Jay, pose la question. Si Jay a demandé le plan et non "
    "l'exécution, ajoute la ligne : [ANNONCE-OK] <pourquoi>. Réécris ta réponse."
)


def announces(reply: str, background: bool = False) -> bool:
    """La fin du message annonce une action de Takumi, sans condition ni question, et rien n'est en cours en arrière-plan."""
    if background or not isinstance(reply, str) or _OK.search(_FENCE.sub(" ", reply)):
        return False
    text = _QUOTED.sub(" ", _FENCE.sub(" ", reply))[-_TAIL:]
    if _COLON_THEN_CONTENT.search(text):  # « Je vais te donner le détail : » followed by the detail itself
        return False
    sentences = [s.strip() for s in _SENTENCE.split(text) if s.strip()]
    if any(s.rstrip("*_`❓ ").endswith("?") for s in sentences[-4:]):
        return False
    return any(_FUTURE.search(s) and not _CONDITION.search(s) for s in sentences[-3:])


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    background = any(r.name in _BACKGROUND or r.background for r in tool_runs(data.get("transcript_path") or ""))
    if isinstance(reply, str) and announces(reply, background):
        block(MESSAGE)
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[announce-without-doing-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
