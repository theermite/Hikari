"""Read recent entries from the Claude Code transcript JSONL.

The Claude Code harness passes `transcript_path` to every hook event.
This module yields parsed entries from that file, latest-first by default,
so hooks can scan recent assistant text, tool calls, and tool results without
re-implementing JSONL parsing.

Stdlib only. Cross-platform (Windows + Linux).
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any, Iterator


# iter_entries: every OSError or ValueError from opening OR READING the file
# (missing file, a permission denial, an unencodable path -- 10th and 11th
# independent reviews, 2026-09-15) is swallowed the same way -- this is a
# best-effort reader, never a hard requirement. It reads the open file object
# directly
# rather than read_text().splitlines() (10th review): str.splitlines() also
# breaks on the Unicode line separators U+2028, U+2029 and NEL (\x85) --
# legal INSIDE a JSON string value (a prompt pasted from Word/PDF, a file
# read by the Read tool), which silently cut one valid entry into two invalid
# ones. Universal-newline text mode only ever splits on \n, \r or \r\n. It
# also avoids loading the whole file into one string before splitting it a
# second time -- measured on a real 63.7 MB transcript: 573.1 MB peak before
# this change (both reverse=True and reverse=False, the two were identical),
# 1.3 MB after for reverse=False (true streaming), 74.6 MB for reverse=True
# (still one list of lines, but only one, and proportional to file size).
def iter_entries(transcript_path: str | Path, reverse: bool = True) -> Iterator[dict[str, Any]]:
    """Yield parsed JSONL entries from the transcript.

    Returns latest-first when reverse=True (default — most hooks scan
    recent activity). Malformed lines are skipped silently. Empty/missing
    transcript yields nothing — caller decides policy.
    """
    p = Path(transcript_path) if transcript_path else None
    if not p:
        return
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            lines = reversed(list(f)) if reverse else f
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
    except (OSError, ValueError):
        return


# entry_message closes a 9-site family (2026-09-14/15, 3 rounds of review):
# a transcript JSON line can be valid yet non-object (`null`), and callers
# assumed a dict. 3 rounds searched for a CODE SHAPE
# ("entry.get('message') or entry") instead of the FAMILY -- context-gauge.py's
# own inline parsing matched neither shape textually and was missed twice.
#
# Importers that want the fallback: iter_tool_calls, assistant_text_blocks and
# count_turns (this file), brief_builder.py, friction.py, logs-first.py,
# reformulate-gate.py, veille-extended.py, hook-blocks-stats.entry_role.
#
# context-gauge.py deliberately does NOT import THIS function: the 6th review
# found its fallback ("no dict message? use the entry itself") made
# context-gauge accept a `usage` field placed flat on the entry, a shape it
# has never accepted (test_a_flat_usage_is_not_accepted). It DOES import
# iter_entries, though (9th review, 2026-09-15): 3 earlier rounds each found
# one more way a hand-rolled copy of file-reading + json.loads in
# context-gauge.py had drifted narrower than this module's own error handling
# -- isinstance on usage, then int()/OverflowError, then json.loads/ValueError,
# each fixed one line higher in the same function. The file-open itself (no
# errors="replace") was the line above all three, and losing THAT one meant
# one bad byte anywhere in the transcript discarded every measurement already
# read, not just the offending line. Delegating the read to iter_entries ends
# the pattern instead of closing it a 4th time.
def entry_message(entry) -> dict | None:
    """The "message" dict a transcript entry carries, or None."""
    if not isinstance(entry, dict):
        return None
    msg = entry.get("message") or entry
    return msg if isinstance(msg, dict) else None


def iter_tool_calls(transcript_path: str | Path, tool_name: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield tool_use blocks from assistant messages, latest-first.

    If `tool_name` is given, filter to that tool only ("Read", "Edit", ...).
    Each yielded dict contains at least: name, input.
    """
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg is None:
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if tool_name and block.get("name") != tool_name:
                continue
            yield block


def assistant_text_blocks(entry: dict) -> list[str]:
    """Text blocks Takumi actually SAID in this one parsed entry, or [].

    Only role == "assistant" counts: a tool_use input or a tool_result's
    content sits in the same JSON tree as his real text blocks but is never
    something he said (independent review, 2026-09-14 -- veille_markers.py and
    veille-extended.py each duplicated this before sharing it here).
    """
    msg = entry_message(entry)
    if msg is None or msg.get("role") != "assistant":
        return []
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    return [b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]


