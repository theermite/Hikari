"""The two agreements that lift the reformulate gate (Jay, 2026-10-18).

1. A design document (PET, CDC, brief) shown, then an exact approval word.
2. Jay's own instruction naming a brick of the project's PET.

Only the reformulate gate relaxes: veille, tests, lint and secrets fire on every
write regardless. Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path

from transcript_reader import (
    entry_message,
    is_copy_entry,
    errored_tool_ids,
    iter_entries,
    norm_path as _norm_path,
)
from user_turns import (
    APPROVAL_WORDS,
    _is_continuation_message,
    _is_real_user_message,
    _normalize,
    _user_text,
)


# A design document is one Jay can validate: the PET, the CDC, or a brief.
# Anchored on the path (docs/ folder), never on the bare word: a comment that
# quotes "docs/PET.md" inside file content is not a document shown to Jay.
_DESIGN_DOC_PATH = re.compile(r"(?:^|/)docs/(?:(?:pet|cdc)\.md|briefs/[^/]+\.md)$")


def _shows_design_doc(msg: dict, errored: set) -> bool:
    """True if Takumi opened/wrote a design document: a tool call that did not
    fail. Never a mention in his text ("je ne touche pas docs/PET.md" shows
    nothing to Jay — independent review 2026-10-18)."""
    content = msg.get("content")
    if isinstance(content, list):
        for blk in content:
            if (
                isinstance(blk, dict)
                and blk.get("type") == "tool_use"
                and blk.get("name") in ("Read", "Write", "Edit")
                and blk.get("id") not in errored
            ):
                inp = blk.get("input")
                fp = inp.get("file_path") if isinstance(inp, dict) else None
                if isinstance(fp, str) and _DESIGN_DOC_PATH.search(_norm_path(fp)):
                    return True
    return False


def has_design_approval(transcript_path: str) -> bool:
    """True while Jay's approval of a shown design document (PET, CDC, brief)
    is the latest word: exact approval word after the document, and no newer
    real instruction since.

    Jay 2026-10-18: a design he validated IS the authorization, like an approved
    plan. Order matters: document first, approval after. A new instruction
    cancels a pending document; a relance nudge ("reprends") keeps it pending
    but never approves. Only this gate relaxes — veille, tests, lint, secrets
    fire on every write regardless.
    """
    if not transcript_path:
        return False
    msgs = [m for m in (entry_message(e) for e in iter_entries(transcript_path, reverse=False)
                        if not is_copy_entry(e)) if m]
    errored: set = set()
    for msg in msgs:
        errored |= errored_tool_ids(msg)
    pending = approved = False
    for msg in msgs:
        role = msg.get("role")
        if role == "assistant":
            if _shows_design_doc(msg, errored):
                pending = True
        elif role == "user" and _is_real_user_message(msg):
            if pending and _normalize(_user_text(msg)) in APPROVAL_WORDS:
                approved = True
            elif not _is_continuation_message(msg):
                # A new instruction ends the agreement: it covers what Jay's
                # approval answered, not everything said afterwards.
                pending = approved = False
    return approved


# Bricks as Jay writes them ("brique 8", "B8", "B0.1a") and as PETs list them
# (Shizen "B-PREP", Kakusei "B0.1a"). Same extraction on both sides, normalized
# to lower case without the leading "b"/"brique": "8", "0.1a", "prep".
_BRICK_NUM = r"(\d{1,3}(?:\.\d+)?[a-z]?)\b"  # "8", "0a", "0.1a" — not a task id like "b3wf2e265"
_BRICK_WORD = re.compile(r"\b(?:brique|brick)s?\s+" + _BRICK_NUM, re.IGNORECASE)
_BRICK_B_NUM = re.compile(r"\bb-?" + _BRICK_NUM, re.IGNORECASE)
_BRICK_B_NAME = re.compile(r"\bB-([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)", re.IGNORECASE)
_PET_MAX_BYTES = 2_000_000


def brick_ids(text: str) -> set:
    ids = set()
    for rx in (_BRICK_WORD, _BRICK_B_NUM, _BRICK_B_NAME):
        for m in rx.finditer(text or ""):
            ident = m.group(1).lower().rstrip(".-")
            if ident:
                ids.add(ident)
    return ids


def pet_brick_ids(file_path: str) -> set:
    """Brick ids of the nearest docs/PET.md above the file being written."""
    if not file_path:
        return set()
    here = Path(file_path).parent
    for d in [here, *list(here.parents)[:8]]:
        pet = d / "docs" / "PET.md"
        try:
            if pet.is_file() and pet.stat().st_size <= _PET_MAX_BYTES:
                return brick_ids(pet.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return set()
    return set()


def last_instruction_text(transcript_path: str) -> str:
    """Jay's latest real instruction: relance nudges ("go") never replace it.

    A message the harness injected (task notification, reminder, command echo)
    opens with "<" and is not Jay's voice: it authorizes nothing, so it yields ""
    (measured on real journals: a task id "b3wf2e265" read as a brick)."""
    for entry in iter_entries(transcript_path):
        if is_copy_entry(entry):
            continue  # the journal re-records each message; the copy is not Jay's voice
        msg = entry_message(entry)
        if msg and _is_real_user_message(msg) and not _is_continuation_message(msg):
            text = _user_text(msg)
            return "" if text.lstrip().startswith("<") else text
    return ""


def names_a_pet_brick(transcript_path: str, file_path: str) -> bool:
    """Jay 2026-10-18: an instruction that names a brick of this project's PET is
    the agreement. A question is not an instruction. Never for a sub-agent: its
    "instruction" is written by Takumi, and nobody but Jay authorizes."""
    if not transcript_path:
        return False
    text = last_instruction_text(transcript_path).strip()
    if not text or text.endswith("?"):
        return False
    named = brick_ids(text)
    return bool(named and named & pet_brick_ids(file_path))
