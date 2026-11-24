"""Registre des décisions — « est-ce tranché ? » a une seule réponse: celle du fichier.

Jay 2026-11-24: les décisions n'avaient pas de maison (fiche, reprises, doctrine, 270 souvenirs), donc savoir si une question
était close dépendait de ma lecture, et elle a failli deux fois dans la journée. Ici: un fichier structuré (`02-Projets/_Decisions.json`
dans Shinzo), des valeurs fermées, une source qui doit exister, une date réelle. Bibliothèque standard seule (les gardes tournent
dans 28 dépôts). Le fichier est la source; toute liste « à trancher » se génère de lui, jamais à la main.

Qui décide (règle 01): `jay` = le quoi (goût, vision, arrêt), `takumi` = le comment. Une décision `takumi` n'est jamais une question
pour Jay. Statuts: `ouverte` (à trancher), `tranchee`, `remplacee` (par une autre), `a_recouper` (reprise d'une liste ancienne,
état non vérifié: on le dit au lieu de le deviner).
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

STATUTS = ("ouverte", "tranchee", "remplacee", "a_recouper")
QUI = ("jay", "takumi")
OBLIGATOIRES = ("id", "sujet", "qui", "statut", "date", "source")
FORME_ID = re.compile(r"^D-\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$")
_ID_DANS_TEXTE = re.compile(r"D-\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*")

PROJETS_DIR = Path(os.environ.get("PROJETS_DIR", "D:/30-Dev-Projects"))


def shinzo_dir() -> Path:
    return Path(os.environ.get("SHINZO_DIR", str(PROJETS_DIR / "Shinzo")))


def chemin_registre(shinzo: Path | None = None) -> Path:
    return (shinzo or shinzo_dir()) / "02-Projets" / "_Decisions.json"


def charger(chemin: Path | None = None) -> list[dict]:
    """Les décisions du fichier; liste vide si absent ou illisible (un garde ne casse jamais sur un fichier absent)."""
    try:
        contenu = json.loads((chemin or chemin_registre()).read_text(encoding="utf-8"))
        liste = contenu.get("decisions") if isinstance(contenu, dict) else None
        return [x for x in liste if isinstance(x, dict)] if isinstance(liste, list) else []
    except (OSError, ValueError):
        return []


def _erreurs_champs(x: dict, projets: Path) -> list[str]:
    ident = str(x.get("id", "?"))
    erreurs = [f"{ident}: champ obligatoire manquant ou vide: {c}" for c in OBLIGATOIRES if not str(x.get(c) or "").strip()]
    if x.get("id") and not FORME_ID.match(str(x["id"])):
        erreurs.append(f"{ident}: identifiant mal formé (attendu D-AAAA-MM-JJ-sujet)")
    if x.get("statut") and x["statut"] not in STATUTS:
        erreurs.append(f"{ident}: statut inconnu {x['statut']!r} (admis: {', '.join(STATUTS)})")
    if x.get("qui") and x["qui"] not in QUI:
        erreurs.append(f"{ident}: qui inconnu {x['qui']!r} (admis: {', '.join(QUI)})")
    erreurs += _erreurs_date_source(x, ident, projets)
    return erreurs


def _erreurs_date_source(x: dict, ident: str, projets: Path) -> list[str]:
    erreurs = []
    if x.get("date"):
        try:
            if date.fromisoformat(str(x["date"])) > date.today():
                erreurs.append(f"{ident}: date dans le futur")
        except ValueError:
            erreurs.append(f"{ident}: date impossible {x['date']!r}")
    if x.get("source") and not (projets / str(x["source"])).exists():
        erreurs.append(f"{ident}: source introuvable: {x['source']}")
    return erreurs


def _erreurs_sens(x: dict, ids: set[str]) -> list[str]:
    ident = str(x.get("id", "?"))
    statut, reponse = x.get("statut"), str(x.get("reponse") or "").strip()
    erreurs = []
    if statut in ("tranchee", "remplacee") and not reponse:
        erreurs.append(f"{ident}: une décision {statut} porte sa réponse")
    if statut in ("ouverte", "a_recouper") and reponse:
        erreurs.append(f"{ident}: une décision {statut} n'a pas de réponse")
    if statut == "remplacee":
        cible = str(x.get("remplace_par") or "")
        if not cible:
            erreurs.append(f"{ident}: une décision remplacée nomme celle qui la remplace (remplace_par)")
        elif cible not in ids:
            erreurs.append(f"{ident}: le remplaçant {cible} n'existe pas")
    return erreurs


def _erreurs_collision(decisions: list[dict]) -> list[str]:
    """Une decision OUVERTE dont le sujet reveille les mots d'une decision deja tranchee serait refusee a tort par la porte
    de question (relecture du 2026-11-24): on la refuse a l'enregistrement, pas a la question."""
    fermees = [x for x in decisions if x.get("statut") in ("tranchee", "remplacee") or x.get("qui") == "takumi"]
    erreurs = []
    for x in decisions:
        if x.get("statut") in ("ouverte", "a_recouper") and x.get("qui") == "jay":
            for f in trouver(str(x.get("sujet") or ""), [g for g in fermees if g is not x]):
                erreurs.append(f"{x.get('id', '?')}: son sujet reveille les mots de la decision tranchee {f['id']} (collision: change les mots de l'une)")
    return erreurs


def valider(decisions: list[dict], projets: Path | None = None) -> list[str]:
    """Les défauts du registre, un par ligne; liste vide = valide. `projets` = dossier qui contient Shinzo, Kata…"""
    projets = projets or PROJETS_DIR
    ids = [str(x.get("id", "")) for x in decisions]
    erreurs = [f"{i}: identifiant en double" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for x in decisions:
        erreurs += _erreurs_champs(x, projets) + _erreurs_sens(x, set(ids))
    return erreurs + _erreurs_collision(decisions)


def _mots_presents(x: dict, bas: str) -> bool:
    mots = [str(m).lower() for m in x.get("mots") or [] if str(m).strip()]
    return bool(mots) and all(re.search(r"(?<!\w)" + re.escape(m), bas) for m in mots)  # debut de mot: lot n'est pas dans pilote


def trouver(texte: str, decisions: list[dict]) -> list[dict]:
    """Les décisions que ce texte nomme (par identifiant) ou dont TOUS les mots-clés y figurent (sans casse)."""
    bas = (texte or "").lower()
    cites = set(_ID_DANS_TEXTE.findall(texte or ""))
    return [x for x in decisions if x.get("id") in cites or _mots_presents(x, bas)]


def ouvertes(decisions: list[dict]) -> list[dict]:
    """Celles qui attendent une réponse ou une vérification (jamais une décision de Takumi: ce n'est pas une question pour Jay)."""
    return [x for x in decisions if x.get("statut") in ("ouverte", "a_recouper")]
