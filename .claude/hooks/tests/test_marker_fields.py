"""lib/marker_fields.py -- one reader for a dashed field label, shared by every
marker that carries one (`[ROBUSTNESS]`, `[CAUSE]`).

Independent review 2026-09-11: the same field ("garde a l'envers") was read by
two different regexes in two hooks, tolerant in one, exact in the other -- a
correct, honest block got refused on an apostrophe style, a loop with no exit.
Same review: French accents are mandatory (Conventions.md, memory
"French accents mandatory"), and the exact-ASCII reader refused the correct
French spelling ("garde a l'envers" vs "garde à l'envers").

One reader, accent- and apostrophe-insensitive, used by both hooks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from marker_fields import field_filled, field_label_present, field_value  # noqa: E402


def test_ascii_apostrophe_is_found():
    assert field_label_present("- garde a l'envers: oui\n", "garde a l'envers")


def test_typographic_apostrophe_is_found():
    assert field_label_present("- garde a l’envers: oui\n", "garde a l'envers")


def test_correct_french_accent_is_found():
    assert field_label_present("- garde à l'envers: oui\n", "garde a l'envers")


def test_no_apostrophe_at_all_is_found():
    assert field_label_present("- garde a lenvers: oui\n", "garde a l'envers")


def test_extra_whitespace_between_words_is_found():
    assert field_label_present("-  garde  a  l'envers :  oui\n", "garde a l'envers")


def test_french_accent_on_appelants_reels_is_found():
    assert field_label_present("- appelants réels: oui\n", "appelants reels")


def test_a_different_label_is_not_found():
    assert not field_label_present("- cause: oui\n", "garde a l'envers")


def test_filled_requires_a_non_empty_value_on_the_same_line():
    assert field_filled("- garde a l'envers: oui\n", "garde a l'envers")
    assert not field_filled("- garde a l'envers:\n", "garde a l'envers")


def test_filled_does_not_borrow_the_next_lines_text():
    text = "- garde a l'envers:\n- autre champ: valeur\n"
    assert not field_filled(text, "garde a l'envers")


def test_filled_works_with_the_typographic_apostrophe_too():
    assert field_filled("- garde a l’envers: oui, verifie\n", "garde a l'envers")


# --- field_value: the SAME field, read once, never re-parsed by hand --------
#
# 3e relecture independante 2026-09-11 : post-review-cause-check.py gardait
# 2 lecteurs a la main pour le champ 'veille' (_VEILLE_DATEE en plus de
# field_filled) et 1 pour 'approche changee' (_APPROACH, avec le bug \s qui
# emprunte la ligne suivante -- la meme famille que ce module a ete cree pour
# fermer). field_value() extrait la valeur une seule fois ; la validation
# specifique (date, "oui") s'applique sur cette valeur, jamais sur une 2e
# lecture du texte brut.


def test_value_returns_the_text_after_the_colon():
    assert field_value("- veille: shlex, doc du 2026-09-07\n", "veille") == "shlex, doc du 2026-09-07"


def test_value_is_none_when_the_field_is_absent():
    assert field_value("- cause: x\n", "veille") is None


def test_value_is_none_when_the_field_is_empty():
    assert field_value("- veille:\n", "veille") is None


def test_value_never_borrows_the_next_line():
    text = "- approche changee:\n- veille: 2026-09-07\n"
    assert field_value(text, "approche changee") is None
