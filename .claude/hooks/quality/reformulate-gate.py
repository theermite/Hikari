#!/usr/bin/env python3
"""Reformulate gate — PreToolUse Write|Edit. AVERTIT, ne bloque plus (2026-10-26).

Pourquoi il avertit. Le mandat du 2026-10-24 dit: « un changement non trivial s'annonce, il ne
s'approuve pas ». Un blocage fait attendre une approbation que la règle n'exige plus. Mesure du
2026-10-26 sur 50 séances: 201 blocages, dont 104 contournés en répétant la même écriture — et le
journal perd le texte de Takumi quand sa réflexion est coupée en deux, donc une annonce FAITE est
vue comme absente. Un garde-fou qui bloque une annonce faite retire la capacité sans rien protéger
(voir plus bas, sous-agents). Il avertit donc, au plus trois fois par tour.


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
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import get_file_path, pass_through, read_hook_input, warn  # type: ignore  # noqa: E402
from reformulate_agreements import has_design_approval, names_a_pet_brick  # type: ignore  # noqa: E402
from transcript_reader import (  # type: ignore  # noqa: E402
    entry_message,
    iter_entries,
    errored_tool_ids,
    norm_path,
    spoken_blocks,
)
from user_turns import _is_continuation_message, _is_real_user_message  # type: ignore  # noqa: E402

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


# Every path decision in this gate uses the ONE canonical form, shared with the
# said channel (transcript_reader.norm_path, `.`/`..` collapsed, 2026-09-26).
_norm_path = norm_path


def is_plan_file(path: str) -> bool:
    """Plan mode's plan file IS the reformulation awaiting approval (2026-09-25:
    blocking it left no in-turn recovery at all). Anchored to the harness plans
    folder — a project folder that merely happens to be named `.claude/plans/`
    stays gated (independent review 2026-09-26)."""
    roots = [Path.home() / ".claude"]
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        roots.append(Path(config_dir))
    target = _norm_path(path)
    return any(target.startswith(_norm_path(str(r / "plans")) + "/") for r in roots)



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
    # Markdown table naming files/actions. Honesty.md constraint 3 REQUIRES a
    # table for 3+ items, so a table reformulation is the mandated format — the
    # keyword-only patterns above blocked it (cross-model review 2026-07-29).
    re.compile(
        r"^\s*\|[^\n]*\b(fichier|file|action|ampleur|touche|impact)[^\n]*\|",
        re.IGNORECASE | re.MULTILINE,
    ),
)

# Harness-supplied identifiers used to build file paths. Kept to a tight
# allow-list so a malformed value can never traverse out of its directory
# (cross-model review 2026-07-29 reproduced a real write outside .claude/state/).
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _window_entries(transcript_path: str):
    """Yield message dicts from latest back to (excluding) the last real,
    instruction-bearing user message. tool_result deliveries AND continuation
    nudges do NOT close the window."""
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg is None:
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
    """Check what Takumi said since the last real instruction for a reformulation.

    The boundary is the last real, instruction-bearing user message; both
    tool_result deliveries and continuation nudges keep the window open, so a
    reformulation emitted before a blocked attempt or a "go" is still honored.

    "Said" = his text AND the shared said-file channel
    (transcript_reader.spoken_blocks, 2026-09-28): the journal drops his text
    when his thinking is split in two, never his tool calls. A said-file write
    that FAILED counts for nothing; one still in flight counts — results land
    only after every tool call of the message (independent review 2026-09-27).
    """
    if not transcript_path:
        return False
    texts: list[str] = []
    errored: set = set()
    for msg in _window_entries(transcript_path):
        errored |= errored_tool_ids(msg)
        texts.extend(spoken_blocks(msg, errored))
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
        msg = entry_message(entry)
        if msg is None:
            continue
        if msg.get("role") == "user":
            _collect_results(msg, result_error)
        elif msg.get("role") == "assistant":
            _collect_tool_ids(msg, ("ExitPlanMode",), plan_ids)
    return any(result_error.get(tid) is False for tid in plan_ids)


def should_skip(file_path: str) -> bool:
    if not file_path:
        return True
    if is_plan_file(file_path):
        return True
    norm = _norm_path(file_path)
    for part in SKIP_PATH_PARTS:
        if part.replace("\\", "/").lower() in norm:
            return True
    return False


MAX_RAPPELS = 3

WARN_MSG = (
    "ANNONCE ATTENDUE: changement non trivial (2+ fichiers ce tour) sans annonce visible. "
    "Cible: {file_path}. Mandat: une phrase — ce que je fais, ce que je ne touche pas, les "
    "fichiers — puis j'agis; aucune approbation n'est attendue. Si ton texte n'est pas vu "
    "(le journal le perd quand la reflexion est coupee en deux), ecris-le dans "
    "<projet>/.claude/state/said.md: un appel d'outil est toujours enregistre."
)


def resolve_transcript(data: dict) -> tuple[str, bool]:
    """Return (transcript_to_scan, readable) for the CURRENT thread of work.

    `agent_id` present = sub-agent -> scan its OWN journal, never the parent's.
    readable=False = no trustworthy context -> the caller passes, never blocks.
    See the module docstring for the measured facts behind this.
    """
    parent = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if not isinstance(parent, str):
        parent = ""
    agent_id = data.get("agent_id")
    if not agent_id or not isinstance(agent_id, str):
        return parent, True  # parent session — behaviour unchanged
    # A malformed agent_id falls back to the PARENT journal (gate stays armed),
    # never to a path built from the untrusted value.
    if not SAFE_ID.match(agent_id):
        return parent, True
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

    # A design document (PET, CDC, brief) Jay approved IS the authorization too.
    if not data.get("agent_id") and has_design_approval(transcript_path):
        pass_through()

    # So does Jay's own instruction naming a brick of the project's PET.
    if not data.get("agent_id") and names_a_pet_brick(transcript_path, file_path):
        pass_through()

    # Au plus trois rappels par tour: au-delà, répéter coûte du contexte sans rien apprendre.
    if writes_so_far <= MAX_RAPPELS:
        warn(WARN_MSG.format(file_path=file_path))
    pass_through()


if __name__ == "__main__":
    # Fail open on any unexpected error (malformed payload, Windows file lock):
    # a crashing gate must never break Jay's session with a raw traceback.
    # block()/pass_through() exit via SystemExit, which must stay unswallowed.
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberate fail-open boundary
        print(f"[reformulate-gate] passing through on unexpected error: {exc}", file=sys.stderr)
        sys.exit(0)
