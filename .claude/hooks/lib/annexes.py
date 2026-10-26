"""Registre des annexes: quelle annexe doit avoir été lue avant quel travail.

Les huit règles sont courtes et toujours chargées; le détail vit dans des annexes
(`.claude/rules-ondemand/`). Une annexe que personne n'est forcé de lire n'est pas lue: le
registre `annexes.json` dit, pour chaque annexe, le moment qui la requiert, et le garde-fou
`guards/annexes-gate.py` refuse l'écriture tant qu'elle n'a pas été lue.

Ce module est pur (aucune entrée/sortie hors le chargement du registre): le garde-fou le
branche à l'outil réel, les tests le branchent à des cas.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import actes

MANIFESTE = Path(".claude") / "rules-ondemand" / "annexes.json"

OUTILS_TRAVAIL = ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash")

class Registre(list):
    """La liste des annexes, avec les chemins exemptés (les annexes elles-mêmes)."""

    exemptions: tuple[str, ...] = ()


def charger(racine: Path) -> Registre:
    """Le registre du dépôt, vide s'il est absent ou illisible: ne jamais rendre une session impossible."""
    registre = Registre()
    try:
        doc = json.loads((Path(racine) / MANIFESTE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return registre
    registre.extend(doc.get("annexes", []))
    registre.exemptions = tuple(doc.get("exemptions", []))
    return registre


def _regex(motif: str) -> str:
    sortie, i = "", 0
    while i < len(motif):
        if motif.startswith("**/", i):
            sortie += "(?:.*/)?"
            i += 3
        elif motif.startswith("**", i):
            sortie += ".*"
            i += 2
        elif motif[i] == "*":
            sortie += "[^/]*"
            i += 1
        elif motif[i] == "?":
            sortie += "[^/]"
            i += 1
        else:
            sortie += re.escape(motif[i])
            i += 1
    return sortie


def correspond_chemin(motif: str, chemin: str) -> bool:
    """`**/` = n'importe quel dossier parent (ou aucun), `*` = un nom sans séparateur.

    Sans égard à la casse: Windows ne la respecte pas (`Docs/cdc.md` est `docs/CDC.md`), et sur un
    serveur Linux sur-déclencher est sans danger alors que sous-déclencher laisse écrire le socle.
    """
    return re.fullmatch(_regex(motif), chemin.replace("\\", "/"), re.IGNORECASE) is not None


def lecture_seule(commande: str) -> bool:
    """Chaque acte de la commande est une lecture connue (liste fermée, voir `actes`)."""
    return actes.est_lecture(commande)


def chemins_de_commande(commande: str) -> list[str]:
    """Les chemins que la commande ÉCRIT, relatifs au dossier courant suivi (`cd x && …`)."""
    return actes.chemins_ecrits(commande)


def _outils_du(d: dict) -> tuple:
    return tuple(d.get("outils") or (OUTILS_TRAVAIL if d.get("travail") else ()))


def _vise_chemin(d: dict, chemin: str, existe: bool) -> bool:
    if not chemin:
        return False
    if any(correspond_chemin(m, chemin) for m in d.get("chemins", [])):
        return True
    return not existe and any(correspond_chemin(m, chemin) for m in d.get("nouveaux_fichiers", []))


def _vise_chemins_commande(d: dict, commande: str, exemptions: tuple = ()) -> bool:
    """Une commande qui écrit est jugée sur les fichiers qu'elle nomme, comme un Write (sauf les dossiers exemptés)."""
    chemins = [j for j in chemins_de_commande(commande) if not any(e in j.replace("\\", "/") for e in exemptions)]
    return any(_vise_chemin(d, j, Path(j).exists()) for j in chemins)


def _vise_commande(d: dict, commande: str) -> bool:
    """Un motif de commande s'applique à la forme de chaque acte, jamais au texte d'un message."""
    return any(re.search(m, t) for t in actes.textes(commande) for m in d.get("commandes", []))


def _declencheur_vise(d: dict, outil: str, chemin: str, commande: str, existe: bool, exemptions: tuple = ()) -> bool:
    if d.get("travail"):
        return outil in _outils_du(d) and not (outil == "Bash" and lecture_seule(commande))
    if outil == "Bash":
        # une écriture par Bash n'est jugée que par les déclencheurs qui nomment Bash: `cp tpl/package.json x/`
        # copie un modèle, elle n'écrit pas du code à veiller
        if "Bash" not in _outils_du(d) or lecture_seule(commande):
            return False
        return _vise_commande(d, commande) or _vise_chemins_commande(d, commande, exemptions)
    return outil in _outils_du(d) and (_vise_chemin(d, chemin, existe) or _vise_commande(d, commande))


def requises(registre: Registre, outil: str, chemin: str = "", commande: str = "", existe: bool = True) -> list[dict]:
    """Les annexes qu'il faut avoir lues avant cet appel d'outil."""
    norme = chemin.replace("\\", "/")
    if norme and any(e in norme for e in registre.exemptions):
        return []
    return [a for a in registre
            if any(_declencheur_vise(d, outil, chemin, commande, existe, registre.exemptions)
                   for d in a.get("declencheurs", []))]
