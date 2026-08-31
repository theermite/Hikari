#!/usr/bin/env python3
"""Lego Library hook: refuse a hand-drawn comfort-settings panel.

Trigger: PreToolUse Write|Edit on a file that DRAWS a UI
(.html/.htm/.tsx/.jsx/.vue/.svelte/.kt/.astro).

Why this exists (audit 2026-08-30, 4 repos affected). The sibling guard
`shinkofa-ui-inventory.py` detects a duplicate by its NAME. A hand-rolled
morphic panel is never named like the real component -- that is exactly why it
got rebuilt. It also reads .tsx/.jsx only, so every HTML mockup escaped it.
Measured cost: a decorative "Contraste" button in a Boken mockup was reported
as a module bug and debugged against the wrong artefact.

So the detection here is on the axis VOCABULARY, which is stable, distinctive,
and survives translation into any markup:
  3+ distinct axes and no module reference -> BLOCK
  2 distinct axes and no module reference  -> WARN
  any module reference present             -> PASS

Two axes only warns, on purpose: a blocking check founded on a guess costs more
than it earns (Jay's decision 2026-08-19, the empty-test check).

Reference: rules/Quality.md > Lego Library > Morphic module.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    format_block,
    format_warn,
    get_content,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)

REAL_PACKAGE = "@theermite/morphic-adapter"

# A file that draws markup. .md is deliberately absent: a CDC or a rule names
# the axes to describe them, and policing prose would fire on every methodology
# doc until someone turned the gate off.
UI_SUFFIXES: tuple[str, ...] = (
    ".html", ".htm", ".tsx", ".jsx", ".vue", ".svelte", ".kt", ".astro",
)

# Paths the gate does not own.
SKIP_SEGMENTS: tuple[str, ...] = (
    "morphic-engine/",          # the module itself cannot import itself
    "node_modules/",
    "/dist/",
    "/build/",
    "/.next/",
    "/out/",
    "/coverage/",
    ".claude/hooks/",           # this gate and its own tests
)

# What counts as "the real module is in play".
#
# A NAME is not a proof of use. Found on a real artefact 2026-08-30: a
# hand-rolled drawer carrying the comment "reproduction fidele de
# @morphic/adapter MorphicButton" walked straight through an earlier version of
# this gate. A decoy names the real module precisely to look real, so accepting
# a mention hands the gate to the thing it hunts.
#
# Two proofs are accepted, both of which a comment cannot fake:
#   1. the EXACT package specifier -- `@morphic/adapter` is a lookalike, not ours
#   2. an element actually rendered -- `<MorphicButton`, never the bare word
_MODULE_REFS = re.compile(
    r"@theermite/morphic-"              # npm packages (engine, adapter, wasm-core)
    r"|com\.theermite\.morphic"         # Android/Kotlin port, import path
    r"|<\s*Morphic(?:Provider|Button|OnboardingScreen)\b"   # JSX/Compose element
    r"|\bMorphicProvider\s*\(",         # Compose / plain call site
    re.IGNORECASE,
)

# One entry per adaptation axis. Repetitions of the same axis count once --
# a page listing five theme options is one axis, not a full panel.
#
# ANCHOR axes use vocabulary only a comfort panel uses. GENERIC ones (theme,
# motion, density, font size) are ordinary UI words: a shop page with a dark-mode
# toggle, a "hover animations" checkbox and a "compact view" checkbox carries
# three of them and has nothing to do with the module. That page was BLOCKED by
# the first version (independent review 2026-08-30) -- family: a signal built
# from generic words, read as specific. A guard that stops legitimate work gets
# switched off, and it would take the real detection down with it.
#
# So a decoy needs at least ONE anchor. All six real decoys of the 2026-08-30
# audit carry one; the product page carries none.
_ANCHOR_AXES: dict[str, re.Pattern[str]] = {
    "panel": re.compile(r"adaptation morphique|confort\s*&(?:amp;)?\s*adaptation|morphicpop"),
    "colorblind": re.compile(r"\bdaltonis|\bcolou?r[- ]?blind"),
    "reading": re.compile(r"guide de (?:lecture|ligne)|focus de lecture|reading guide"),
    "wai": re.compile(r"symboles? wai\b"),
    "dys_font": re.compile(r"opendyslexic|atkinson"),
    "contrast": re.compile(r"contraste eleve|high[- ]contrast"),
}

_GENERIC_AXES: dict[str, re.Pattern[str]] = {
    "theme": re.compile(r"\bthemes?\b"),
    "motion": re.compile(r"\banimations?\b|\bmouvement\b|reduced[- ]motion"),
    "density": re.compile(r"\bdensite\b|\bdensity\b|\bspacieux\b|\bcompacte?\b"),
    "font": re.compile(r"taille (?:du )?(?:texte|police)|font[- ]size"),
}

_AXES: dict[str, re.Pattern[str]] = {**_ANCHOR_AXES, **_GENERIC_AXES}


def _fold(text: str) -> str:
    """Lowercase and strip accents.

    An accent must never be the difference between caught and missed: the same
    mockup is written `Densite` by one pass and `Densite` (accented) by the next.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _is_skipped(norm_path: str) -> bool:
    lowered = norm_path.lower()
    if any(seg in lowered for seg in SKIP_SEGMENTS):
        return True
    return not lowered.endswith(UI_SUFFIXES)


def _matched_axes(folded: str) -> set[str]:
    return {name for name, pat in _AXES.items() if pat.search(folded)}


_RECOVERY = (
    f"draw this panel with `MorphicButton` from '{REAL_PACKAGE}/ui'. "
    "A static mockup with no build step loads the published package from a "
    f"CDN (script type=module, src=https://esm.sh/{REAL_PACKAGE}) "
    f"or links its stylesheet ({REAL_PACKAGE}/ui.css). "
    "Android uses `com.theermite.morphic`."
)
_REFERENCE = "rules/Quality.md > Lego Library > Morphic module"


def _report(name: str, axes: set[str]) -> None:
    """Block on a full panel, warn on a partial signal. Never returns silently."""
    listed = ", ".join(sorted(axes))
    if len(axes) >= 3:
        block(format_block(
            reason=f"{name} draws {len(axes)} adaptation axes ({listed}) with "
                   "no reference to the morphic module -- this is a decoy "
                   "panel, not the real thing",
            recovery=_RECOVERY,
            reference=_REFERENCE,
        ))
    warn(format_warn(
        reason=f"{name} mentions 2 adaptation axes ({listed}) with no "
               "reference to the morphic module",
        action=_RECOVERY,
        reference=_REFERENCE,
    ))


def main() -> None:
    _, data = read_hook_input()

    path = get_file_path(data)
    if not path:
        pass_through()

    norm = path.replace("\\", "/")
    if _is_skipped(norm):
        pass_through()

    content = get_content(data)
    if not content or _MODULE_REFS.search(content):
        pass_through()

    axes = _matched_axes(_fold(content))
    # Generic UI words alone never accuse: without an anchor this is an ordinary
    # screen, not a comfort panel (independent review 2026-08-30).
    if len(axes) < 2 or not (axes & set(_ANCHOR_AXES)):
        pass_through()

    _report(Path(norm).name, axes)
    sys.exit(0)


if __name__ == "__main__":
    main()
