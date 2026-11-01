#!/usr/bin/env python3
"""Couverture linguistique — Stop hook. Une langue annoncée `ok` doit avoir été cherchée.

Décision de Jay (2026-10-31, règle ciblée) : une recherche de fond (choix de technologie, bug qui dure,
enrichissement de la base de savoir) se fait en sept langues et se termine par `[LANGUES] EN=ok FR=ok ...`.
Origine : feedback de Jay du 2026-05-26, les agents « prétendent avoir cherché en 7 langues ».

Se déclenche quand la dernière réponse porte le marqueur. Lit les requêtes réellement lancées dans le
journal de la séance (WebSearch et web_search du serveur web) et refuse une langue `ok` sans requête dans son
écriture. Une seule fois par tour (stop_hook_active), tolère la mise en forme, échoue ouvert.

Limites écrites : (1) sans marqueur, rien n'est jugé — la règle dit QUAND le poser, pas ce hook ;
(2) si un sous-agent a été lancé depuis le dernier message de Jay, ses recherches sont dans son propre
journal : on ne juge alors que la forme du marqueur ; (3) la langue d'une requête se lit à la forme.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, format_block, pass_through, read_hook_input  # type: ignore  # noqa: E402
from langues_couverture import LANGUES, parse_marker, problemes  # type: ignore  # noqa: E402
from transcript_reader import entry_message, iter_entries  # type: ignore  # noqa: E402
from user_turns import _is_real_user_message  # type: ignore  # noqa: E402

OUTILS_DE_RECHERCHE = {"WebSearch", "web_search", "mcp__shinkofa-web__web_search"}
OUTILS_DE_DELEGATION = {"Agent", "Task"}


def _blocs_outil(message: dict):
    contenu = message.get("content")
    for bloc in contenu if isinstance(contenu, list) else []:
        if isinstance(bloc, dict) and bloc.get("type") == "tool_use":
            yield bloc


def _requete_du_bloc(bloc: dict) -> str | None:
    entree = bloc.get("input") or {}
    if bloc.get("name") in OUTILS_DE_RECHERCHE and isinstance(entree.get("query"), str):
        return entree["query"]
    return None


def requetes_et_delegation(chemin: str) -> tuple[list[str], bool]:
    """Les requêtes de la séance, et si un sous-agent a été lancé depuis le dernier message de Jay."""
    requetes: list[str] = []
    delegue = False
    depuis_jay = True
    for entree in iter_entries(chemin):
        message = entry_message(entree)
        if message is None:
            continue
        depuis_jay = depuis_jay and not _is_real_user_message(message)
        for bloc in _blocs_outil(message):
            requete = _requete_du_bloc(bloc)
            if requete is not None:
                requetes.append(requete)
            delegue = delegue or (depuis_jay and bloc.get("name") in OUTILS_DE_DELEGATION)
    return requetes, delegue


def message_de_refus(erreurs: list[str]) -> str:
    return format_block(
        reason="couverture linguistique annoncée, non prouvée par les recherches faites :\n  - "
               + "\n  - ".join(erreurs),
        recovery=("Soit lancer la requête manquante dans la langue (écriture native), soit corriger le marqueur "
                  "en `rien` pour cette langue — dire « rien » est permis, annoncer `ok` sans avoir cherché "
                  f"ne l'est pas. Les sept langues figurent toutes dans le marqueur : {', '.join(LANGUES)}."),
        reference=".claude/rules/05-Savoir.md § 6 (recherche de fond)",
    )


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reponse = data.get("last_assistant_message")
    marqueur = parse_marker(reponse) if isinstance(reponse, str) else None
    if marqueur is None:
        pass_through()
    # SubagentStop : les recherches d'un agent sont dans SON journal (`agent_transcript_path`), pas dans celui
    # de la séance. Sans ce chemin, le journal de la séance est le seul disponible.
    chemin = data.get("agent_transcript_path") or data.get("transcript_path")
    if not isinstance(chemin, str) or not chemin or not Path(chemin).is_file():
        pass_through()   # pas de journal à lire : on ne juge pas (échec ouvert)
    requetes, delegue = requetes_et_delegation(chemin)
    erreurs = problemes(marqueur, requetes, delegue)
    if erreurs:
        block(message_de_refus(erreurs))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — échoue ouvert, ne casse jamais une réponse
        print(f"[langues-check] passe sans juger : {exc}", file=sys.stderr)
        sys.exit(0)
