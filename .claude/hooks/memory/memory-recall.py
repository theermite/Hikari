#!/usr/bin/env python3
"""Rappel de mémoire — PreToolUse Bash. Rappelle, ne bloque jamais.

Plan d'action point 3, seconde brique.

L'INCIDENT QUI LE JUSTIFIE. Le 2026-09-02, une commande dangereuse a été lancée
alors qu'un souvenir vieux de 11 jours l'interdisait explicitement. Le souvenir
existait, il était juste, il n'a pas été ouvert.

Le sommaire généré rend les 601 souvenirs VISIBLES. Il ne garantit pas qu'on les
LISE au moment où ils comptent. L'audit avait mesuré le vrai chiffre : zéro
consultation tracée sur dix sessions. **Un corpus visible mais jamais rouvert
reste une archive.**

CE QU'IL FAIT. Avant une commande shell, il compare les mots de la commande aux
souvenirs du sommaire, et remonte celui qui parle du sujet. Il lit le SOMMAIRE
GÉNÉRÉ, pas les 601 fichiers : un fichier au lieu de six cents, et toujours à
jour puisqu'il est produit.

POURQUOI IL SE TAIT SOUVENT. Un rappel à chaque commande deviendrait du bruit, et
le bruit se filtre mentalement en trois minutes — c'est la leçon du 2026-08-30,
où un garde-fou fait de mots trop généraux gênait du travail légitime et a failli
être débranché. Trois freins : un mot commun ne suffit jamais, deux souvenirs au
maximum, et chacun n'est rappelé qu'une fois par session.

SANS HOOK (autre harnais). Ouvrir `Shinzo/05-Memoire/MEMORY.md` avant toute
commande destructive ou inhabituelle, et le dire dans le rapport.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root, get_command, pass_through, read_hook_input  # type: ignore

# Defaut D3, relecture independante du 2026-09-06 : un chemin en dur ne trouve
# rien hors du poste de Jay, et `_lignes_index` avale l'erreur — le rappel se
# tairait sur le serveur sans un mot, pendant que la sonde le compterait parmi
# les « operationnels ». Meme variable que le hook voisin qui ecrit la memoire.
SHINZO = Path(os.environ.get("SHINZO_DIR", "D:/30-Dev-Projects/Shinzo"))
INDEX = SHINZO / "05-Memoire" / "MEMORY.md"
ETAT = "memory-recalled.json"

MAX_RAPPELS = 2
# Deux mots partagés, ou un seul s'il est rare — voir `_score`.
SEUIL = 2

# Mots trop courants pour prouver quoi que ce soit. Un rappel déclenché par
# « avant » ou « fichier » serait du bruit, et le bruit tue la garde.
BANALS = {
    "avant", "apres", "toujours", "jamais", "faire", "quand", "dans", "pour", "avec",
    "cette", "celui", "celle", "leur", "sont", "était", "etait", "plus", "moins",
    "tout", "tous", "toute", "sans", "sous", "chaque", "meme", "même", "aussi",
    "file", "files", "fichier", "fichiers", "code", "test", "tests", "projet",
    "session", "sessions", "jour", "jours", "chose", "quelque", "table", "base",
    "the", "and", "not", "with", "from", "that", "this", "true", "false", "null",
}


# Les gestes de LECTURE, qui ne changent rien et n'ont donc jamais besoin d'un
# souvenir. C'est une liste BLANCHE, jamais une liste noire : une liste noire de
# commandes risquees serait « toujours une liste a rallonger » (lecon Kanee
# 2026-08-31), alors que l'ensemble des gestes inoffensifs est stable et fini.
# Mesure du 2026-09-05 : sans ce filtre, `git status` remontait deux souvenirs —
# du bruit sur la commande la plus courante de toutes.
ROUTINE = {
    "ls", "cat", "head", "tail", "grep", "rg", "find", "echo", "pwd", "wc",
    "which", "type", "stat", "du", "df", "date", "env", "printf", "sed", "awk",
    "pytest", "diff", "less", "more", "tree", "file", "basename", "dirname",
}
GIT_LECTURE = {"status", "log", "diff", "show", "branch", "remote", "config",
               "rev-parse", "describe", "blame", "shortlog", "ls-files"}


def est_routine(commande: str) -> bool:
    """Vrai si la commande ne fait que LIRE. Elle n'a alors rien a rappeler."""
    morceaux = (commande or "").strip().split()
    if not morceaux:
        return True
    tete = morceaux[0].rsplit("/", 1)[-1]
    if tete == "git":
        return len(morceaux) > 1 and morceaux[1] in GIT_LECTURE
    return tete in ROUTINE


