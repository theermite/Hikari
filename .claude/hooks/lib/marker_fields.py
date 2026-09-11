"""One reader for a dashed marker field label (`- <label>: <value>`).

Independent review 2026-09-11: two hooks read the SAME field ("garde a
l'envers") with two different regexes -- one tolerant of apostrophe style, one
exact. An honest, correctly-filled [CAUSE] block got refused on a typographic
apostrophe, with no way out except retyping the exact byte the hook wanted --
a loop with no visible cause. Same review: Conventions.md makes French accents
mandatory, and an exact-ASCII reader refused the grammatically correct French
spelling of its own field name.

One reader, accent- and apostrophe-insensitive, used by every hook that checks
a dashed field. Stdlib only.
"""

from __future__ import annotations

import re
import unicodedata


def _fold(text: str) -> str:
    """Casefold + strip accents + normalize both apostrophe styles to a plain
    one, so a label matches regardless of how a human typed it."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").replace("‘", "'")
    return text.casefold()


def _label_pattern(label: str) -> re.Pattern[str]:
    """A label's words, joined by flexible whitespace; an apostrophe inside a
    word becomes optional (matches present, absent, or typographic)."""
    words = _fold(label).split(" ")
    parts = [re.escape(w).replace("'", "'?") for w in words]
    body = r"[^\S\n]+".join(parts)
    return re.compile(r"-[^\S\n]*" + body + r"[^\S\n]*:", re.IGNORECASE)


def field_label_present(text: str, label: str) -> bool:
    """True when a dashed `- <label>:` line exists, tolerant to accent,
    apostrophe style, and extra whitespace. Presence only -- no value check."""
    return bool(_label_pattern(label).search(_fold(text)))


def _value_match(text: str, label: str):
    pattern = re.compile(_label_pattern(label).pattern + r"[^\S\n]*(\S.*)", re.IGNORECASE)
    return pattern.search(_fold(text))


def field_filled(text: str, label: str) -> bool:
    """True when the label is present AND followed by a non-empty value on
    the SAME line (horizontal space only -- never borrows the next line)."""
    match = _value_match(text, label)
    return bool(match and match.group(1).strip())


def field_value(text: str, label: str) -> str | None:
    """The label's value (same line only), or None when absent/empty.

    One reader for the VALUE, not just its presence (independent review
    2026-09-11): a caller that needs to validate the value further (a date,
    a link, a specific word) reads it once here instead of re-parsing the
    field by hand -- the exact family this module exists to close.
    """
    match = _value_match(text, label)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None
