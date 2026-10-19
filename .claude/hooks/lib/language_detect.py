"""Spot English prose inside a reply meant to be French. Stdlib only.

Function-word counting, not a language model: it must refuse a real English
paragraph and leave technical French (full of English terms) alone. When in
doubt it says no — a gate that cries wolf gets unplugged (Workflows.md, context
gauge). Code, inline code, tables, paths and URLs are not prose and are removed
first, so an English literal (marker, template, quoted error) never counts.
"""

from __future__ import annotations

import re

MIN_WORDS = 25  # under this, too short to decide
MIN_WORDS_JAY = 6  # Jay's own messages are short; same ratio test

_EN = frozenset(
    "the and is are was were this that with for not you your have has will would can could "
    "should of to in it on as be by from or an at we i if then but what when which there "
    "their they them our also just so do does did been being been into than these those "
    "its my me he she his her about because after before while where how why".split()
)
_FR = frozenset(
    "le la les des du de un une et est sont était pour pas vous votre avec sur dans que qui "
    "ce cette ces en au aux ou mais donc je tu il elle nous ils on par plus ne se si son sa "
    "ses leur y a été sans comme très aussi tout tous mon ma mes ton ta tes ici là car "
    "puis alors quand où comment pourquoi ont avoir être fait faire peut peux veux".split()
)

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+")
_PATH = re.compile(r"[\w.~:-]*[/\\][\w./\\~:-]*")
_QUOTE_LINE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
_QUOTED = re.compile(r'«[^»]*»|"[^"\n]{20,}"|“[^”]*”')
_WORD = re.compile(r"[a-zà-ÿ']+")
_ASKS_ENGLISH = re.compile(
    r"\b(?:en\s+anglais|in\s+english|en\s+ingl[eé]s|version\s+anglaise)\b"
    r"|\ben\s+EN\b|\bEN\s*(?:/|,|et|and)\s*(?:ES|FR)\b",
    re.IGNORECASE,
)


def _is_english(paragraph: str, min_words: int) -> bool:
    words = _WORD.findall(paragraph.lower())
    if len(words) < min_words:
        return False
    en = sum(w in _EN for w in words)
    fr = sum(w in _FR for w in words)
    return en >= 8 and en >= 2 * fr if min_words >= MIN_WORDS else en >= 3 and en >= 2 * fr


def prose_paragraphs(text: str) -> list[str]:
    """Prose paragraphs only: no fenced or inline code, no URL or path, no table."""
    text = _FENCE.sub("", text or "")
    text = _QUOTE_LINE.sub("", text)
    text = _QUOTED.sub("", text)
    text = _INLINE.sub("", text)
    text = _URL.sub("", text)
    text = _PATH.sub("", text)
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.splitlines() if not ln.lstrip().startswith("|")]
        paragraph = " ".join(" ".join(lines).split())
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs


def english_paragraphs(text: str) -> list[str]:
    """The prose paragraphs of `text` that are English (>= 25 words, clear majority)."""
    return [p for p in prose_paragraphs(text) if _is_english(p, MIN_WORDS)]


def jay_wants_english(text: str) -> bool:
    """Jay asked for English, or wrote his message in English."""
    if _ASKS_ENGLISH.search(text or ""):
        return True
    return any(_is_english(p, MIN_WORDS_JAY) for p in prose_paragraphs(text))
