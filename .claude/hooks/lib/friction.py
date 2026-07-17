"""friction.py — detect 'overcome' hook blocks in a transcript.

An overcome block = a tool call blocked by a hook (PreToolUse exit 2 -> tool
result is_error with 'BLOCKED:'), where a LATER call on the SAME target then
succeeded. That retry-and-pass is the strongest transcript signal that the block
created friction (a false positive, or forced throwaway work) rather than
stopping a genuinely bad action.

PROXY, not proof: a legitimate gate (e.g. read-this-file-first) is also overcome
by complying. Jay's manual flag is the ground truth; this only surfaces
candidates worth reviewing. Stdlib only, cross-platform.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from transcript_reader import iter_entries  # noqa: E402

_BLOCK_RE = re.compile(r"BLOCKED:\s*(.+)", re.IGNORECASE)
MAX_SIG_WORDS = 9


def signature(reason: str) -> str:
    """Normalize a block reason into a stable grouping key (first sentence,
    lowercased, bounded word count) — same scheme as hook-blocks-stats."""
    head = re.split(r"[.\n]", reason, maxsplit=1)[0].strip().lower()
    return " ".join(head.split()[:MAX_SIG_WORDS])


def _content_blocks(entry: dict) -> list:
    msg = entry.get("message") or entry
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    return content if isinstance(content, list) else []


def _target(tool_input: object) -> str:
    if not isinstance(tool_input, dict):
        return ""
    return tool_input.get("file_path") or tool_input.get("command") or ""


def _result_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def _events(transcript_path: str) -> list[tuple]:
    """Chronological events: ('use', id, tool, target) | ('result', id, is_error, text)."""
    out: list[tuple] = []
    for entry in iter_entries(transcript_path, reverse=False):
        for b in _content_blocks(entry):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                out.append(("use", b.get("id"), b.get("name") or "", _target(b.get("input"))))
            elif b.get("type") == "tool_result":
                out.append(("result", b.get("tool_use_id"), bool(b.get("is_error")), _result_text(b)))
    return out


def _calls(events: list[tuple]) -> list[tuple]:
    """Resolve each result against its tool_use: (tool, target, blocked, signature)."""
    use = {e[1]: (e[2], e[3]) for e in events if e[0] == "use"}
    calls: list[tuple] = []
    for e in events:
        if e[0] != "result":
            continue
        tool, target = use.get(e[1], ("", ""))
        m = _BLOCK_RE.search(e[3] or "")
        blocked = bool(e[2] and m)
        calls.append((tool, target, blocked, signature(m.group(1)) if m else ""))
    return calls


def _later_success(calls: list[tuple], start: int, key: tuple) -> bool:
    for tool, target, blocked, _ in calls[start:]:
        if (tool, target) == key and not blocked:
            return True
    return False


def _count_overcome(calls: list[tuple]) -> dict[str, int]:
    overcome: dict[str, int] = {}
    seen: set = set()
    for i, (tool, target, blocked, sig) in enumerate(calls):
        key = (tool, target)
        if not blocked or not sig or key in seen:
            continue
        if _later_success(calls, i + 1, key):
            overcome[sig] = overcome.get(sig, 0) + 1
            seen.add(key)
    return overcome


def detect_overcome_blocks(transcript_path: str) -> dict[str, int]:
    """Map {block signature: number of targets blocked then overcome by retry}."""
    return _count_overcome(_calls(_events(transcript_path)))
