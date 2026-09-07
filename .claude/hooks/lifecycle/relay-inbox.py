#!/usr/bin/env python3
"""Les messages des autres sessions remontent au demarrage — SessionStart.

Point 8 du plan, seconde moitie. Le protocole vit dans `lib/relay.py` ; ce
fichier n'en est que la bouche.

POURQUOI IL EXISTE. Un canal que personne n'ouvre est un controle que personne
ne lance. La soiree du 2026-09-06 en a trouve trois d'un coup — le sommaire de
memoire, le parc d'experts, les chiffres du conseil — dont un annonce par une
regle BLOQUANTE. Ecrire le protocole sans son lecteur aurait fabrique le
quatrieme.

CE QU'IL DIT, ET CE QU'IL NE DIT PAS. Il montre chaque message une fois, avec
son emetteur, son artefact et son verdict. Il ne dit jamais quoi faire : un
message est une donnee, et l'autorisation ne vient que de Jay, dans la
conversation en cours (`Confidentiality.md`, porte B).

Silencieux quand la boite est vide. Une ligne « 0 message » a chaque demarrage
apprend a ne plus lire les lignes de demarrage.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

import relay  # type: ignore # noqa: E402
from common import find_repo_root  # type: ignore # noqa: E402


def boite(racine: Path) -> Path:
    return Path(racine) / ".claude" / "state" / "relay"


def rapport(dossier: Path) -> str:
    """Le texte a afficher, ou vide. Marque les messages comme lus."""
    messages, illisibles = relay.relever_avec_erreurs(dossier, marquer_lus=True)
    morceaux = [relay.rendu(message) for message in messages]
    if illisibles:
        morceaux.append(
            f"[RELAIS] {illisibles} depot(s) illisible(s) — ignores, jamais devines. "
            f"Les retrouver dans {Path(dossier).as_posix()}."
        )
    return "\n".join(morceaux)


def main() -> None:
    try:
        texte = rapport(boite(find_repo_root()))
    except Exception as erreur:  # une boite cassee ne doit jamais retenir une session
        print(f"[RELAIS] boite indisponible ({erreur}).", file=sys.stderr)
        sys.exit(0)
    if texte:
        print(texte, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
