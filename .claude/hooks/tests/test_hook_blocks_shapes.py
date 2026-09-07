"""La liste des formes d'evenement est confrontee a de VRAIS transcripts.

POURQUOI CE FICHIER EXISTE, et pas seulement un test de plus dans la suite.

Le 2026-09-07, le compteur de blocages a ete corrige trois fois dans la journee.
La troisieme version remplacait une liste de ce qu'il faut ECARTER — ouverte,
donc toujours depassee — par une liste FERMEE de ce qu'on accepte. Bonne idee,
mauvaise execution : la liste avait ete etablie sur UN SEUL canal, le resultat
d'outil. Une relecture sur un modele different a trouve la 5e forme (`[HOOK=`),
presente dans 55 fichiers de session, et donc de vrais blocages perdus.

La lecon n'est pas « il manquait une forme ». Elle est : une liste fermee ne
vaut que par l'etendue de ce qu'on a regarde avant de la fermer. Corriger la 5e
forme a la main laisserait la 6e arriver de la meme facon.

Ce test regarde donc le terrain, pas mon imagination : il relit les transcripts
reels de ce poste, cherche les entrees que le harnais marque comme un blocage,
et echoue si l'une porte une ligne de blocage qu'`EVENEMENT_RE` ne reconnait
pas. Il se saute la ou les transcripts n'existent pas — la verite du terrain
n'est pas portable, et un test qui echoue faute de donnees se fait desactiver.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
HOOK = RACINE / ".claude/hooks/lifecycle/hook-blocks-stats.py"
_spec = importlib.util.spec_from_file_location("hook_blocks_stats", HOOK)
hbs = importlib.util.module_from_spec(_spec)
sys.modules["hook_blocks_stats"] = hbs
_spec.loader.exec_module(hbs)

TRANSCRIPTS = Path.home() / ".claude" / "projects"
# Ce que le harnais nomme lui-meme un blocage. C'est le seul juge : on ne
# devine pas qu'une entree est un evenement, on lit son etiquette.
ETIQUETTES = ("blockingError", "hook_blocking_error")


def _fichiers_a_lire(par_projet=6):
    """Les transcripts les plus RECENTS de CHAQUE projet, jamais les 40 premiers.

    Defaut trouve par relecture croisee le 2026-09-07 : la premiere version
    lisait `sorted(...)[:40]` sur 167 fichiers. Le tri etant alphabetique, elle
    couvrait toujours les sept memes projets — et **jamais Kata**, le depot que
    ce test protege. Un filet qui regarde toujours au meme endroit reste vert
    pour toujours ; c'est un controle mort qui a l'air vivant.

    On prend donc les plus recents de chaque projet : la couverture suit
    l'atelier au lieu de suivre l'alphabet.
    """
    if not TRANSCRIPTS.is_dir():
        return []
    fichiers = []
    for projet in sorted(TRANSCRIPTS.iterdir()):
        if not projet.is_dir():
            continue
        recents = sorted(projet.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        fichiers.extend(recents[:par_projet])
    return fichiers


def _textes_de_blocage():
    """Les textes que le harnais a etiquetes comme blocage, sur ce poste."""
    trouves = []
    for fichier in _fichiers_a_lire():
        try:
            contenu = fichier.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ligne in contenu.splitlines():
            if not any(e in ligne for e in ETIQUETTES):
                continue  # tri grossier, pour ne pas analyser 167 fichiers entiers
            try:
                entree = json.loads(ligne)
            except (json.JSONDecodeError, ValueError):
                continue
            texte = _texte_du_blocage(entree)
            if texte:
                trouves.append(texte)
    return trouves


def _texte_du_blocage(entree):
    """Le texte porte par le CHAMP d'erreur, jamais un message qui en parle.

    Premiere version : toute ligne du fichier contenant le mot `blockingError`.
    Elle attrapait donc une conversation QUI PARLE de blocage — dont le rapport
    du relecteur lui-meme. Troisieme fois dans la journee que la meme erreur de
    forme revient : selectionner sur un mot present au lieu de la structure.

    On descend donc jusqu'au champ, et on ne lit que ce qu'il contient.
    """
    morceaux = []

    def descendre(noeud):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle in ETIQUETTES:
                    morceaux.append(hbs.extract_text(valeur))
                else:
                    descendre(valeur)
        elif isinstance(noeud, list):
            for valeur in noeud:
                descendre(valeur)

    descendre(entree)
    return "\n".join(m for m in morceaux if m)


def test_every_real_block_shape_is_covered():
    """Une forme de blocage que la liste ne reconnait pas fait rougir ce test.

    C'est ce qui manquait le 2026-09-07 : la 5e forme a ete trouvee par un
    relecteur, pas par la suite. Le prochain ecart sera trouve ici.
    """
    textes = _textes_de_blocage()
    if not textes:
        pytest.skip("aucun transcript sur ce poste — la verite du terrain n'est pas portable")

    inconnues = []
    for texte in textes:
        for ligne in texte.splitlines():
            if "BLOCKED:" not in ligne:
                continue
            if hbs.EVENEMENT_RE.match(ligne):
                continue
            depart = ligne.strip()[:60]
            # Une ligne de suite (le detail sous le message) n'ouvre pas un
            # evenement : seules celles qui PORTENT le marqueur en tete comptent.
            if ligne.lstrip().startswith("BLOCKED:") or "BLOCKED:" in ligne.split(":")[0]:
                inconnues.append(depart)
            elif ligne[:1] not in (" ", "\t", "-", "+", "#"):
                inconnues.append(depart)
    assert not inconnues, (
        "formes de blocage reelles que la liste fermee ne reconnait pas :\n  "
        + "\n  ".join(sorted(set(inconnues))[:8])
    )


def test_the_net_looks_at_the_repository_it_protects():
    """Un filet qui regarde toujours ailleurs reste vert pour toujours.

    Premiere version : les 40 premiers fichiers par ordre alphabetique, sur 167.
    Elle couvrait sept projets, toujours les memes, et jamais Kata — celui-la
    meme dont ce test garde le compteur.
    """
    fichiers = _fichiers_a_lire()
    if not fichiers:
        pytest.skip("aucun transcript sur ce poste")
    projets = {f.parent.name for f in fichiers}
    assert len(projets) > 7, "le filet doit couvrir tout l'atelier, pas son debut alphabetique"
    ici = RACINE.name
    if any(ici in p.name for p in TRANSCRIPTS.iterdir() if p.is_dir()):
        assert any(ici in p for p in projets), f"le depot {ici} doit etre regarde"


def test_the_five_measured_shapes_are_accepted():
    """Les cinq formes viennent d'une mesure, jamais d'une supposition."""
    formes = [
        "PreToolUse:Bash hook error: [x]: BLOCKED: un motif",
        "PostToolUse:Edit hook blocking error: [x]: BLOCKED: un motif",
        "BLOCKED: un motif",
        '[bash ".../_run.sh" quality/x.py]: BLOCKED: un motif',
        '[HOOK="$(git rev-parse --show-toplevel)/.claude/hooks/guards/x.py"]: BLOCKED: un motif',
    ]
    for forme in formes:
        assert hbs.EVENEMENT_RE.match(forme), forme


def test_code_that_merely_talks_about_a_block_is_still_rejected():
    """Le garde-fou du gonflement, dans le meme fichier que celui du manque."""
    for ligne in (
        '    msg = "PreToolUse:Bash hook error: [x]: BLOCKED: un motif"',
        '+           "PreToolUse:[x]: BLOCKED: un motif"',
        "#   PreToolUse:Bash hook error: [x]: BLOCKED: un motif",
        "    'PreToolUse: [x]: BLOCKED: un motif'",
    ):
        assert not hbs.EVENEMENT_RE.match(ligne), ligne
