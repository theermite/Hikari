"""Fraîcheur d'une fiche de projet : la date qu'elle porte contre le dernier changement de code.

Origine : Jay, 2026-11-01. « Sans fiches à jour, l'autonomie fera des bêtises, et je ne dois jamais être la
mémoire de secours. » Le code forçait la LECTURE de la fiche (`lifecycle/obsidian-mandatory-read.py`), rien
ne forçait sa mise à jour.

Deux consommateurs : le garde `quality/fiche-fraicheur-check.py` (avertit à l'écriture du rapport de séance,
seuil 0 jour) et `scripts/garde-methode.py` (entretien hebdomadaire, seuil 14 jours).

Ce qui compte comme « le code a bougé » : le dernier commit qui n'est ni une synchronisation de la méthode
(`chore(methodo)`, `chore|fix(rules|hooks)`), ni de la documentation (`docs…`, rapports de séance compris), ni une
montée de dépendances (`chore(deps)`). Sans cette exclusion, chaque propagation ferait croire que tous les projets
ont changé (mesuré par la relecture du 2026-11-01 : rok-recruit à 155 jours de « retard » pour des synchronisations).
Limite écrite : la liste est ouverte (un commit de méthode au sujet inhabituel compte comme du code) et `git log`
lit la branche sortie du dépôt principal.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROJETS_DIR = Path(os.environ.get("PROJETS_DIR", "D:/30-Dev-Projects"))
SHINZO_DIR = Path(os.environ.get("SHINZO_DIR", str(PROJETS_DIR / "Shinzo")))

# L'étiquette OUVRE une ligne (gras, citation et espaces tolérés), ou est posée en gras (`**Dernière MAJ**`) au milieu
# d'une ligne d'en-tête ; le mot cité sans gras dans une phrase ne compte pas. Clés d'en-tête YAML `updated:` / `mis à jour:`.
_LIBELLE = r"(?:Derni[eè]re\s+(?:MAJ|mise\s+[àa]\s+jour)|Mise\s+[àa]\s+jour|updated|mis\s+[àa]\s+jour)"
_ETIQUETTE_RE = re.compile(
    r"(?:^[\s>*_`-]*|\*\*)" + _LIBELLE + r"[\s*_`]*:?[\s*_`]*(\d{4})-(\d{2})-(\d{2})",
    re.IGNORECASE | re.MULTILINE,
)
# Ni synchronisation de la méthode, ni documentation, ni montée de dépendances : le code n'a pas bougé.
_COMMITS_IGNORES = ("^docs", "^chore(methodo)", "^chore(deps)", "^chore(hooks)", "^chore(rules)", "^fix(rules)", "^fix(hooks)")
_LIGNES_LUES = 60


@dataclass(frozen=True)
class Etat:
    nom: str
    etat: str  # a_jour | en_retard | absente | sans_date | sans_depot
    retard: int = 0
    date_fiche: date | None = None
    date_code: date | None = None


def date_fiche(texte: str) -> date | None:
    """La date de mise à jour portée par l'en-tête de la fiche (les premières lignes), ou None."""
    entete = "\n".join((texte or "").splitlines()[:_LIGNES_LUES])
    m = _ETIQUETTE_RE.search(entete)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def date_code(depot: Path) -> date | None:
    """Date du dernier commit de code du dépôt, ou None (dépôt absent, vide ou illisible)."""
    if not (depot / ".git").exists():
        return None
    commande = ["git", "-C", str(depot), "log", "-1", "--format=%cs", "--invert-grep"]
    commande += [f"--grep={motif}" for motif in _COMMITS_IGNORES]
    try:
        sortie = subprocess.run(commande, capture_output=True, text=True, timeout=20)
        return date.fromisoformat(sortie.stdout.strip()) if sortie.returncode == 0 and sortie.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


# Dépôt dont la fiche porte un autre nom (index de Shinzo : Hikari-Stream.md pour le dépôt Hikari).
FICHE_SOUS_UN_AUTRE_NOM = {"Hikari": "Hikari-Stream"}


def chemin_fiche(nom: str, shinzo: Path = SHINZO_DIR) -> Path:
    return shinzo / "02-Projets" / f"{FICHE_SOUS_UN_AUTRE_NOM.get(nom, nom)}.md"


def etat_fiche(nom: str, projets: Path = PROJETS_DIR, shinzo: Path = SHINZO_DIR, seuil: int = 14) -> Etat:
    """L'état de la fiche d'un projet : en retard quand le code a bougé de plus de `seuil` jours après elle."""
    code = date_code(projets / nom)
    if code is None:
        return Etat(nom, "sans_depot")
    fiche = chemin_fiche(nom, shinzo)
    if not fiche.is_file():
        return Etat(nom, "absente", date_code=code)
    try:
        ecrite = date_fiche(fiche.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        ecrite = None
    if ecrite is None:
        return Etat(nom, "sans_date", date_code=code)
    retard = max((code - ecrite).days, 0)
    return Etat(nom, "en_retard" if retard > seuil else "a_jour", retard, ecrite, code)


def bilan(noms: list[str], projets: Path = PROJETS_DIR, shinzo: Path = SHINZO_DIR, seuil: int = 14) -> Counter:
    """Nombre de projets par état. Une clé absente vaut zéro."""
    return Counter(etat_fiche(n, projets, shinzo, seuil).etat for n in noms)
