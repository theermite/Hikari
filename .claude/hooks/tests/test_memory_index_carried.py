"""Un souvenir ecrit emporte le sommaire avec lui.

Ne 2026-09-06. Deux defauts de la meme famille, trouves en cherchant pourquoi le
sommaire de memoire avait derive :

1. `memory/memory-autocommit.py` n'etait CABLE SUR AUCUN EVENEMENT. La regle
   Memoire annonce pourtant « un hook PostToolUse commet + pousse Shinzo a
   chaque ecriture », et donne comme preuve la ligne que ce hook imprime. Une
   regle BLOQUANTE decrivait un mecanisme qui ne tournait pas.

2. Meme cable, il commettait le souvenir sans jamais regenerer le sommaire.
   Chaque souvenir ecrit rendait donc l'index un peu plus faux — mesure du
   jour : 601 annonces pour 604 fichiers, 28 indexes pour 283.

Un generateur qu'on n'execute pas produit exactement la meme derive qu'un
sommaire recopie a la main.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
HOOK = RACINE / ".claude/hooks/memory/memory-autocommit.py"

SOUVENIR = """---
name: essai
description: un souvenir d essai
type: feedback
---

Le contenu.
"""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, check=True)


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "Shinzo"
    (root / "05-Memoire").mkdir(parents=True)
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "branch", "-M", "main")
    (root / "README.md").write_text("seed", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "-u", "origin", "main")
    return root


def _ecrire_souvenir(root: Path, nom: str = "feedback-essai.md") -> Path:
    chemin = root / "05-Memoire" / nom
    chemin.write_text(SOUVENIR, encoding="utf-8")
    return chemin


def _lancer(chemin: Path, root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "SHINZO_DIR": str(root)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"file_path": str(chemin)}}),
        capture_output=True, text=True, env=env, check=False,
    )


# --- le cablage -------------------------------------------------------------

def test_the_memory_hook_is_wired_to_an_event():
    """Une regle BLOQUANTE annonce ce hook. Il doit exister dans les reglages."""
    reglages = json.loads((RACINE / ".claude/settings.json").read_text(encoding="utf-8"))
    commandes = [
        h.get("command", "")
        for evenement in reglages["hooks"].values()
        for entree in evenement
        for h in entree.get("hooks", [])
    ]
    assert any("memory-autocommit" in c for c in commandes)


# --- le sommaire voyage avec le souvenir ------------------------------------

def test_writing_a_memory_regenerates_the_summaries(tmp_path):
    root = _init_repo(tmp_path)
    chemin = _ecrire_souvenir(root)
    _lancer(chemin, root)
    assert (root / "05-Memoire" / "MEMORY.md").is_file()
    assert (root / "05-Memoire" / "README.md").is_file()


def test_the_summaries_travel_in_the_same_commit(tmp_path):
    root = _init_repo(tmp_path)
    chemin = _ecrire_souvenir(root)
    _lancer(chemin, root)
    portes = _git(root, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "05-Memoire/feedback-essai.md" in portes
    assert "05-Memoire/MEMORY.md" in portes
    assert "05-Memoire/README.md" in portes


def test_the_new_memory_appears_in_the_loaded_summary(tmp_path):
    root = _init_repo(tmp_path)
    _lancer(_ecrire_souvenir(root), root)
    charge = (root / "05-Memoire" / "MEMORY.md").read_text(encoding="utf-8")
    assert "feedback-essai.md" in charge


# --- ce qui ne doit pas changer ---------------------------------------------

def test_a_file_outside_the_memory_directory_is_left_alone(tmp_path):
    root = _init_repo(tmp_path)
    dehors = root / "02-Projets" / "Kata.md"
    dehors.parent.mkdir(parents=True)
    dehors.write_text("note", encoding="utf-8")
    avant = _git(root, "rev-parse", "HEAD").stdout.strip()
    _lancer(dehors, root)
    assert _git(root, "rev-parse", "HEAD").stdout.strip() == avant


def test_another_session_staged_work_is_not_carried_away(tmp_path):
    # Defaut observe le 2026-08-10 : un commit non cible emporte le travail
    # d'une session voisine sous son propre message.
    root = _init_repo(tmp_path)
    voisin = root / "02-Projets" / "Autre.md"
    voisin.parent.mkdir(parents=True)
    voisin.write_text("travail d une autre session", encoding="utf-8")
    _git(root, "add", "--", "02-Projets/Autre.md")
    _lancer(_ecrire_souvenir(root), root)
    portes = _git(root, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert "02-Projets/Autre.md" not in portes


# --- defaut trouve par la relecture independante du 2026-09-06 --------------
# Le generateur vivait dans `scripts/`, qui n'est PAS propage. Chez un receveur
# il etait absent, et la fonction rendait une liste vide SANS RIEN DIRE. Or
# Shinzo est partage : un souvenir ecrit depuis n'importe quel depot y arrivait
# avec un index perime. La derive « 601 annonces pour 604 » revenait par 32
# portes, en silence.

def test_the_generator_lives_where_the_propagation_carries_it():
    generateur = RACINE / ".claude/hooks/lib/memory_index.py"
    assert generateur.is_file(), "le generateur doit vivre dans hooks/lib, qui voyage"


# Le raccourci vit dans `scripts/`, qui ne voyage pas : chez un receveur ce test
# rougit sur un fichier absent et bloque toute la propagation (2026-09-07).
DANS_KATA = (RACINE / "scripts" / "propagate-methodology.py").is_file()


@pytest.mark.skipif(not DANS_KATA, reason="le raccourci `scripts/` ne vit que dans Kata")
def test_the_command_line_wrapper_still_works():
    """Le raccourci `scripts/` reste utilisable DANS Kata."""
    import subprocess
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "scripts/generate-memory-index.py"), "--check"],
        capture_output=True, text=True, cwd=str(RACINE))
    assert "Sommaires" in resultat.stdout


def test_a_missing_generator_is_said_never_swallowed(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "memory_autocommit", RACINE / ".claude/hooks/memory/memory-autocommit.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_autocommit"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_regenerate_summaries",
                        lambda _root: (_ for _ in ()).throw(FileNotFoundError("absent")))
    assert module._stage_summaries(tmp_path) == []
