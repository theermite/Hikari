#!/usr/bin/env python3
"""hook-blocks-stats.py — SessionEnd observability (A2: guardrail-fatigue meter).

Counts how often each hook BLOCKED or WARNED during the session, grouped by a
normalized signature (the short reason after "BLOCKED:" / "WARNING:"). Appends
one cumulative entry per session to <repo>/.claude/state/hook-blocks.jsonl.

Why this exists
---------------
The methodology has ~30 hooks. Some block legitimately, some create friction
(false positives). Today there is no measure of WHICH guardrail fires most.
This meter surfaces that signal so a chronically-blocking hook can be reviewed
(reclassified WARN, relaxed, or fixed) BEFORE the friction pushes Takumi or Jay
to bypass it. It reads the transcript in aggregate — zero change to the 30 hooks.

What it measures (and what it does NOT)
---------------------------------------
- Measures: FREQUENCY of blocks/warns per reason. A good proxy for friction.
- Does NOT yet distinguish a justified block from a false positive. That needs
  correlation with a later successful retry/skip — a v2 refinement.

Design choices
--------------
- Only NON-assistant transcript entries are scanned, so Takumi's own citations
  of "BLOCKED:" in prose are never counted (only real hook output is).
- Lines whose reason contains <...> placeholders are skipped (RECOVERY/templates).
- Pure observability: this hook NEVER blocks. It always exits 0, swallowing any
  I/O error (a meter must never break a session).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # noqa: E402
from friction import detect_overcome_blocks, signature  # noqa: E402
from transcript_reader import iter_entries  # noqa: E402

# A real hook message starts a line with BLOCKED: or WARNING: (see common.py
# format_block / format_warn). Capture the reason that follows, one per line.
MARKER_RE = re.compile(r"^\s*(BLOCKED|WARNING):\s*(.+?)\s*$", re.MULTILINE)

STATE_REL = ".claude/state/hook-blocks.jsonl"


def read_input() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return {}


def entry_role(entry: object) -> str:
    """Best-effort role extraction (transcript shape varies: nested or flat)."""
    if not isinstance(entry, dict):
        return ""
    msg = entry.get("message")
    if isinstance(msg, dict):
        return msg.get("role") or ""
    return entry.get("role", "") or ""


def extract_text(node: object) -> str:
    """Collect every string in a nested transcript entry, joined by newlines."""
    chunks: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, str):
            chunks.append(n)
        elif isinstance(n, dict):
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return "\n".join(chunks)


def scan(transcript_path: str) -> tuple[dict[str, int], dict[str, int]]:
    blocks: dict[str, int] = {}
    warns: dict[str, int] = {}
    for entry in iter_entries(transcript_path):
        if entry_role(entry) == "assistant":
            continue  # Takumi quoting a message is not a real block
        text = extract_text(entry)
        for kind, reason in MARKER_RE.findall(text):
            if "<" in reason and ">" in reason:
                continue  # placeholder/template line, not a real occurrence
            sig = signature(reason)
            if not sig:
                continue
            bucket = blocks if kind == "BLOCKED" else warns
            bucket[sig] = bucket.get(sig, 0) + 1
    return blocks, warns


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_journal(session_id: str, blocks: dict, warns: dict, overcome: dict) -> None:
    entry = {"session_id": session_id, "ts": now_iso(),
             "blocks": blocks, "warns": warns, "overcome": overcome}
    state_path = find_repo_root() / STATE_REL
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # observability must never break the session


def _emit_summary(blocks: dict, warns: dict, overcome: dict) -> None:
    total_b, total_w = sum(blocks.values()), sum(warns.values())
    top = (max(blocks.items(), key=lambda kv: kv[1], default=None)
           or max(warns.items(), key=lambda kv: kv[1], default=None))
    top_str = f" — top: {top[0]} (x{top[1]})" if top else ""
    print(f"hook-blocks: {total_b} block(s), {total_w} warn(s) this session{top_str}", file=sys.stderr)
    if overcome:
        cand = ", ".join(sorted(overcome))
        print(f"hook-friction: {sum(overcome.values())} block(s) overcome by retry "
              f"(possible parasite): {cand}. If any hindered you, note it under "
              f"'Hooks Friction' in MNK-GoRin-Notes-Jay.md.", file=sys.stderr)


def main() -> None:
    data = read_input()
    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    if not transcript_path:
        sys.exit(0)
    blocks, warns = scan(transcript_path)
    overcome = detect_overcome_blocks(transcript_path)
    if not blocks and not warns:
        sys.exit(0)
    _append_journal(session_id, blocks, warns, overcome)
    _emit_summary(blocks, warns, overcome)
    sys.exit(0)


if __name__ == "__main__":
    main()
