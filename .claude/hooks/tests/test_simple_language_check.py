"""Tests for quality/simple-language-check.py — _analyze() violations.

Covers the existing length/acronym constraints (regression) plus the three
checks added 2026-06-14 (client<->expert reframe): BLUF buried conclusion,
condescendance markers, and bare lowercase dev-jargon.

The hook is loaded by file path (hyphen in name -> not importable as module).
Only the pure _analyze() and its helpers are exercised; no transcript needed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parents[1]
    / "quality"
    / "simple-language-check.py"
)
_spec = importlib.util.spec_from_file_location("simple_language_check", HOOK)
slc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slc)


def _joined(text: str) -> str:
    return " || ".join(slc._analyze(text))


# --- BLUF (constraint 1 — conclusion first, no staging) ---------------------


def test_bluf_staging_opener_is_flagged():
    text = "Après analyse approfondie du hook, voici le résultat."
    assert "BLUF" in _joined(text) or "conclusion" in _joined(text).lower()


def test_bluf_opener_flagged_through_markdown_bold():
    text = "**Après vérification**, le système marche."
    assert "BLUF" in _joined(text) or "conclusion" in _joined(text).lower()


def test_direct_conclusion_passes_bluf():
    text = "Le hook est en place. Trois contrôles ajoutés."
    out = _joined(text).lower()
    assert "bluf" not in out and "conclusion" not in out


# --- Condescendance (constraint 10 — Jay is HPI, never infantilize) ----------


def test_condescendance_marker_is_flagged():
    text = "En gros, le système range les fichiers."
    assert "condescendance" in _joined(text).lower()


def test_pour_faire_simple_is_flagged():
    text = "Pour faire simple, on câble les permissions."
    assert "condescendance" in _joined(text).lower()


def test_no_condescendance_marker_passes():
    text = "Le système range chaque fichier à sa place."
    assert "condescendance" not in _joined(text).lower()


# --- Bare lowercase jargon (constraint 6 — translate or gloss) ---------------


def test_bare_lowercase_jargon_is_flagged():
    text = "Le payload arrive au endpoint sans contrôle."
    assert "jargon" in _joined(text).lower()


def test_jargon_inside_backticks_is_allowed():
    text = "La donnée arrive au point d'entrée `endpoint` du service."
    assert "jargon" not in _joined(text).lower()


# --- File-name accumulation (Jay 2026-07-18 — pile of file names buries sense)


def test_single_file_name_passes():
    text = "Je corrige le composant `SkillLastHitTrainer.tsx` maintenant."
    assert "accumulation de noms de fichiers" not in _joined(text).lower()


def test_three_file_names_are_flagged():
    text = "Je touche `a.ts`, puis `b.py`, et enfin `c.exs` pour finir."
    assert "accumulation de noms de fichiers" in _joined(text).lower()


def test_folder_name_is_allowed():
    text = "La source vit dans le dossier 07-Methode/Regles, c'est prêt."
    assert "accumulation de noms de fichiers" not in _joined(text).lower()


def test_file_names_in_fenced_block_are_allowed():
    text = "Voici la liste :\n```\na.py\nb.py\nc.py\nd.py\n```\nC'est prêt."
    assert "accumulation de noms de fichiers" not in _joined(text).lower()


def test_slashed_french_pair_is_not_flagged():
    text = "On garde le thème clair et/ou sombre, dispo 24/7 partout."
    assert "accumulation de noms de fichiers" not in _joined(text).lower()


# --- Regression: existing length / paragraph constraints --------------------


def test_long_sentence_still_flagged():
    long_sentence = "Le hook " + "très " * 30 + "long dépasse la limite de mots."
    assert "mots" in _joined(long_sentence)


def test_more_than_three_prose_paragraphs_flagged():
    text = "\n\n".join(f"Paragraphe court numéro {i}." for i in range(1, 6))
    assert "paragraphes de prose" in _joined(text)


def test_clean_short_french_passes_clean():
    text = "Le hook est prêt. Je lance les tests."
    assert slc._analyze(text) == []
