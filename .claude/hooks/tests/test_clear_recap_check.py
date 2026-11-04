"""quality/clear-recap-check.py — Stop hook : ce que Takumi dit à Jay se comprend sans avoir vu le code.

Reproche de Jay (2026-11-01) : les récapitulatifs étaient trop techniques. Décision de Jay (2026-11-04) : le gabarit
imposé (L'essentiel / Pour toi / Gains et limites / Ta question) alourdissait les réponses et faisait réécrire
chaque message refusé. La FORME est libre ; le garde ne refuse plus que le jargon accumulé et les numéros de commit.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "clear-recap-check.py"
_spec = importlib.util.spec_from_file_location("clear_recap_check", HOOK)
crc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crc)

PAD = ("Voici le point du travail de la journée, avec toutes les vérifications faites étape par étape sur la partie "
       "concernée du projet. ") * 2
JARGON = "J'ai relancé le receveur avec le marqueur et la dispense, puis comparé l'empreinte. "


def _problems(text: str) -> list[str]:
    return [p for p, _ in crc.problems(text)]


# --- la forme est libre -----------------------------------------------------------------------------------------


def test_a_question_without_any_titles_is_left_alone():
    assert _problems(PAD + "J'ai mis à jour le garde et tout est vert. Veux-tu que je continue avec la suite ?") == []


def test_a_long_report_without_titles_is_left_alone():
    text = "Voici où on en est. " + "Le travail avance sur plusieurs points, avec des vérifications à chaque étape. " * 20
    assert _problems(text) == []


def test_lists_tables_and_emojis_are_free():
    text = (PAD + "\n- ✅ la page de connexion accepte tous les comptes\n- ⚠️ la vitesse n'a pas changé\n\n"
            "| point | état |\n|---|---|\n| connexion | réglé |\n")
    assert _problems(text) == []


def test_the_old_template_is_gone():
    assert not hasattr(crc, "TEMPLATE") and not hasattr(sys.modules[crc.problems.__module__], "TEMPLATE")


# --- le vocabulaire que Jay n'a pas -------------------------------------------------------------------------------


def test_internal_vocabulary_is_flagged_from_three_distinct_terms():
    found = dict(crc.problems(PAD + JARGON))
    assert "vocabulaire" in found and "receveur" in found["vocabulaire"].lower()


def test_two_internal_terms_are_tolerated_and_code_is_ignored():
    text = (PAD + "J'ai relancé le receveur avec le marqueur, tout va bien pour la suite du travail.\n"
            "```\nhook dispense empreinte mutation worktree\n```\n`yaml json regex`")
    assert _problems(text) == []


def test_a_commit_number_in_the_chat_is_refused_alone():
    assert "vocabulaire" in _problems(PAD + "Le correctif est dans le commit 9a2885a1, tout le reste est en ordre et vérifié.")


def test_a_long_number_is_not_a_commit_number():
    assert _problems(PAD + "Le suivi a consommé 1500000 jetons ce mois-ci, ce qui reste normal pour ce type de travail.") == []


def test_the_message_gives_a_plain_word_for_each_term_found():
    suggestion = dict(crc.problems(PAD + JARGON))["vocabulaire"]
    assert "projet qui reçoit" in suggestion and "numéro de version" in suggestion


def test_a_short_message_is_left_alone_even_with_jargon():
    assert _problems("Le hook, le receveur, le marqueur, la dispense.") == []


# --- le message de refus : début conservé, aucun gabarit ----------------------------------------------------------


def test_the_refusal_keeps_its_opening_and_imposes_no_template():
    msg = crc.message(crc.problems(PAD + JARGON))
    assert msg.startswith("Jay n'a pas le contexte de ce que tu viens de faire : il n'a pas vu les commandes")
    assert "L'essentiel" not in msg and "Pour toi" not in msg and "##" not in msg


# --- le garde tel que l'application le lance -----------------------------------------------------------------------


def _run(payload: dict):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20)


def test_the_hook_blocks_jargon_once_then_lets_the_second_stop_through():
    reply = PAD + JARGON
    first = _run({"hook_event_name": "Stop", "last_assistant_message": reply})
    assert first.returncode == 2 and b"Jay n'a pas le contexte" in first.stderr
    assert _run({"hook_event_name": "Stop", "stop_hook_active": True, "last_assistant_message": reply}).returncode == 0


def test_the_hook_lets_a_free_form_question_through():
    reply = PAD + "Veux-tu que je continue avec la suite du travail prévu ?"
    assert _run({"hook_event_name": "Stop", "last_assistant_message": reply}).returncode == 0


def test_the_hook_fails_open_on_garbage():
    assert _run({"hook_event_name": "Stop", "last_assistant_message": 12}).returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True).returncode == 0


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/clear-recap-check.py" in settings