def iter_assistant_text(transcript_path: str | Path, limit: int = 20) -> Iterator[str]:
    """Yield text content from recent assistant messages, latest-first.

    Stops after `limit` text blocks to bound cost. Useful for pattern-scan
    hooks (e.g. rules-vs-memory) that need recent Takumi output.
    """
    count = 0
    for entry in iter_entries(transcript_path):
        if count >= limit:
            return
        for text in assistant_text_blocks(entry):
            yield text
            count += 1
            if count >= limit:
                return


# --- What Takumi SAID, even when the journal dropped his text (2026-09-28) ---
#
# Measured 2026-09-26 on the 60 latest journals: 391 assistant messages whose
# thinking is saved as two entries, and NONE of them kept its text block; 2203
# messages with one thinking entry kept theirs. A tool_use is always recorded.
# So a guard that reads only text blocks goes blind exactly when it matters —
# the reformulation, veille and review markers were all invisible that week.
#
# The channel: text Takumi writes (Write content / Edit new_string) to
# `<any repo>/.claude/state/said-*.md` counts as said, at its place in the
# journal. `reformulation*.md` stays accepted (first shipped name, 2026-09-26).
# A write whose result is an error was never said; one still in flight is —
# the journal writes results only after every tool call of the message.
#
# Guards that police Takumi's WORDING (simple-language, clock-not-fatigue) keep
# iter_assistant_text: they read the last message, which is text-only and
# always recorded, and a said-file is not the message Jay read.

SAID_PREFIXES = ("said", "reformulation")


def norm_path(path: str) -> str:
    """Canonical form for every path decision: forward slashes, `.`/`..`
    collapsed (pure string work, never touches the disk), lower case.

    A raw-string compare let `~/.claude/plans/../../repo/src/x.py` pass for a
    plan file (independent review, 2026-09-26)."""
    return posixpath.normpath(path.replace("\\", "/")).lower()


def is_said_file(path) -> bool:
    """`<any repo>/.claude/state/said*.md` (or `reformulation*.md`), nothing looser.

    Not anchored to one repo on purpose: a session routinely writes into a
    sibling repo. The body still has to carry the marker a guard looks for."""
    if not isinstance(path, str):
        return False
    parts = norm_path(path).split("/")
    return (
        len(parts) >= 3
        and parts[-3:-1] == [".claude", "state"]
        and parts[-1].startswith(SAID_PREFIXES)
        and parts[-1].endswith(".md")
    )


def _content_of(entry, role: str) -> list:
    """The content blocks of this entry when it is a `role` message, else []."""
    msg = entry_message(entry)
    if msg is None or msg.get("role") != role:
        return []
    content = msg.get("content")
    return content if isinstance(content, list) else []


def _said_body(blk) -> str:
    """The text a Write|Edit tool_use puts into a said-file, else ""."""
    if not isinstance(blk, dict) or blk.get("type") != "tool_use":
        return ""
    name = blk.get("name")
    inp = blk.get("input")
    if name not in ("Write", "Edit") or not isinstance(inp, dict):
        return ""
    if not is_said_file(inp.get("file_path")):
        return ""
    body = inp.get("content") if name == "Write" else inp.get("new_string")
    return body if isinstance(body, str) else ""


def said_file_writes(entry) -> list[tuple[object, str]]:
    """(tool_use id, body) of every Write|Edit to a said-file in this entry."""
    out = []
    for blk in _content_of(entry, "assistant"):
        body = _said_body(blk)
        if body:
            out.append((blk.get("id"), body))
    return out


def errored_tool_ids(entry) -> set:
    """Ids of the tool calls this entry reports as failed."""
    content = _content_of(entry, "user")
    return {b.get("tool_use_id") for b in content
            if isinstance(b, dict) and b.get("type") == "tool_result"
            and b.get("is_error") is True and b.get("tool_use_id") is not None}


def spoken_blocks(entry, errored: set) -> list[str]:
    """What Takumi said in this entry: his text blocks, then the said-files he
    wrote that did not fail. `errored` must hold the failed ids seen so far —
    read latest-first, a result always comes before its call."""
    said = [body for tid, body in said_file_writes(entry) if tid not in errored]
    return assistant_text_blocks(entry) + said


