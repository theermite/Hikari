#!/usr/bin/env python3
"""Reformulate gate — PreToolUse Write|Edit.

Enforces Workflows.md "Reformulate before coding": when a non-trivial change
(>1 file in the current turn) is in progress, Takumi MUST have output a
reformulation in the current conversation turn before the 2nd file write.

A reformulation is observable: numbered or bulleted list mentioning
"compris/understood" + "fichiers/files" or similar pattern, OR explicit
"REFORMULATION" marker.

Counts Write|Edit tool calls in the current turn (since last user message).
If count >= 2 AND no reformulation marker found in recent assistant text -> BLOCK.

Trivial changes (single file) are always allowed.

Sub-agents (fixed 2026-07-16)
-----------------------------
A hook fired from a sub-agent receives the PARENT's `transcript_path`. Measured
on a real sub-agent Write:

    field             parent    sub-agent
    ---------------   -------   ------------------------------
    agent_id          absent    present ("a57c9581dd38b0f5b")
    session_id        X         X  (identical -> cannot discriminate)
    transcript_path   its own   the PARENT's

Scanning the parent's journal from a sub-agent counted the PARENT's writes
against it, and looked for its reformulation in a journal where its text is
never written (parent journal: 621 entries, 0 with `isSidechain`). Result:
writes_so_far >= 1 AND reformulation undetectable -> EVERY sub-agent write
blocked, permanently. The 2026-07-16 Sakusen B2 autonomous run lost its budget
without producing a line — and it escalated cleanly instead of bypassing the
hook via Bash, which is exactly why a false positive here is expensive: a
disciplined agent pays the full price of a gate that is wrong.

Fix: `agent_id` present -> scan the sub-agent's OWN journal, which lives at
`<transcript-without-suffix>/subagents/agent-<agent_id>.jsonl`. Cannot read it
-> pass. A gate that fires 100% of the time protects nothing: it removes the
capability. The residual risk stays covered by the other Ring 0 gates (veille,
secrets, tests, complexity), which fire on every write — the same reasoning
already recorded for has_approved_plan.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import block, get_file_path, pass_through, read_hook_input  # type: ignore  # noqa: E402
from transcript_reader import iter_entries  # type: ignore  # noqa: E402

# Files exempt from the gate (methodology, docs, configs)
SKIP_PATH_PARTS = (
    "/.claude/state/",
    "\\.claude\\state\\",
    "/node_modules/",
    "\\node_modules\\",
    "/dist/",
    "\\dist\\",
    "/build/",
    "\\build\\",
    "/.next/",
    "\\.next\\",
)

# Reformulation patterns — observable evidence in assistant output
REFORMULATION_PATTERNS = (
    re.compile(r"\bREFORMULATION\b", re.IGNORECASE),
    # Numbered list with understanding + files keywords
    re.compile(
        r"(compris|understood|j'ai\s+lu|je\s+vais)[^\n]{0,200}(fichiers?|files?|touche|touch)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Explicit plan announcement
    re.compile(r"(plan|s[ée]quence|steps?)[^\n]{0,100}(fichiers?|files?|hooks?|commits?)", re.IGNORECASE),
)


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
CONTINUATION_WORDS = frozenset({
    "",  # bare punctuation ("?", "...") normalizes to empty
    # FR + EN approval words (mirror Interpretation-Protocol "Approval Words")
    "ok", "okay", "oui", "go", "go go", "go ahead", "valide", "continue",
    "vas y", "vasy", "approuve", "d accord", "parfait", "nickel", "top", "super",
    "c est bon", "lance", "lance toi", "fais", "fais le", "execute", "banco",
    "feu vert", "yes", "proceed", "confirmed", "approved", "approve", "confirm",
    "validate", "lgtm", "perfect", "do it", "let s go", "lets go", "looks good",
    "green light", "ship it",
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


def _window_entries(transcript_path: str):
    """Yield message dicts from latest back to (excluding) the last real,
    instruction-bearing user message. tool_result deliveries AND continuation
    nudges do NOT close the window."""
    for entry in iter_entries(transcript_path):
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
            continue
        if (
            msg.get("role") == "user"
            and _is_real_user_message(msg)
            and not _is_continuation_message(msg)
        ):
            return
        yield msg


def _collect_results(msg: dict, result_error: dict) -> None:
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "tool_result":
            tid = blk.get("tool_use_id")
            if tid is not None:
                result_error[tid] = bool(blk.get("is_error"))


def _collect_tool_ids(msg: dict, names: tuple[str, ...], out: list) -> None:
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") in names:
            tid = blk.get("id")
            if tid is not None:
                out.append(tid)


def count_writes_this_turn(transcript_path: str) -> int:
    """Count COMPLETED, non-error Write|Edit calls since the last real user turn.

    Only writes whose tool_result is present AND not an error count. This
    excludes (a) the current in-flight attempt (no result yet) and (b) blocked
    attempts (is_error result). A continuation nudge does not close the window
    (Jay 2026-06-16) — see _window_entries.
    """
    if not transcript_path:
        return 0
    write_ids: list[str] = []
    result_error: dict[str, bool] = {}
    for msg in _window_entries(transcript_path):
        if msg.get("role") == "user":
            _collect_results(msg, result_error)
        elif msg.get("role") == "assistant":
            _collect_tool_ids(msg, ("Write", "Edit"), write_ids)
    return sum(1 for tid in write_ids if result_error.get(tid) is False)


def has_reformulation_marker(transcript_path: str) -> bool:
    """Check assistant text since the last real instruction for a reformulation.

    The boundary is the last real, instruction-bearing user message; both
    tool_result deliveries and continuation nudges keep the window open, so a
    reformulation emitted before a blocked attempt or a "go" is still honored.
    """
    if not transcript_path:
        return False
    texts: list[str] = []
    for msg in _window_entries(transcript_path):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text"):
                texts.append(blk["text"])
    blob = "\n".join(texts)
    return any(p.search(blob) for p in REFORMULATION_PATTERNS)


def has_approved_plan(transcript_path: str) -> bool:
    """True if an approved plan exists anywhere in the session.

    A plan presented via Claude Code's plan mode (ExitPlanMode tool_use) is
    "approved" when its tool_result is present and not an error. Once approved,
    the plan IS the reformulation + authorization for the actions it describes
    (Interpretation-Protocol 'Approved plan'). Scope is session-wide.

    A rejected plan (is_error=True) or an in-flight plan (no result yet) does
    NOT count. Detection is lenient on the approval signal — the quality gates
    still fire on every write, so a false positive only removes a redundant
    reformulation prompt, never a gate.
    """
    if not transcript_path:
        return False
    plan_ids: list[str] = []
    result_error: dict[str, bool] = {}
    for entry in iter_entries(transcript_path):
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            _collect_results(msg, result_error)
        elif msg.get("role") == "assistant":
            _collect_tool_ids(msg, ("ExitPlanMode",), plan_ids)
    return any(result_error.get(tid) is False for tid in plan_ids)


def should_skip(file_path: str) -> bool:
    if not file_path:
        return True
    norm = file_path.replace("\\", "/").lower()
    for part in SKIP_PATH_PARTS:
        if part.replace("\\", "/").lower() in norm:
            return True
    return False


BLOCK_MSG = (
    "BLOCKED: Non-trivial change (2+ files this turn) without reformulation. "
    "Target: {file_path}. RECOVERY: Output a brief reformulation BEFORE retrying — "
    "state (1) what you understood, (2) what you'll do, (3) what you won't touch, "
    "(4) files impacted. Use the keyword REFORMULATION or a numbered list mentioning "
    "files. See rules/Workflows.md 'Reformulate before coding'."
)


def resolve_transcript(data: dict) -> tuple[str, bool]:
    """Return (transcript_to_scan, readable) for the CURRENT thread of work.

    `agent_id` present = sub-agent -> scan its OWN journal, never the parent's.
    readable=False = no trustworthy context -> the caller passes, never blocks.
    See the module docstring for the measured facts behind this.
    """
    parent = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    agent_id = data.get("agent_id")
    if not agent_id:
        return parent, True  # parent session — behaviour unchanged
    if not parent:
        return "", False
    own = Path(parent).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
    return (str(own), True) if own.exists() else ("", False)


def main() -> None:
    _, data = read_hook_input()
    file_path = get_file_path(data)
    if should_skip(file_path):
        pass_through()

    # A sub-agent scans its OWN journal, never its parent's (see module docstring).
    transcript_path, readable = resolve_transcript(data)
    if not readable:
        pass_through()

    writes_so_far = count_writes_this_turn(transcript_path)

    # writes_so_far does not include the current attempt
    # If this is the 1st write of the turn -> pass
    # If this is the 2nd or later -> require reformulation
    if writes_so_far < 1:
        pass_through()

    if has_reformulation_marker(transcript_path):
        pass_through()

    # An approved plan (plan mode) IS the reformulation for the actions it
    # describes — see Interpretation-Protocol 'Approved plan'.
    if has_approved_plan(transcript_path):
        pass_through()

    block(BLOCK_MSG.format(file_path=file_path))


if __name__ == "__main__":
    main()
