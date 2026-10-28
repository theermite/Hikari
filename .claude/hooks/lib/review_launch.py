"""What a reviewer was GIVEN: the launch prompt itself, read from the journal (2026-10-28).

The spoken text Takumi writes around a reviewer launch is often lost by the journal; the launch
is recorded as a `tool_use` block with its real prompt, and a brief that lives in that prompt
cannot be written next to it (Jay 2026-10-28). Kept apart from `transcript_reader` (file size).
"""

from __future__ import annotations

import re

LAUNCHERS = ("Agent", "Task")
_BRIEF_FIELDS = (
    ("objectif", r"objectif"),
    ("perimetre", r"p[ée]rim[èe]tre"),
    ("zones suspectes", r"zones?\s+suspectes?"),
)
_REFUTE_WORD = re.compile(r"r[ée]fut|contredi", re.IGNORECASE)


def brief_from_prompt(prompt) -> str:
    """The `[REVIEW-BRIEF]` a launch prompt carries, rewritten in the guards' four-line form,
    or "" when a field is missing or the prompt never asks to refute."""
    if not isinstance(prompt, str) or not _REFUTE_WORD.search(prompt):
        return ""
    lines = []
    for name, pattern in _BRIEF_FIELDS:
        found = re.search(rf"(?im)^[\s*_#>\-]*{pattern}[^\n:]{{0,40}}:[\s*_]*(\S[^\n]*)", prompt)
        if not found:
            return ""
        # Backticks would be stripped as code by the guards and empty the field.
        lines.append(f"- {name}: {found.group(1).strip().replace(chr(96), chr(39))}")
    lines.append("- consigne: refuter (consigne du lancement du relecteur)")
    return "[REVIEW-BRIEF]\n" + "\n".join(lines)


def brief_from_blocks(blocks) -> str:
    """The brief of the first reviewer launch among an assistant message's content blocks."""
    for blk in blocks:
        if not isinstance(blk, dict) or blk.get("type") != "tool_use":
            continue
        if blk.get("name") not in LAUNCHERS or not isinstance(blk.get("input"), dict):
            continue
        if "review" not in str(blk["input"].get("subagent_type", "")).lower():
            continue
        brief = brief_from_prompt(blk["input"].get("prompt"))
        if brief:
            return brief
    return ""


_HANDBACK_MARK = "[Subagent hand-back]"
_AGENT_MESSAGE = re.compile(r'<agent-message from="[0-9A-Za-z]+">')


def verdict_lines_from_user_message(message) -> str:
    """The `[REVIEW] ` lines of a sub-agent report recorded as a USER message, or "".

    This environment records a reviewer's report as a user-role message ("Another Claude session sent a
    message: <agent-message from=...> [Subagent hand-back] ..."), not as an attachment: the guards heard
    nothing of a real verdict and only what Takumi wrote himself (Jay 2026-10-28). A user message without
    the hand-back mark and the agent-message envelope is never a verdict. Only the `[REVIEW] ` lines are
    kept, as for an attachment: a `[REVIEW-SKIP]` or `[VEILLE]` quoted in a report must lift no gate."""
    if not isinstance(message, dict) or message.get("role") != "user":
        return ""
    content = message.get("content")
    if not isinstance(content, str) or _HANDBACK_MARK not in content or not _AGENT_MESSAGE.search(content):
        return ""
    lines = (ln.strip() for ln in content.splitlines())
    return "\n".join(ln for ln in lines if ln.startswith("[REVIEW] "))
