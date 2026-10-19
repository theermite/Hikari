"""lib/language_detect.py — spot English prose inside a reply meant to be French.

The detector counts function words. It must refuse a real English paragraph and
leave technical French (full of English terms) alone; when in doubt it says no.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from language_detect import english_paragraphs, jay_wants_english  # noqa: E402

ENGLISH = (
    "I have read the three files and the tests that you asked me to check, and "
    "there is nothing in them that would explain why the build is failing on "
    "the server, so I will look at the logs next and then report what I find."
)
FRENCH_TECH = (
    "Le hook pre-commit lance le linter sur les fichiers modifiés, puis le "
    "runner de tests vérifie que le build passe avant le push, et le garde-fou "
    "de review bloque le merge si le diff touche un module critique sans relecture."
)


def test_english_paragraph_is_detected():
    assert english_paragraphs(ENGLISH) == [ENGLISH]


def test_french_with_english_technical_terms_is_left_alone():
    assert english_paragraphs(FRENCH_TECH) == []


def test_one_english_paragraph_inside_a_french_reply_is_found():
    reply = f"Voici le résultat de la mesure.\n\n{ENGLISH}\n\nOn continue demain."
    assert english_paragraphs(reply) == [ENGLISH]


def test_english_inside_a_code_block_does_not_count():
    assert english_paragraphs(f"Voici l'exemple :\n\n```\n{ENGLISH}\n```\n") == []


def test_english_inside_inline_code_or_a_table_does_not_count():
    assert english_paragraphs(f"`{ENGLISH}`") == []
    assert english_paragraphs(f"| clé | valeur |\n|---|---|\n| texte | {ENGLISH} |") == []


def test_under_25_words_is_too_short_to_decide():
    assert english_paragraphs("I have read the files and there is nothing to report here.") == []


def test_paths_and_urls_are_not_prose():
    text = "Voir C:/Users/x/the/path/to/the/file.py et https://example.com/the/page/that/is/here " * 3
    assert english_paragraphs(text) == []


def test_jay_asking_for_english_is_recognised():
    assert jay_wants_english("Réponds-moi en anglais s'il te plaît")
    assert jay_wants_english("please answer in English")
    assert jay_wants_english("Responde en inglés")


def test_jay_writing_in_english_is_recognised():
    assert jay_wants_english("can you check the build and tell me why the tests are failing now")


def test_jay_writing_french_is_not_english():
    assert not jay_wants_english("peux-tu vérifier le build et me dire pourquoi les tests échouent")


# --- relecture independante 2026-10-18 ---------------------------------------


def test_quoted_english_is_not_the_reply_language():
    assert english_paragraphs(f"La doc dit :\n\n> {ENGLISH}\n") == []
    assert english_paragraphs(f"La doc dit « {ENGLISH} » et on suit.") == []
    assert english_paragraphs(f'La doc dit "{ENGLISH}" et on suit.') == []


def test_more_ways_to_ask_for_english():
    for t in ("fais la version anglaise du post", "rédige-le en EN et ES", "traduis en anglais"):
        assert jay_wants_english(t), t
