"""What Jay typed: real user turns, approval words, relance nudges.

Shared by quality/reformulate-gate.py and lib/reformulate_agreements.py.
Stdlib only.
"""

from __future__ import annotations

import unicodedata


def _is_real_user_message(msg: dict) -> bool:
    """True for a human-typed user turn; False for tool_result deliveries.

    Tool results are delivered as role=user messages carrying tool_result
    blocks. They must NOT be treated as a turn boundary, otherwise a blocked
    attempt (which produces an error tool_result) would cut the window short.
    """
    if not isinstance(msg, dict) or msg.get("role") != "user":
        return False
    content = msg.get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "tool_result":
                return False
        return True
    return False


# Continuation / approval nudges — a short message that resumes in-progress work
# WITHOUT carrying a new instruction ("go", "reprends", "gelé ?"). Such a message
# must NOT reset the reformulation window: the reformulation made before the
# nudge still covers the writes that follow it, until Jay gives a genuinely new
# instruction (Jay 2026-06-16, Notes-Jay "Hooks — Friction"). A false positive
# here only skips a redundant reformulation prompt; the real gates (veille,
# tests, lint) still fire on every write — same risk profile as has_approved_plan.
# Approval words, exact (mirror Interpretation-Protocol "Approval Words"). Alone,
# they also count as an agreement on a design document (has_design_approval).
APPROVAL_WORDS = frozenset({
    "ok", "okay", "oui", "go", "go go", "go ahead", "valide", "continue",
    "vas y", "vasy", "approuve", "d accord", "parfait", "nickel", "top", "super",
    "c est bon", "lance", "lance toi", "fais", "fais le", "execute", "banco",
    "feu vert", "yes", "proceed", "confirmed", "approved", "approve", "confirm",
    "validate", "lgtm", "perfect", "do it", "let s go", "lets go", "looks good",
    "green light", "ship it",
})

CONTINUATION_WORDS = APPROVAL_WORDS | frozenset({
    "",  # bare punctuation ("?", "...") normalizes to empty
    # relances / nudges (no new instruction)
    "reprends", "reprend", "suite", "la suite", "next", "encore", "et apres",
    "et ensuite", "alors", "gele", "tu es la", "t es la", "tes la", "toujours la",
    "tu dors", "bloque", "tu es gele", "tu es bloque",
})


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    """Lowercase, drop accents, strip terminal punctuation, collapse spaces."""
    t = _strip_accents(text).lower().strip().strip(".?!…,;:")
    t = t.replace("-", " ").replace("'", " ")
    return " ".join(t.split())


def _user_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(parts)
    return ""


def _is_continuation_message(msg: dict) -> bool:
    """A real user message that is purely a relance/approval nudge."""
    return _normalize(_user_text(msg)) in CONTINUATION_WORDS