def _mots(texte: str) -> set[str]:
    """Les mots qui portent du sens : au moins 4 lettres, jamais un mot banal."""
    bruts = re.findall(r"[a-zA-ZÀ-ÿ0-9_.-]{4,}", (texte or "").lower())
    return {m.strip(".-_") for m in bruts if m.strip(".-_") not in BANALS}


def _lignes_index(index: Path) -> list[dict]:
    """Lit le sommaire GÉNÉRÉ. Un sommaire absent n'est pas une erreur — il faut
    juste le produire (`scripts/generate-memory-index.py`)."""
    try:
        texte = Path(index).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    entrees = []
    for ligne in texte.splitlines():
        trouve = re.match(r"^- \[(.+?)\]\((.+?)\)\s*—\s*(.*)$", ligne.strip())
        if trouve:
            entrees.append({
                "nom": trouve.group(1),
                "fichier": trouve.group(2),
                "ligne": ligne.strip(),
                "mots": _mots(f"{trouve.group(1)} {trouve.group(2)} {trouve.group(3)}"),
            })
    return entrees


def _rarete(entrees: list[dict]) -> dict:
    compte: dict = {}
    for entree in entrees:
        for mot in entree["mots"]:
            compte[mot] = compte.get(mot, 0) + 1
    return compte


def _score(partages: set[str], rarete: dict) -> int:
    """Deux mots partagés suffisent. Un seul suffit s'il est RARE — « taskkill »
    n'apparaît que dans un souvenir, il désigne donc précisément celui-là."""
    if len(partages) >= SEUIL:
        return len(partages)
    if len(partages) == 1 and rarete.get(next(iter(partages)), 99) <= 2:
        return SEUIL
    return 0


def souvenirs_pertinents(commande: str, index: Path | None = None) -> list[dict]:
    if est_routine(commande):
        return []
    entrees = _lignes_index(index or INDEX)
    if not entrees:
        return []
    mots_commande = _mots(commande)
    rarete = _rarete(entrees)
    notes = []
    for entree in entrees:
        note = _score(mots_commande & entree["mots"], rarete)
        if note:
            notes.append((note, entree))
    notes.sort(key=lambda couple: -couple[0])
    return [entree for _, entree in notes[:MAX_RAPPELS]]


def _chemin_etat() -> Path:
    return find_repo_root() / ".claude" / "state" / ETAT


def doit_rappeler(fichier: str, chemin_etat: Path | None = None) -> bool:
    """Une fois par souvenir et par session. Un état illisible ne fait jamais
    taire le rappel — mieux vaut un rappel de trop qu'un silence par panne."""
    chemin = Path(chemin_etat) if chemin_etat else _chemin_etat()
    try:
        deja = json.loads(chemin.read_text(encoding="utf-8"))
        deja = deja if isinstance(deja, list) else []
    except (OSError, ValueError):
        deja = []
    if fichier in deja:
        return False
    deja.append(fichier)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(deja, ensure_ascii=False), encoding="utf-8", newline="\n")
    except OSError as error:
        print(f"[DEBUG][memory-recall] etat non ecrit: {error}", file=sys.stderr)
    return True


def build_decision(data: dict, index: Path | None = None, deja_rappele=None) -> dict | None:
    """Rend le rappel, ou None. Ne lève jamais."""
    if not isinstance(data, dict) or not isinstance(data.get("tool_input"), dict):
        return None
    commande = get_command(data)
    if not commande:
        return None
    trouves = souvenirs_pertinents(commande, index)
    verifie = deja_rappele or doit_rappeler
    retenus = [t for t in trouves if verifie(t["fichier"])]
    if not retenus:
        return None
    corps = "\n".join(f"  {t['ligne']}" for t in retenus)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "[MEMOIRE] Un souvenir parle de ce que tu t'apprêtes à faire :\n"
                f"{corps}\n"
                "  Ouvre-le avant d'exécuter si la commande est destructive ou "
                "inhabituelle. Dossier : Shinzo/05-Memoire/"
            ),
        }
    }


def main() -> None:
    try:
        _, data = read_hook_input()
        decision = build_decision(data)
        if decision is not None:
            print(json.dumps(decision, ensure_ascii=False))
            return
    except Exception as error:  # noqa: BLE001 — un rappel ne casse jamais une commande
        print(f"[DEBUG][memory-recall] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
