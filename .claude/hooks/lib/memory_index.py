#!/usr/bin/env python3
"""Sommaire de la mémoire — produit depuis les fichiers, jamais recopié.

Plan d'action point 3 (`docs/Plan-Action-Methodologie-2026-09.md`).

POURQUOI. Mesuré le 2026-09-05 : **601 souvenirs, 28 dans le sommaire**, soit
4,7 %. Coût démontré, pas supposé : le 2026-09-02, une commande dangereuse a été
lancée alors qu'un souvenir vieux de 11 jours l'interdisait. Le souvenir
existait, il était juste, il n'a pas été ouvert — parce qu'il n'apparaissait
nulle part.

Un sommaire recopié à la main vieillit et ment. Même famille que l'inventaire de
composants : 79 annoncés, 83 déclarés, 149 réels, le même jour. La seule sortie
est de le PRODUIRE.

DEUX SOMMAIRES, DEUX RÔLES — la contradiction tranchée le 2026-09-05 :

| Fichier | Rôle | Contenu |
|---|---|---|
| `README.md` | Le sommaire complet, pour naviguer | les 601, groupés par type |
| `MEMORY.md` | Celui que l'outil CHARGE à chaque session | ce qui change le comportement |

Notre règle disait « l'index est README, ne créez pas MEMORY.md ». La réalité est
que MEMORY.md est injecté à chaque démarrage : l'interdire revenait à interdire
le seul index réellement lu. Les deux existent, chacun avec sa raison.

**Pourquoi MEMORY.md ne prend que `feedback` et `user`** : ce sont les souvenirs
qui changent la façon de travailler. Les mémoires de projet et de référence se
cherchent quand on en a besoin ; celles-là doivent être là AVANT qu'on sache
qu'on en a besoin. Coût mesuré : environ 280 lignes, ~7 000 jetons par session.
Au-delà de 400 lignes, rouvrir la question.

USAGE
    python .claude/hooks/lib/memory_index.py            # écrit les deux sommaires
    python .claude/hooks/lib/memory_index.py --check    # code 1 si un sommaire a vieilli
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Chemin de ce poste, surchargeable — son voisin `memory-autocommit.py` honore
# deja `SHINZO_DIR`, pas celui-ci (3e relecture independante, 2026-09-07). Ce
# fichier part sur 32 depots et sur le serveur, ou Shinzo vit ailleurs.
MEMOIRE = Path(os.environ.get("SHINZO_DIR", "D:/30-Dev-Projects/Shinzo")) / "05-Memoire"
INDEX_COMPLET = "README.md"
INDEX_CHARGE = "MEMORY.md"
NON_MEMOIRES = {INDEX_COMPLET, INDEX_CHARGE}

# Ceux qui changent le comportement — ils doivent être là avant qu'on sache
# qu'on en a besoin.
TYPES_CHARGES = ("user", "feedback")

MARQUE = "<!-- SOMMAIRE GENERE — ne pas editer a la main -->"

LEGENDE = {
    "user": "Qui est l'utilisateur",
    "feedback": "Ce qu'il a corrigé dans ma façon de travailler",
    "project": "Ce qui court sur un projet",
    "reference": "Pointeurs vers des ressources",
    "inconnu": "En-tête illisible — à réparer",
}


def _champ(entete: str, cle: str) -> str:
    trouve = re.search(rf"^\s*{cle}:\s*(.+)$", entete, re.M)
    return trouve.group(1).strip().strip('"').strip("'") if trouve else ""


def lire_memoires(dossier: Path | None = None) -> list[dict]:
    """Lit chaque fichier. Les DEUX formes d'en-tête sont acceptées : la forme
    documentée (plate) et celle que l'outil écrit vraiment (imbriquée sous
    `metadata:`). Un lecteur qui n'en lit qu'une produit un sommaire faux et
    silencieux — 105 fichiers sur 601 utilisent la seconde."""
    dossier = Path(dossier) if dossier else MEMOIRE
    fiches: list[dict] = []
    for chemin in sorted(dossier.glob("*.md")):
        if chemin.name in NON_MEMOIRES:
            continue
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        entete = re.match(r"^---\n(.*?)\n---", texte, re.S)
        entete = entete.group(1) if entete else ""
        fiches.append({
            "fichier": chemin.name,
            "name": _champ(entete, "name") or chemin.stem,
            "description": _champ(entete, "description"),
            # un fichier sans en-tête est SIGNALÉ, jamais jeté : le jeter
            # fabriquerait un sommaire qui ment par omission.
            "type": _champ(entete, "type") or "inconnu",
            "date": _champ(entete, "date"),
        })
    return fiches


def _ligne(fiche: dict) -> str:
    desc = fiche["description"] or "(sans description)"
    return f"- [{fiche['name']}]({fiche['fichier']}) — {desc}"


# Le harnais coupe MEMORY.md a 200 lignes OU 25 Ko, selon ce qui arrive en premier. Mesure du 2026-11-02 :
# 275 souvenirs charges, 286 lignes et 37,6 Ko -- 84 lignes de fin de liste etaient COUPEES sans que personne le voie.
# Meme le seul lien `[titre](fichier)` de chaque souvenir pese 28,7 Ko : il n'y a pas de forme a une ligne par
# souvenir qui tienne. Le sommaire charge ne porte donc que le NOM DE FICHIER (sans .md), range a plusieurs par
# ligne ; titre et description complets restent dans README.md, jamais charge. Et si meme cela deborde, il le dit.
MAX_LIGNES_CHARGEES = 190   # sous les 200 du harnais : marge pour l'en-tete qu'il ajoute
MAX_OCTETS_CHARGES = 24_000  # sous les 25 Ko
LARGEUR_LIGNE = 150
SEPARATEUR = " · "


def _entrees(fiches: list[dict]) -> list[tuple[str, str]]:
    """[(type, nom de fichier sans .md)] : user d'abord, puis feedback, chacun par ordre alphabetique."""
    return [(t, f["fichier"].removesuffix(".md")) for t in TYPES_CHARGES
            for f in sorted((f for f in fiches if f["type"] == t), key=lambda f: f["fichier"].lower())]


