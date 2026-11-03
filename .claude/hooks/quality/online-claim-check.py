#!/usr/bin/env python3
"""Contrôle en ligne avant de dire « en ligne » — Stop. Refuse l'affirmation tant qu'aucun contrôle réel n'a suivi la mise en ligne.

Décision de Jay (2026-10-30) : après une mise en ligne, avant de lui dire qu'un site est en ligne, Takumi lance `web_check` (ou
`curl` si le serveur web n'est pas chargé) sur l'adresse publique et un parcours critique, et cite la sortie. « En ligne » veut
dire joignable ET fonctionnel. Jusqu'ici la règle ne tenait que par discipline : `deploy/smoke-test-required.py` ne prévenait
qu'une fois et ne voyait pas un appel MCP. Ce garde lit le même état (`deploy-smoke`, posé par ce garde de fumée) : si une mise
en ligne de la séance n'a eu aucun contrôle depuis ET que la réponse affirme que c'est en ligne, il garde le tour ouvert une fois.

Limites écrites : l'affirmation est reconnue par des tournures (fr/en), pas par le sens ; une négation (« pas encore en ligne »)
la laisse passer ; l'état « mise en ligne en attente » vient de la lecture des vraies commandes (`lib/deploy_reader.py`), donc
une mise en ligne faite hors de cette séance n'est pas vue. Un seul refus par tour (`stop_hook_active`), jamais de refus sur panne.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402
from session_state import read_state  # noqa: E402

STATE_NAME = "deploy-smoke"

_NEGATION = re.compile(r"\b(pas|jamais|ni|not|never|n't|aucun)\b|\bavant\b|\bquand\b|\bsi\b|\?", re.IGNORECASE)
_CLAIM = re.compile(
    r"c['’]est\s+(?:bien\s+|déjà\s+)?en\s+ligne"
    r"|\best\s+(?:bien\s+|maintenant\s+|déjà\s+)?(?:en\s+ligne|déployée?s?|en\s+production|en\s+prod|live)\b"
    r"|\bsont\s+(?:bien\s+|maintenant\s+)?(?:en\s+ligne|déployée?s?|en\s+production)\b"
    r"|\bmise\s+en\s+(?:ligne|production)\s+(?:est\s+)?(?:terminée|réussie|faite|effectuée|ok)\b"
    r"|\bdéploiement\s+(?:est\s+)?(?:terminé|réussi|fait|effectué|ok)\b"
    r"|\b(?:is|are|it['’]s)\s+(?:now\s+)?(?:live|online|deployed)\b"
    r"|\bdeployed\s+and\s+(?:verified|working|running)\b"
    r"|\bup\s+and\s+running\b",
    re.IGNORECASE)
# Ce qui ressemble à une affirmation sans en être une (relecture 2026-11-02, R2) : une mise en ligne locale ou de prévisualisation,
# « en ligne avec » (aligné sur), et tout texte cité (guillemets, « », code) qui parle de la phrase au lieu de la dire.
# On retire seulement le PASSAGE exempté, jamais la phrase entière : « c'est en ligne avec le nouveau formulaire » reste une
# affirmation (relecture ciblée du 2026-11-02). « En ligne avec » ne veut dire « aligné sur » que devant une charte, une spec…
_EXEMPT = re.compile(
    r"en\s+ligne\s+avec\s+(?:la|le|les|l['’])\s*(?:charte|maquette|spec\w*|cahier|doc\w*|norme|règles?|convention\w*|doctrine)\b"
    r"|déployée?s?\s+(?:localement|en\s+(?:pré|pre)visualisation|en\s+local|sur\s+(?:staging|preview|ma\s+machine))"
    r"|deployed\s+(?:locally|to\s+(?:staging|preview))", re.IGNORECASE)
_QUOTED = re.compile(r"«[^»]*»|\"[^\"\n]*\"|“[^”]*”|`[^`\n]*`")   # jamais à travers une fin de ligne : un guillemet seul n'avale pas la suite

RECOVERY = (
    "BLOCKED: tu annonces que c'est en ligne, mais la mise en ligne de cette séance n'a eu aucun contrôle depuis. RECOVERY: lance "
    "`web_check` (serveur web shinkofa-web) sur l'adresse publique et sur un parcours critique ; sans ce serveur : "
    "`curl -fsS -o /dev/null -w \"%{http_code}\" <url>` sur l'adresse et sur ce parcours. Cite la sortie, puis réécris ta réponse : "
    "« en ligne » veut dire joignable ET fonctionnel (un site qui répond mais plante sur son parcours critique n'est pas en ligne). "
    "Si le contrôle est impossible, dis-le et dis pourquoi au lieu d'affirmer. See .claude/rules-ondemand/Mise-En-Service.md "
    "(Live check before saying « online »)."
)


def claims_online(reply: str) -> bool:
    """True when a sentence of the reply states that something is online, and that sentence is not negated, conditional or a question."""
    sentences = re.split(r"(?<=[.!?…])\s+|\n+", _QUOTED.sub(" ", reply))
    kept = [_EXEMPT.sub(" ", s) for s in sentences]
    return any(_CLAIM.search(s) and not _NEGATION.search(s) for s in kept)


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    if not isinstance(reply, str) or not claims_online(reply):
        pass_through()
    state = read_state(STATE_NAME, data.get("session_id") or None)
    if state.get("pending_deploy"):
        block(RECOVERY)
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[online-claim-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
