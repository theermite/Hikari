# KATA-ONLY
"""scripts/souvenirs-contreparties.py — chaque famille de souvenirs de retour nomme ses gardes, et ils existent."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
SCRIPT = RACINE / "scripts" / "souvenirs-contreparties.py"
_spec = importlib.util.spec_from_file_location("souvenirs_contreparties", SCRIPT)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def test_every_guard_cited_exists():
    assert sc.gardes_manquants() == []


def test_a_cited_guard_that_vanishes_is_caught(monkeypatch):
    monkeypatch.setattr(sc, "FAMILLES", [("x", ("a",), ("guards/n-existe-pas.py",))])
    assert sc.gardes_manquants() == ["guards/n-existe-pas.py"]


def test_classification_reads_the_name_by_token_start():
    assert sc.famille_de("feedback-deploy-prudence-never-break-prod.md") == "mise en ligne et serveur"
    assert sc.famille_de("feedback-tutoyer-jay-toujours.md") == "langue, forme et réponse"
    assert sc.famille_de("zzz-rien.md") == "autre"
    assert sc.famille_de("feedback-quuix.md") == "autre"  # « ui » exact : pas dans « quuix »


def test_only_feedback_memories_are_counted(tmp_path):
    (tmp_path / "a-deploy.md").write_text("---\nname: a\ntype: feedback\n---\nx", encoding="utf-8")
    (tmp_path / "b-deploy.md").write_text("---\nname: b\ntype: reference\n---\nx", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("type: feedback", encoding="utf-8")
    assert sum(sc.compter(tmp_path).values()) == 1


def test_the_output_is_deterministic_and_names_the_uncovered(tmp_path):
    (tmp_path / "x-zzz.md").write_text("---\ntype: feedback\n---\n", encoding="utf-8")
    sortie = [subprocess.run([sys.executable, str(SCRIPT), "--dossier", str(tmp_path)], capture_output=True, text=True,
                             encoding="utf-8").stdout for _ in range(2)]
    assert sortie[0] == sortie[1] and "sans contrepartie" in sortie[0] and "Total : 1" in sortie[0]


def test_every_manual_classification_names_a_real_family():
    titres = {t for t, _, _ in sc.FAMILLES}
    assert set(sc.CLASSEMENT_MANUEL.values()) <= titres


def test_a_manual_classification_beats_the_name():
    assert sc.famille_de("feedback-rare-n-est-pas-impossible.md") == "pièces existantes et recherche"
    assert sc.famille_de("valeur-fondamentale-libre-arbitre.md") == sc.PRODUIT


def test_the_real_memories_leave_nothing_unclassified():
    if not sc.SOUVENIRS.exists():
        return  # dossier absent de cette machine : rien à mesurer
    assert sc.compter(sc.SOUVENIRS).get("autre", 0) == 0, "un souvenir de retour neuf n'est dans aucune famille : le classer"


def test_a_short_word_does_not_capture_a_longer_one():
    """Relecture du 2026-11-24 : « prod » prenait « produit », « port » prenait « porte », « dire » prenait « direct »."""
    assert sc.famille_de("feedback-le-produit-s-adapte.md") != "mise en ligne et serveur"
    assert sc.famille_de("feedback-qui-porte-l-historique.md") != "mise en ligne et serveur"
    assert sc.famille_de("feedback-direct-vers-main.md") != "langue, forme et réponse"