def _paquets(noms: list[str]) -> list[str]:
    lignes: list[str] = []
    courante = ""
    for nom in noms:
        if courante and len(courante) + len(SEPARATEUR) + len(nom) > LARGEUR_LIGNE:
            lignes.append(courante)
            courante = ""
        courante = f"{courante}{SEPARATEUR}{nom}" if courante else nom
    return lignes + ([courante] if courante else [])


def _corps_charge(entrees: list[tuple[str, str]]) -> list[str]:
    blocs: list[str] = []
    for type_ in TYPES_CHARGES:
        noms = [n for t, n in entrees if t == type_]
        if noms:
            blocs += [f"\n## {type_} — {LEGENDE.get(type_, '')} ({len(noms)})\n", *_paquets(noms)]
    return blocs


def _tient(texte: str) -> bool:
    return len(texte.splitlines()) <= MAX_LIGNES_CHARGEES and len(texte.encode("utf-8")) <= MAX_OCTETS_CHARGES


def _sections(fiches: list[dict], types: tuple[str, ...], rendre=_ligne) -> list[str]:
    blocs = []
    for type_ in types:
        lot = [f for f in fiches if f["type"] == type_]
        if not lot:
            continue
        blocs.append(f"\n## {type_} — {LEGENDE.get(type_, '')} ({len(lot)})\n")
        blocs.extend(rendre(f) for f in sorted(lot, key=lambda f: f["name"].lower()))
    return blocs


