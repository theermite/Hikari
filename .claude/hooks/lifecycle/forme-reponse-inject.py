#!/usr/bin/env python3
"""Forme-réponse inject — UserPromptSubmit. La taille de la réponse se règle AVANT qu'elle soit écrite, selon la forme de la question.

Jay 2026-11-24: « Je t'ai posé une question simple et on regarde la taille de ta réponse. » Une question fermée (oui ou non) reçoit une
ou deux phrases, pas un tableau. Le garde de forme existant (`simple-language-check`) ne mesure que la longueur des phrases, et seulement
après coup. Ici, le test est déterministe (mêmes mots, même verdict) et la consigne arrive dans le contexte avant la réponse.

Une question est « fermée » quand le message est court (40 mots au plus), finit par « ? », n'en contient qu'un, n'a pas de bloc de code,
s'ouvre ou se dit comme une question oui/non (« est-ce que », « as-tu », « c'est bien ça », « tu peux »…) et ne demande ni explication,
ni liste, ni point, ni action (« pourquoi », « comment », « liste », « fais », « montre »…). Limite écrite: lexical sur le message de Jay
(l'entrée), jamais sur le texte de Takumi ; une question tournée autrement n'est pas reconnue et reste soumise au garde de forme.
"""

from __future__ import annotations

import re
import sys

MAX_MOTS = 40
_FERMEE = re.compile(
    r"(?i)(?:\best-ce (?:que|qu['’])|\b(?:as|es|peux|veux|vois|sais)-tu\b|\b(?:a|est|peut|y a)-(?:t-)?(?:on|il|elle)\b|\btu (?:peux|as|vois|sais|confirmes)\b|"
    r"\bc['’]est (?:bien )?(?:ça|normal|vrai|fusionn\w*|fait|prêt|propag\w*|pouss\w*)\b|\bn['’]est-ce pas\b|\bça (?:peut|marche|va|suffit)\b)"
)
_OUVERTE = re.compile(
    r"(?i)\b(?:pourquoi|comment|explique\w*|d[ée]taill\w*|liste\w*|montre\w*|quels?|quelles?|combien|fais\w*|construi\w*|dis-moi|donne\w*|"
    r"[ée]cris\w*|point|[ée]tat|propose\w*|corrige\w*|lance\w*|c['’]est (?:quoi|o[ùu]|qui|quand)|"
    r"aider|m['’]aide\w*|refaire|faire|montrer|donner)\b"
)
_CODE = re.compile(r"```")

CONSIGNE = (
    "[FORME — QUESTION FERMÉE] Jay pose une question à réponse oui ou non. Réponds par le oui ou le non (ou la réponse en une ligne), "
    "puis une ou deux phrases au plus. Ni tableau, ni liste, ni détail de vérification, sauf s'il le demande : tu vérifies dans tes outils, "
    "tu ne montres pas ta vérification."
)


def est_question_fermee(message: str) -> bool:
    texte = (message or "").strip()
    if not texte.endswith("?") or texte.count("?") != 1 or _CODE.search(texte) or len(texte.split()) > MAX_MOTS:
        return False
    return bool(_FERMEE.search(texte)) and not _OUVERTE.search(texte)


def main() -> None:
    try:
        import json
        donnees = json.loads(sys.stdin.read() or "{}")
        if isinstance(donnees, dict) and est_question_fermee(str(donnees.get("prompt") or "")):
            sys.stdout.write(CONSIGNE + "\n")
            sys.stdout.flush()
    except Exception:  # noqa: BLE001 — never break Jay's prompt
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
