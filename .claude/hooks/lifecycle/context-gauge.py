#!/usr/bin/env python3
"""La taille du contexte se lit, elle ne s'estime plus — UserPromptSubmit.

Trigger
-------
UserPromptSubmit : une fois par tour de Jay, jamais a chaque outil.

Regle
-----
Lire la taille reellement occupee dans le transcript, et ne parler qu'au
franchissement d'un palier. Jamais bloquer : c'est une jauge, pas une porte.

Pourquoi
--------
La regle precedente disait « alerte a ~40 echanges ou ~15 lectures de fichiers
(~60 %) · arret a ~60 echanges ». Trois defauts, mesures le 2026-09-06 :

1. Ce sont des raccourcis. Un echange peut couter 200 jetons ou 40 000 ; une
   lecture, 3 lignes ou 3 000. Le compte d'echanges ne mesure rien.
2. Ils sont calibres sur une fenetre de 200 000. La session travaille sur
   1 000 000 — les seuils etaient faux d'un facteur 5.
3. Mesure prise pendant la session qui a pose cette jauge : ~479 000 jetons
   occupes, moins de la moitie de la fenetre, alors que l'ancienne regle
   ordonnait l'arret depuis longtemps. Un garde-fou qui se declenche a tort
   finit debranche — et il emporte la detection reelle avec lui.

Jay, le meme jour : « il y a une degradation possible a partir de 600 a
700 000 jetons ». Les paliers viennent de la, pas d'une fraction inventee.

Sortie recommandee au palier haut : la reprise a chaud (resume + `/clear`),
moins chere que fermer puis rouvrir une session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import pass_through, read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402

# Zone de degradation annoncee par Jay (2026-09-06). Absolus, pas une fraction :
# une fraction changerait de sens le jour ou la fenetre change.
SEUIL_ALERTE = 600_000
SEUIL_REPRISE = 700_000

_ETAT = "context-gauge"


def context_size(transcript_path) -> int | None:
    """Les jetons reellement occupes au dernier tour, ou None si on ne sait pas.

    Somme l'entree, le cache ecrit et le cache lu : le cache lu occupe la
    fenetre, meme s'il coute moins cher a facturer.

    Rend None, jamais 0, quand la mesure est absente — un faux zero se lit
    comme « tout va bien », et c'est exactement le defaut que cette jauge
    existe pour eviter.
    """
    dernier = None
    try:
        with Path(transcript_path).open(encoding="utf-8") as f:
            for ligne in f:
                try:
                    d = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                u = (d.get("message") or {}).get("usage")
                if isinstance(u, dict):
                    dernier = u
    except (OSError, UnicodeDecodeError):
        return None
    if not dernier:
        return None
    return sum(
        int(dernier.get(k) or 0)
        for k in ("input_tokens", "cache_creation_input_tokens",
                  "cache_read_input_tokens")
    )


def level(tokens: int | None) -> str:
    """Le palier : ok · alerte · reprise · inconnu."""
    if tokens is None:
        return "inconnu"
    if tokens >= SEUIL_REPRISE:
        return "reprise"
    if tokens >= SEUIL_ALERTE:
        return "alerte"
    return "ok"


_RANG = {"ok": 0, "alerte": 1, "reprise": 2}


def should_speak(palier: str, precedent: str) -> bool:
    """On parle en MONTANT d'un palier, jamais en boucle ni en redescendant.

    Repeter a chaque tour, c'est se faire ignorer. Et apres une reprise a chaud
    la jauge redescend : ce n'est pas un evenement.
    """
    if palier not in _RANG:
        return False
    return _RANG[palier] > _RANG.get(precedent, -1)


def message(tokens: int, palier: str) -> str:
    milliers = f"{tokens:,}".replace(",", " ")
    if palier == "reprise":
        return (
            f"[CONTEXTE] {milliers} jetons occupes — zone de degradation depassee. "
            "Reprise a chaud recommandee : ecrire les fils encore ouverts avec "
            "[EN-SUSPENS], puis /clear, puis reprendre sur le resume. Moins cher "
            "que fermer et rouvrir la session."
        )
    return (
        f"[CONTEXTE] {milliers} jetons occupes — entree de la zone ou la qualite "
        "peut se degrader. Poser les fils ouverts avec [EN-SUSPENS] des maintenant, "
        "pour qu'une reprise ne les perde pas."
    )


def main() -> None:
    _, data = read_hook_input()
    tokens = context_size(data.get("transcript_path") or "")
    palier = level(tokens)
    precedent = (read_state(_ETAT) or {}).get("palier", "ok")
    if should_speak(palier, precedent):
        write_state(_ETAT, {"palier": palier})
        print(message(tokens, palier), file=sys.stderr)
        sys.exit(2)  # 2 = le message remonte, sans bloquer le tour
    if palier != "inconnu" and palier != precedent:
        write_state(_ETAT, {"palier": palier})
    pass_through()


if __name__ == "__main__":
    main()