def rendre_index_complet(fiches: list[dict]) -> str:
    types = tuple(dict.fromkeys([*TYPES_CHARGES, "project", "reference", "inconnu"]))
    tete = [
        "# 05 — Mémoire",
        "",
        MARQUE,
        f"> **{len(fiches)} souvenirs.** Sommaire produit depuis les fichiers par",
        "> `Kata/.claude/hooks/lib/memory_index.py`. Toute modification à la main sera écrasée.",
        "> Le format d'un souvenir et la règle d'écriture : `Kata/.claude/rules/Memory.md`.",
        "",
        "> **`MEMORY.md`** est le sommaire CHARGÉ à chaque session : il ne porte que",
        f"> `{'` et `'.join(TYPES_CHARGES)}`. Celui-ci porte tout.",
    ]
    return "\n".join(tete + _sections(fiches, types)) + "\n"


def _index_charge_pour(fiches: list[dict], retenus: list[tuple[str, str]], total: int) -> str:
    tete = [
        "# Mémoire",
        "",
        MARQUE,
        f"> **{total} souvenirs qui changent la façon de travailler**, sur {len(fiches)} au total.",
        "> Chaque entrée est un fichier de ce dossier (ajouter `.md`). Titres et descriptions : `README.md`.",
        "> Sommaire généré par `Kata/.claude/hooks/lib/memory_index.py` — ne pas éditer.",
    ]
    reste = total - len(retenus)
    queue = [f"\n> … et {reste} souvenirs de plus, rangés dans README.md (le sommaire chargé ne tient pas plus)."] if reste else []
    return "\n".join(tete + _corps_charge(retenus) + queue) + "\n"


def rendre_index_charge(fiches: list[dict]) -> str:
    """Le sommaire que l'outil charge : tous les souvenirs qui changent le comportement, tant que 200 lignes / 25 Ko tiennent."""
    entrees = _entrees(fiches)
    bas, haut = 0, len(entrees)
    while bas < haut:  # le plus grand nombre d'entrees qui tient (la taille croit avec le nombre)
        milieu = (bas + haut + 1) // 2
        if _tient(_index_charge_pour(fiches, entrees[:milieu], len(entrees))):
            bas = milieu
        else:
            haut = milieu - 1
    return _index_charge_pour(fiches, entrees[:bas], len(entrees))


def ecrire_index(dossier: Path | None = None) -> dict:
    dossier = Path(dossier) if dossier else MEMOIRE
    fiches = lire_memoires(dossier)
    (dossier / INDEX_COMPLET).write_text(rendre_index_complet(fiches),
                                         encoding="utf-8", newline="\n")
    (dossier / INDEX_CHARGE).write_text(rendre_index_charge(fiches),
                                        encoding="utf-8", newline="\n")
    return {"total": len(fiches),
            "charges": len([f for f in fiches if f["type"] in TYPES_CHARGES])}


def verifier(dossier: Path | None = None) -> list[str]:
    """Rend les écarts entre les fichiers et les sommaires. Vide = à jour."""
    dossier = Path(dossier) if dossier else MEMOIRE
    fiches = lire_memoires(dossier)
    problemes = []
    for nom, rendu in ((INDEX_COMPLET, rendre_index_complet(fiches)),
                       (INDEX_CHARGE, rendre_index_charge(fiches))):
        chemin = dossier / nom
        try:
            actuel = chemin.read_text(encoding="utf-8")
        except OSError:
            problemes.append(f"{nom} : absent — aucun sommaire ne couvre les souvenirs")
            continue
        if actuel != rendu:
            problemes.append(f"{nom} : perime — relancer .claude/hooks/lib/memory_index.py")
    return problemes


def main() -> int:
    if "--check" in sys.argv:
        problemes = verifier()
        for probleme in problemes:
            print(f"  - {probleme}")
        print("Sommaires a jour." if not problemes else "Sommaires en derive.")
        return 1 if problemes else 0
    etat = ecrire_index()
    print(f"Sommaires produits : {etat['total']} souvenirs indexes, "
          f"dont {etat['charges']} charges a chaque session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
