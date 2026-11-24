"""La liste de tâches du tour, lue dans le journal: un FAIT, pas des mots.

Jay 2026-11-24: « j'annonce sans faire » se jugeait sur des mots du futur. La liste de tâches tenue pendant le tour dit l'état réel :
des étapes non terminées, et un tour qui finit sans `wrap_up`. Bibliothèque standard seule. Les appels lus sont ceux de CE tour
(depuis le dernier message de Jay), rejoués dans l'ordre : `items` pose la liste, `advance` termine l'étape en cours et ouvre la
suivante, `done` (numéros à partir de 1) termine, `start` (numéro à partir de 1) ouvre.
"""

from __future__ import annotations

from dataclasses import dataclass

from transcript_reader import entry_message, iter_entries
from turn_log import _is_jay_message

PLAN = "mcp__ccd_turn__update_plan"
FIN = "mcp__ccd_turn__wrap_up"


@dataclass(frozen=True)
class PlanTour:
    a_une_liste: bool
    restantes: list[str]
    cloture: bool


def _entrees_du_tour(chemin: str) -> list:
    """Les entrées du journal depuis le dernier message de Jay, de la plus récente à la plus ancienne."""
    entrees: list = []
    try:
        for entree in iter_entries(chemin):
            if _is_jay_message(entree):
                break
            entrees.append(entree)
    except Exception:  # noqa: BLE001 — échec ouvert
        return []
    return entrees


def _blocs_outil(entree) -> list[tuple[str, dict]]:
    msg = entry_message(entree)
    contenu = msg.get("content") if msg else None
    blocs = [b for b in contenu if isinstance(b, dict) and b.get("type") == "tool_use"] if isinstance(contenu, list) else []
    return [(str(b.get("name", "")), b["input"] if isinstance(b.get("input"), dict) else {}) for b in blocs]


def _appels_du_tour(chemin: str) -> list[tuple[str, dict]]:
    """Les appels d'outil de ce tour, du plus ancien au plus récent."""
    if not chemin:
        return []
    return [appel for entree in reversed(_entrees_du_tour(chemin)) for appel in _blocs_outil(entree)]


def _avancer(etapes: list[list[str]]) -> None:
    """Termine l'étape en cours et ouvre la suivante encore en attente."""
    for k, e in enumerate(etapes):
        if e[1] == "in_progress":
            e[1] = "completed"
            suivante = next((x for x in etapes[k + 1:] if x[1] == "pending"), None)
            if suivante:
                suivante[1] = "in_progress"
            return


def _marquer(etapes: list[list[str]], numeros, statut: str) -> None:
    for n in numeros if isinstance(numeros, list) else [numeros]:
        if isinstance(n, int) and 1 <= n <= len(etapes):
            etapes[n - 1][1] = statut


def _appliquer(etapes: list[list[str]], entree: dict) -> list[list[str]]:
    """Un appel de mise à jour de la liste. `etapes`: [[contenu, statut], …]."""
    if isinstance(entree.get("items"), list):
        return [[str(i.get("content", "")), str(i.get("status", "pending"))] for i in entree["items"] if isinstance(i, dict)]
    if entree.get("advance"):
        _avancer(etapes)
    _marquer(etapes, entree.get("done") or [], "completed")
    _marquer(etapes, entree.get("start"), "in_progress")
    return etapes


def plan_du_tour(chemin: str) -> PlanTour:
    etapes: list[list[str]] = []
    a_une_liste = cloture = False
    for nom, entree in _appels_du_tour(chemin):
        if nom == PLAN:
            a_une_liste = True
            etapes = _appliquer(etapes, entree)
        elif nom == FIN:
            cloture = True
    return PlanTour(a_une_liste, [c for c, s in etapes if s != "completed"], cloture)


def tour_incomplet(plan: PlanTour, reponse: str) -> bool:
    """Le tour finit avec des étapes ouvertes, sans `wrap_up`, et sans demander quoi que ce soit à Jay (un arrêt est légitime)."""
    texte = (reponse or "").strip()
    demande = texte.endswith("?") or "[ARRET]" in texte.upper()
    return plan.a_une_liste and bool(plan.restantes) and not plan.cloture and not demande
