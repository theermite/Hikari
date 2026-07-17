"""Tests for quality/clock-not-fatigue-check.py — _analyze() violations.

Rule enforced: Identity.md "The Clock Is Not a Fatigue Signal (BLOCKING)".
The injected time serves ONLY greetings — never to refuse, defer, shorten
work, reduce scope/quality, suggest stopping, or infer "Jay must be tired".

Detection = a clock/hour reference AND a brake/fatigue inference within the
same sentence or an adjacent one. A clock reference ALONE (greeting, factual
statement) must never flag.

The hook is loaded by file path (hyphen in name -> not importable as module).
Only the pure _analyze() and its helpers are exercised; no transcript needed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parents[1]
    / "quality"
    / "clock-not-fatigue-check.py"
)
_spec = importlib.util.spec_from_file_location("clock_not_fatigue_check", HOOK)
cnf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cnf)


def _joined(text: str) -> str:
    return " || ".join(cnf._analyze(text))


# --- Violations: clock linked to a brake (same sentence) --------------------


def test_clock_plus_rest_same_sentence_is_flagged():
    text = "Il est tard, tu devrais te reposer."
    assert cnf._analyze(text) != []


def test_hour_plus_defer_tomorrow_is_flagged():
    text = "Vu l'heure, on peut reprendre demain."
    assert cnf._analyze(text) != []


def test_explicit_late_hour_plus_stop_is_flagged():
    text = "Il est déjà minuit passé. On s'arrête là pour ce soir."
    assert cnf._analyze(text) != []


def test_english_clock_plus_rest_is_flagged():
    text = "It's late — you should get some rest."
    assert cnf._analyze(text) != []


def test_infer_tired_from_hour_is_flagged():
    text = "À cette heure-ci, tu dois être fatigué."
    assert cnf._analyze(text) != []


# --- Clean: clock reference ALONE (no brake) --------------------------------


def test_clock_alone_without_brake_passes():
    text = "Il est tard mais on a le temps de finir le rouge 1."
    assert cnf._analyze(text) == []


def test_greeting_bonsoir_passes():
    text = "Bonsoir Jay. On attaque le hook horloge tout de suite."
    assert cnf._analyze(text) == []


def test_plus_tard_is_not_a_clock_reference():
    text = "On verra cette option plus tard, une fois le hook livré."
    assert cnf._analyze(text) == []


# --- Clean: brake ALONE (no clock reference) --------------------------------


def test_brake_alone_without_clock_passes():
    text = "On continue demain matin comme prévu dans le plan."
    assert cnf._analyze(text) == []


def test_rest_word_in_technical_context_passes():
    text = "Le test au repos vérifie l'état stable de la fonction."
    assert cnf._analyze(text) == []


# --- Code exemption ---------------------------------------------------------


def test_clock_and_brake_inside_code_block_is_allowed():
    text = (
        "Voici l'exemple de message:\n\n"
        "```\nIl est tard, repose-toi.\n```\n\n"
        "Le hook ignore ce bloc de code."
    )
    assert cnf._analyze(text) == []