def reviewer_handback(entry) -> str:
    """A sub-agent's final report, as the harness delivered it, or "".

    Written by the reviewer, never by Takumi: it cannot be lost with his text,
    and he cannot forge it. Only `origin.kind == "peer"` with `handback` counts
    — a queued message from Jay has no such origin. The harness indents every
    report line by two spaces; the frame is removed so markers read as usual.

    Only its `[REVIEW]` verdict lines are kept (independent review 2026-09-29):
    a hand-back is ANY sub-agent's report, and a [REVIEW-SKIP] or [VEILLE]
    quoted in an exploration report must never lift a gate."""
    origin = _handback_origin(entry)
    body = origin.get("body") if origin else None
    if not isinstance(body, str):
        return ""
    lines = (ln.strip() for ln in body.splitlines())
    return "\n".join(ln for ln in lines if ln.startswith("[REVIEW] "))


def _handback_origin(entry) -> dict | None:
    """The origin of a sub-agent hand-back attachment, else None."""
    att = entry.get("attachment") if isinstance(entry, dict) else None
    if not isinstance(att, dict) or att.get("type") != "queued_command":
        return None
    origin = att.get("origin")
    if not isinstance(origin, dict):
        return None
    if origin.get("kind") != "peer" or origin.get("handback") is not True:
        return None
    return origin


def iter_spoken_text(transcript_path: str | Path, limit: int = 20,
                     include_reviewer: bool = False) -> Iterator[str]:
    """Like iter_assistant_text, plus the said-file channel — latest-first, in
    journal order, `limit` counting every item. With include_reviewer, a
    reviewer's report is heard at its place too: only the review guards ask
    for it, since a [VEILLE] in a reviewer's report is not Takumi's veille.

    A verdict is heard once, and a contrary one is never erased (rule agreed
    with Jay, 2026-10-06): « un avis qui repete est ignore, un avis qui
    contredit n'est jamais efface ». Within one review round — a round opens
    at each [REVIEW-BRIEF] — a Takumi [REVIEW] line carrying the SAME verdict
    as a reviewer hand-back already delivered is an echo and is dropped.
    Anything else stays: a contrary verdict, a verdict with no hand-back
    (human review), a verdict from an earlier round. No text comparison —
    it lost to a space or a full stop (review 2026-09-29) — and no blanket
    priority — « the reviewer is authoritative » erased a later human FAIL
    and was reverted (review 2026-10-06)."""
    if not include_reviewer:
        yield from _limited(_spoken_items(transcript_path, False), limit)
        return
    chronological = reversed(list(_spoken_items(transcript_path, True)))
    heard = [t for t in _drop_echoes(chronological) if t]
    yield from _limited(reversed(heard), limit)


def _spoken_items(transcript_path, include_reviewer: bool) -> Iterator[tuple[str, str]]:
    """(source, text) latest-first: source is "takumi" or "reviewer"."""
    errored: set = set()
    for entry in iter_entries(transcript_path):
        errored |= errored_tool_ids(entry)
        items = [("takumi", t) for t in spoken_blocks(entry, errored)]
        report = reviewer_handback(entry) if include_reviewer else ""
        if report:
            items.append(("reviewer", report))
        yield from reversed(items)


def _limited(texts, limit: int) -> Iterator[str]:
    for count, item in enumerate(texts, start=1):
        yield item[1] if isinstance(item, tuple) else item
        if count >= limit:
            return


# Only the VERDICT WORD is read — never the rest of the line, so spacing,
# punctuation, quotes or a decorated reviewer name cannot change the outcome.
# `[REVIEW]` exactly: [REVIEW-BRIEF] and [REVIEW-SKIP] are other markers.
_VERDICT_LINE = re.compile(
    r"\[review\][^\n]*?verdict[\s*_`\"']*:?[\s*_`\"']*(pass|fail)\b", re.IGNORECASE)
_SUR_SHA = re.compile(r"\bsur\s+[\"'`]?([0-9a-f]{7,40})\b", re.IGNORECASE)
# A round opens on a brief that OPENS a line, outside code blocks — a sentence
# quoting the tag is not a brief (review 2026-10-06, F3).
_BRIEF_OPENS_LINE = re.compile(r"^[\s*_`>]*\[review-brief\]", re.IGNORECASE | re.MULTILINE)


def _verdict_of(line: str):
    """(verdict word, commit or None) of a [REVIEW] line, or None."""
    m = _VERDICT_LINE.search(line)
    if not m:
        return None
    sha = _SUR_SHA.search(line[:m.end()])
    return m.group(1).lower(), (sha.group(1).lower() if sha else None)


