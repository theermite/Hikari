#!/usr/bin/env python3
"""Le conseil arrive AVANT l'ecriture — et il laisse une trace.

Trigger
-------
PreToolUse Write/Edit sur un rapport de session (`docs/Sessions/Session-*.md`).

Regle
-----
Le rapport porte soit une contradiction emise (`[CHALLENGE] ...`), soit la
raison ecrite de n'en avoir emis aucune (`[NO-CHALLENGE] motif: <liste
fermee>`). Sans l'un des deux, l'ecriture est refusee.

Pourquoi
--------
Mesure du 2026-09-06 sur tout l'atelier : le gabarit de contradiction technique
a ete emis pour de vrai **1 fois sur 1269 rapports**. Sur les 20 dernieres
sessions : 43 decisions structurantes, 3 contradictions (dont une fausse), et
~43 defauts rattrapes APRES ecriture — un par decision prise. La regle existait
depuis des mois ; elle n'a jamais mordu, parce que rien ne la tenait.

La raison ecrite n'est pas une sortie de secours : c'est le signal. « Jay a
apporte le meilleur chemin lui-meme » est exactement ce qu'on veut voir compte,
pas efface — c'est arrive le jour meme ou cette porte a ete posee.

Le lecteur est tolerant a la mise en forme (gras, accents graves, cellule de
tableau) : une porte doit refuser un defaut de fond, jamais un defaut de
presentation. Un marqueur en gras a deja bloque silencieusement toute une serie
de tentatives.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    format_block,
    get_content,
    get_file_path,
    pass_through,
    read_hook_input,
)

# Liste FERMEE. Une liste qu'on rallonge n'est plus une garde — chaque motif
# doit rester un signal qu'on peut compter, pas une case a cocher.
MOTIFS = (
    "aucune-decision-structurante",
    "chemin-unique-impose",
    "contradiction-portee-par-jay",
    "session-de-correction-dirigee",
)

# Le chemin arrive tantot absolu, tantot relatif au depot : les deux comptent.
_RAPPORT_RE = re.compile(r"(?:^|\\)docs\\Sessions\\Session-[^\\]*\.md$", re.I)
_CHALLENGE_RE = re.compile(r"\[CHALLENGE\]", re.I)
_NO_CHALLENGE_RE = re.compile(
    r"\[NO-CHALLENGE\][\s`*_|]*motif\s*:\s*([a-z0-9-]+)", re.I
)


def is_session_report(chemin: str) -> bool:
    """Vrai pour un rapport de session, faux pour tout le reste du depot."""
    if not chemin:
        return False
    return bool(_RAPPORT_RE.search(chemin.replace("/", "\\")))


def trace(contenu: str) -> str | None:
    """La trace portee par le texte, ou None s'il n'y en a pas de valable."""
    if not contenu:
        return None
    if _CHALLENGE_RE.search(contenu):
        return "challenge"
    m = _NO_CHALLENGE_RE.search(contenu)
    if m and m.group(1).lower() in MOTIFS:
        return m.group(1).lower()
    return None


_REPROCHES_RE = re.compile(r"reproches?\s+de\s+livraison", re.I)
# Une reponse, pas un titre : soit « aucun », soit une parole rapportee.
_REPONSE_RE = re.compile(r"\baucun\b|[«\"']", re.I)


def complaints_section(contenu: str) -> bool:
    """La section « Reproches de livraison » existe ET dit quelque chose.

    Un titre vide serait une case a cocher. On exige donc une reponse dans les
    lignes qui suivent : « aucun », ou la parole de Jay rapportee.

    Pourquoi : 5 reproches en 20 sessions, 3 d'entre eux APRES le correctif
    cense les fermer. Le signal etait documente a chaque fois et n'entrait dans
    aucun score, donc rien ne changeait.
    """
    if not contenu:
        return False
    m = _REPROCHES_RE.search(contenu)
    if not m:
        return False
    suite = contenu[m.end():m.end() + 400]
    # On s'arrete au titre suivant : ce qui appartient a une autre section ne
    # repond pas pour celle-ci.
    coupe = re.split(r"\n\s*#{1,6}\s", suite)[0]
    return bool(_REPONSE_RE.search(coupe))


def verdict(chemin: str, contenu: str) -> str | None:
    """Le message de refus, ou None quand la porte laisse passer."""
    if not is_session_report(chemin):
        return None
    if not contenu.strip():
        # Squelette vide : la porte se pose au contenu, pas au geste.
        return None
    if not trace(contenu):
        return _refus_trace()
    if not complaints_section(contenu):
        return _refus_reproches()
    return None


def _refus_trace() -> str:
    return format_block(
        reason=(
            "rapport de session sans trace de conseil. Mesure : le gabarit de "
            "contradiction technique a ete emis 1 fois sur 1269 rapports, "
            "pendant que ~43 defauts etaient rattrapes APRES ecriture."
        ),
        recovery=(
            "Ajouter au rapport SOIT la contradiction emise :\n"
            "  [CHALLENGE] <ce qui a ete contredit, et ce qui en est sorti>\n"
            "SOIT la raison de n'en avoir emis aucune, motif dans la liste "
            "fermee :\n"
            f"  [NO-CHALLENGE] motif: <{' | '.join(MOTIFS)}>\n"
            "La raison n'est pas une sortie de secours : c'est le signal."
        ),
        reference="rules/Honesty.md — Active Technical Challenge",
    )


def _refus_reproches() -> str:
    return format_block(
        reason=(
            "rapport de session sans section « Reproches de livraison » remplie. "
            "Mesure : 5 reproches en 20 sessions, dont 3 APRES le correctif cense "
            "les fermer — le signal n'entrait dans aucun score."
        ),
        recovery=(
            "Ajouter la section au rapport :\n"
            "  ## Reproches de livraison\n"
            "  aucun\n"
            "OU, s'il y en a eu, la parole de Jay mot pour mot, la cause trouvee, "
            "et ce qui a change. -10 Valeur par occurrence."
        ),
        reference="rules/Workflows.md — Scoring V2",
    )


def main() -> None:
    _, data = read_hook_input()
    message = verdict(get_file_path(data), get_content(data))
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    main()
