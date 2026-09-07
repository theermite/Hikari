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


def boite_partagee(racine: Path) -> Path:
    """La boite de Shinzo, lue quel que soit le depot ou l'on demarre.

    Choix de Jay, 2026-09-07. Une propagation qui ne peut pas rendre une reserve
    y depose son constat : `/session-start` lit Shinzo a chaque demarrage, tandis
    que `.claude/state/` est ignore par git et s'efface sans laisser de trace.

    Shinzo vit en frere de l'atelier, jamais dans le depot courant.
    """
    return Path(racine).parent / "Shinzo" / "09-Relais"


def _lire(dossier: Path) -> tuple[list, int]:
    """Une boite absente est vide ; une boite EN PANNE est comptee.

    Defaut introduit puis trouve par relecture le 2026-09-07 : en lisant deux
    boites, j'avais neutralise l'erreur de l'une en la rendant vide. Une boite
    cassee devenait alors indiscernable d'une boite calme — precisement le
    silence qu'on passe la journee a fermer. Un depot illisible est COMPTE, et
    le lecteur le dit.
    """
    dossier = Path(dossier)
    if dossier.exists() and not dossier.is_dir():
        return [], 1  # une boite qui n'est pas un dossier est cassee, pas calme
    try:
        return relay.relever_avec_erreurs(dossier, marquer_lus=True)
    except OSError:
        return [], 1


def rapport(dossier: Path, partagee: Path | None = None) -> str:
    """Le texte a afficher, ou vide. Marque les messages comme lus.

    Deux boites, une seule passe : celle du depot et celle de Shinzo. Un canal
    ecrit sans son lecteur est un controle orphelin de plus — il y en a eu trois
    le 2026-09-06.
    """
    morceaux, illisibles = [], 0
    for boite_a_lire in [dossier] + ([partagee] if partagee is not None else []):
        messages, rates = _lire(Path(boite_a_lire))
        morceaux.extend(relay.rendu(message) for message in messages)
        illisibles += rates
    if illisibles:
        morceaux.append(
            f"[RELAIS] {illisibles} depot(s) illisible(s) — ignores, jamais devines. "
            f"Les retrouver dans {Path(dossier).as_posix()}."
        )
    return "\n".join(morceaux)


def main() -> None:
    try:
        racine = find_repo_root()
        texte = rapport(boite(racine), boite_partagee(racine))
    except Exception as erreur:  # une boite cassee ne doit jamais retenir une session
        print(f"[RELAIS] boite indisponible ({erreur}).", file=sys.stderr)
        sys.exit(0)
    if texte:
        print(texte, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