def _drop_echoes(chronological) -> Iterator[str]:
    """Texts in journal order, Takumi's echoes of the reviewer's LATEST verdict
    removed. Only the latest counts (review 2026-10-06, F1): remembering every
    verdict of a round erased a human FAIL after « FAIL -> fix -> PASS ».
    A hand-back's verdict is its FIRST [REVIEW] line — the reviewer opens with
    it; later ones are quotes (review 2026-10-06 on f5cc888, case 3)."""
    state = {"latest": None}  # (word, commit) of the reviewer's latest verdict
    for src, text in chronological:
        if src == "reviewer":
            found = [v for v in map(_verdict_of, text.splitlines()) if v]
            state["latest"] = found[0] if found else state["latest"]
            yield text
            continue
        yield _without_echoes(text, state)


def _is_echo(verdict, latest) -> bool:
    """Same word, and the same commit as far as both sides name one: a sha may
    be written shorter or longer, or left out of a retelling (review on f5cc888,
    cases 1-2). A contrary verdict differs by its WORD, so it is never an echo."""
    if verdict is None or latest is None or verdict[0] != latest[0]:
        return False
    a, b = verdict[1], latest[1]
    return a is None or b is None or a.startswith(b) or b.startswith(a)


def _without_echoes(text: str, state: dict) -> str:
    """Takumi's text, line by line: a brief that opens a line (outside fenced
    code) starts a new round from THAT line (case 4); a line echoing the
    reviewer's latest verdict loses its verdict part, what precedes it stays."""
    kept, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and _BRIEF_OPENS_LINE.match(line):
            state["latest"] = None  # a new review round starts here
        elif _is_echo(_verdict_of(line), state["latest"]):
            line = line[:_VERDICT_LINE.search(line).start()].rstrip(" *_`>")
            if not line:
                continue
        kept.append(line)
    return "\n".join(kept)


def count_turns(transcript_path: str | Path) -> tuple[int, int]:
    """Return (user_turns, assistant_turns) in the transcript.

    Rough proxy for conversation length. Used by context-awareness hook.
    """
    user, assistant = 0, 0
    for entry in iter_entries(transcript_path, reverse=False):
        msg = entry_message(entry)
        if msg is None:
            continue
        role = msg.get("role")
        if role == "user":
            user += 1
        elif role == "assistant":
            assistant += 1
    return user, assistant


def count_tool_calls(transcript_path: str | Path, tool_name: str | None = None) -> int:
    """Count tool_use blocks in the transcript, optionally filtered by name."""
    return sum(1 for _ in iter_tool_calls(transcript_path, tool_name=tool_name))


def has_read_file(transcript_path: str | Path, file_path_substring: str) -> bool:
    """Return True if any Read tool call references a path containing the substring.

    Match is substring-based (case-sensitive) to tolerate absolute vs relative paths
    and forward/backward slash variations. Caller normalizes input as needed.
    """
    needle = file_path_substring.replace("\\", "/")
    for block in iter_tool_calls(transcript_path, tool_name="Read"):
        fp = (block.get("input") or {}).get("file_path", "") or ""
        if needle in fp.replace("\\", "/"):
            return True
    return False


def has_instructions_attachment(transcript_path: str | Path, file_path_substring: str) -> bool:
    """Return True if the file's content was already delivered as a harness
    instructions attachment (CLAUDE.md / .claude/rules/*.md auto-loaded at
    session start), not just via an explicit Read tool call.

    Confirmed on a real transcript (2026-09-18): Claude Code writes one entry
    shaped {"attachment": {"type": "instructions", "files": [{"path": ...}]}}
    carrying the full text of every project-instructions file. A caller that
    only checks Read tool calls misses this and re-asks for content the model
    already has -- paid for twice, every session.
    """
    needle = file_path_substring.replace("\\", "/")
    for entry in iter_entries(transcript_path):
        if not isinstance(entry, dict):
            continue
        att = entry.get("attachment")
        if not isinstance(att, dict) or att.get("type") != "instructions":
            continue
        files = att.get("files")
        if not isinstance(files, list):
            continue
        for f in files:
            if not isinstance(f, dict):
                continue
            fp = f.get("path", "") or ""
            if needle in fp.replace("\\", "/"):
                return True
    return False
