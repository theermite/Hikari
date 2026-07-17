#!/usr/bin/env python3
"""Clock-is-not-fatigue check — Stop hook (WARN + next-turn injection).

Enforces Identity.md "The Clock Is Not a Fatigue Signal (BLOCKING)" on
Takumi's most recent assistant response.

The rule: the injected [TIME] serves ONLY greetings (bonsoir / bonjour).
It must NEVER be used to refuse, defer, or shorten work, reduce scope or
quality, suggest stopping, or infer "Jay must be tired". Jay's energy is
read ONLY from his explicit in-conversation signals — never from the clock.

Detection = a clock / hour REFERENCE and a brake / fatigue INFERENCE within
the same sentence or an adjacent one. A clock reference ALONE (greeting,
factual "il est tard mais on finit") never flags — the brake is required.
This keeps false positives low: the violation is the *link* clock -> brake,
not the mention of the hour.

Code blocks (``` and `inline`) are stripped before analysis (examples in
code must not trigger).

Output: WARNING on stderr (Jay sees it) + persists to state file
        clock-fatigue-violations-<session>.json with pending:true, so the
        UserPromptSubmit companion (clock-not-fatigue-inject.py) re-injects
        the violation into Takumi's NEXT context — Option A equivalent-of-
        BLOCKING for a Stop hook (a Stop hook cannot rewrite an already
        emitted response). Exit 0 always.

Status: Functional BLOCKING via Option A (next-turn injection). Mirrors
        quality/simple-language-check.py.

Source: rules/Identity.md "The Clock Is Not a Fatigue Signal" ;
        Kata-Notes-Jay note 4 (2026-07-05) ; audit vs Michi no Kata Go Rin
        (2026-07-07) — rule was BLOCKING in text but had zero hook.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import pass_through, read_hook_input  # noqa: E402
from session_state import write_state  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402


# Match fenced code blocks (```...```) and inline code (`...`)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")

# Ordered-unit splitter: sentence punctuation OR newline.
_UNIT_SPLIT_RE = re.compile(r"[.!?\n]+")

# Set A — clock / hour REFERENCE. Curated tight: unambiguous late-hour or
# explicit-clock phrases. Bare "tard" is excluded on purpose ("plus tard" /
# "trop tard" = "later" / "missed", not the clock). "bonsoir" contains no
# Set A phrase, so greetings pass unless a brake is also present.
_CLOCK_TERMS = (
    "il est tard", "il se fait tard", "il est déjà tard", "il est bien tard",
    "heure tardive", "à cette heure", "à pareille heure", "à une heure pareille",
    "vu l'heure", "au vu de l'heure", "si tard", "en pleine nuit",
    "minuit passé", "passé minuit", "minuit", "heure du matin",
    # English
    "it's late", "it is late", "the late hour", "late at night",
    "given the hour", "at this hour", "so late", "this late",
)

# Set B — brake / fatigue INFERENCE. Fuller phrases only, to avoid catching
# technical uses ("le test au repos", "async" etc.). Bare "repos" / "reposer"
# / "fatigue" excluded on purpose.
_BRAKE_TERMS = (
    "te reposer", "repose-toi", "va te reposer", "prends du repos",
    "un peu de repos", "tu devrais dormir", "va dormir", "il faut dormir",
    "tu dois être fatigué", "tu es fatigué", "tu dois être épuisé",
    "sûrement fatigué", "peut-être fatigué", "tu es épuisé",
    "on continue demain", "on reprend demain", "reprendre demain",
    "on remet à demain", "on remet ça à demain", "à demain", "on verra demain",
    "on s'arrête là", "on arrête là", "on s'arrête pour ce soir",
    "on s'arrête pour aujourd'hui", "il vaut mieux s'arrêter",
    "mieux vaut s'arrêter", "garde ton énergie", "ménage-toi",
    "ne te surmène pas",
    # English
    "get some rest", "get rest", "rest up", "you should sleep",
    "go to sleep", "you must be tired", "you're probably tired",
    "continue tomorrow", "pick this up tomorrow", "call it a night",
    "wrap up for tonight",
)


def _strip_code(text: str) -> str:
    """Remove fenced and inline code blocks."""
    text = _CODE_BLOCK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def _units(text: str) -> list[str]:
    """Split into ordered units (sentences / lines), lowercased, non-empty."""
    return [u.strip().lower() for u in _UNIT_SPLIT_RE.split(text) if u.strip()]


def _terms_in(unit: str, terms: tuple[str, ...]) -> list[str]:
    """Return the terms from `terms` present as substrings in `unit`."""
    return [t for t in terms if t in unit]


def _analyze(text: str) -> list[str]:
    """Return violations: a clock ref linked to a brake within +/-1 unit."""
    units = _units(_strip_code(text))
    violations: list[str] = []
    seen: set[tuple[str, str]] = set()

    for i, unit in enumerate(units):
        clocks = _terms_in(unit, _CLOCK_TERMS)
        if not clocks:
            continue
        # Look in this unit and its immediate neighbours for a brake.
        window = units[max(0, i - 1): i + 2]
        brakes = sorted({b for u in window for b in _terms_in(u, _BRAKE_TERMS)})
        if not brakes:
            continue
        key = (clocks[0], brakes[0])
        if key in seen:
            continue
        seen.add(key)
        violations.append(
            f"Horloge liée à un frein (Identity « The Clock Is Not a Fatigue "
            f"Signal », BLOCKING): « {clocks[0]} » + « {brakes[0]} ». L'heure "
            f"ne sert qu'aux salutations — jamais à refuser, différer, réduire "
            f"le travail ni inférer une fatigue de Jay."
        )

    return violations


def _emit_warning(violations: list[str]) -> None:
    """WARN on stderr (Jay's console) — the response is already emitted."""
    sys.stderr.write(
        "[CLOCK-NOT-FATIGUE WARN] Identity.md violee dans la derniere "
        "reponse Takumi:\n"
    )
    for v in violations[:8]:
        sys.stderr.write(f"  - {v}\n")
    sys.stderr.write(
        "Reformuler au prochain tour: l'heure sert aux salutations, jamais "
        "a freiner. L'etat de Jay se lit dans ses signaux explicites seuls.\n"
    )
    sys.stderr.flush()


def _persist(violations: list[str], session_id: str) -> None:
    """Persist for next-turn injection (Option A). Best-effort, never break."""
    try:
        write_state(
            "clock-fatigue-violations",
            {"pending": True, "violations": violations[:20]},
            session_id=session_id or None,
        )
    except Exception:
        pass


def _latest_response(transcript_path: str) -> str | None:
    """Return Takumi's most recent assistant text, or None if unavailable."""
    try:
        chunks = list(iter_assistant_text(transcript_path, limit=1))
    except Exception:
        return None
    return chunks[0] if chunks else None


def main() -> None:
    _, data = read_hook_input()
    transcript_path = data.get("transcript_path") or ""
    session_id = data.get("session_id") or ""
    if not transcript_path:
        pass_through()

    text = _latest_response(transcript_path)
    if text is None:
        pass_through()

    violations = _analyze(text)
    if violations:
        _emit_warning(violations)
        _persist(violations, session_id)

    pass_through()


if __name__ == "__main__":
    main()
