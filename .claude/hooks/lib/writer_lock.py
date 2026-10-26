"""Un seul écrivain par dépôt: un battement de cœur, pas une serrure.

Doctrine § 4: « trois collisions réelles entre sessions, faute de règle ». Chaque séance qui écrit
laisse son identité et l'heure dans `.claude/state/writer-lock.json`; une autre qui arrive la voit.

Pourquoi un battement et pas une serrure: Jay travaille volontairement sur plusieurs séances à la
fois. Interdire toute écriture concurrente retirerait cette capacité. Le coût réel d'une collision est
ailleurs: un commit qui embarque le travail de l'autre, une branche changée sous ses pieds. Le garde-
fou bloque donc ces gestes-là seulement (voir `touche_etat_partage`).

Limite connue: la lecture-modification-écriture du fichier n'est pas atomique entre deux processus;
au pire un battement est perdu et rétabli au suivant (30 s). C'est un avis, pas une preuve.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import actes
from session_state import read_state, write_state

NOM = "writer-lock"
TTL_S = 300        # une séance dont ni le dernier battement ni le journal n'ont bougé depuis 5 min n'écrit plus
HEARTBEAT_S = 30   # on ne réécrit pas le fichier à chaque appel d'outil

_AUTORISATION = re.compile(r"#\s*WRITER-OK:\s*\S")


def _entree(brut) -> dict:
    """Une entrée du fichier: `{"t": date, "journal": chemin, "certain": bool}`; l'ancien format était la seule date."""
    if isinstance(brut, dict):
        return {"certain": True, **brut}
    return {"t": brut, "journal": "", "certain": True}


def _vivacite(entree: dict) -> float:
    """La dernière preuve de vie: le battement, ou la dernière écriture du journal de la séance.

    Une séance vidée ou redémarrée change d'identifiant; son journal, lui, s'arrête de bouger. Une séance qui
    réfléchit longtemps n'écrit pas de battement mais son journal avance: elle reste vivante.
    """
    try:
        modifie = Path(entree["journal"]).stat().st_mtime if entree["journal"] else 0.0
    except OSError:
        modifie = 0.0
    return max(float(entree["t"]), modifie)


def _ecrivains(racine: Path, maintenant: float) -> dict[str, dict]:
    brut = read_state(NOM, repo_root=Path(racine)).get("ecrivains", {})
    entrees = {sid: _entree(v) for sid, v in brut.items()}
    return {sid: e for sid, e in entrees.items() if maintenant - _vivacite(e) < TTL_S}


def battre(racine: Path, session: str, maintenant: float | None = None, journal: str = "",
           certain: bool = True) -> bool:
    """Note que cette séance écrit. `certain=False`: elle a lancé une commande qui écrit peut-être (avis seulement).

    Une séance déjà certaine le reste; devenir certaine se note tout de suite, sans attendre le prochain battement.
    Retourne True si le fichier a été réécrit.
    """
    maintenant = time.time() if maintenant is None else maintenant
    ecrivains = _ecrivains(racine, maintenant)
    avant = ecrivains.get(session, {"t": -TTL_S, "certain": False})
    if maintenant - avant["t"] < HEARTBEAT_S and (avant["certain"] or not certain):
        return False
    ecrivains[session] = {"t": maintenant, "journal": journal, "certain": certain or avant["certain"]}
    write_state(NOM, {"ecrivains": ecrivains}, repo_root=Path(racine))
    return True


def autre_ecrivain(racine: Path, session: str, maintenant: float | None = None) -> dict | None:
    """L'autre séance qui a écrit ici récemment; une écriture certaine l'emporte sur une écriture possible."""
    maintenant = time.time() if maintenant is None else maintenant
    autres = [(e["certain"], _vivacite(e), sid) for sid, e in _ecrivains(racine, maintenant).items() if sid != session]
    if not autres:
        return None
    certain, t, sid = max(autres)
    return {"session": sid, "il_y_a_s": int(maintenant - t), "certain": certain}


def touche_etat_partage(commande: str, racine: str | None = None) -> bool:
    """Le geste change l'historique, la branche ou l'arbre de travail que l'autre séance utilise, dans ce dépôt."""
    return actes.touche_etat_partage(commande, racine)


def autorise_par_jay(commande: str) -> bool:
    """`# WRITER-OK: <raison>` en fin de commande: même chantier, deux fenêtres — Jay l'a dit."""
    return any(_AUTORISATION.match(c) for c in actes.commentaires(commande))
