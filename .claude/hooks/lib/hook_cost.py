"""What the guards cost in the conversation, read from the session journal.

Jay, 2026-09-28: « ca coute des tokens sur mes sessions ? ». Running a guard
costs nothing — it is a local script. What costs is the text a guard puts in
front of the model: injected context, and refusals (plus the retries they
trigger, which this meter counts as `refusals`, never prices).

Selection is on the journal's own fields, never on a word in the text
(Quality.md « measuring a thing, never a word about it »):

- context: `hook_success.content` (UserPromptSubmit / SessionStart output),
  `hook_additional_context.content`
- refusals: `hook_blocking_error.blockingError`, and an errored tool_result
  whose text OPENS with the harness frame `PreToolUse:<tool> hook error`
- NOT counted: `hook_system_message` (shown to Jay, not to the model),
  `hook_success.stdout` of tool hooks (their content is "" — the model never
  sees it; what does reach it arrives as hook_additional_context)

Tokens are an ESTIMATE (CHARS_PER_TOKEN), labelled as such wherever shown —
the journal holds no per-hook token count to read.

Stdlib only.
"""

from __future__ import annotations

import re

from transcript_reader import entry_message, iter_entries

# Rough conversion, NOT a measure: English prose runs near 4 characters per
# token, French and code often fewer. Shown as « ~N (estimation) », never bare.
CHARS_PER_TOKEN = 4

_REFUSAL_FRAME = re.compile(r"^(?:Pre|Post)ToolUse:\S* hook error")


def _as_text(value) -> str:
    """A journal value as plain text: str, list of str/text blocks, or {"blockingError": ...}."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_as_text(v) for v in value)
    if isinstance(value, dict):
        return _as_text(value.get("blockingError") or value.get("text") or "")
    return ""


def _context_chars(att: dict) -> int:
    if att.get("type") in ("hook_success", "hook_additional_context"):
        return len(_as_text(att.get("content")))
    return 0


def _tool_result_refusals(entry) -> list[str]:
    """Errored tool_results that open with the harness refusal frame."""
    msg = entry_message(entry)
    content = msg.get("content") if msg is not None and msg.get("role") == "user" else None
    if not isinstance(content, list):
        return []
    errored = [_as_text(b.get("content")) for b in content
               if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error") is True]
    return [t for t in errored if _REFUSAL_FRAME.match(t)]


def _refusal_texts(entry) -> list[str]:
    """Refusal texts carried by this entry (attachment or errored tool_result)."""
    att = entry.get("attachment") if isinstance(entry, dict) else None
    if isinstance(att, dict) and att.get("type") == "hook_blocking_error":
        return [_as_text(att.get("blockingError"))]
    return _tool_result_refusals(entry)


def measure(transcript_path) -> dict:
    """{context_chars, refusal_chars, refusals, tokens_est, lues} for one session."""
    context = refusal_chars = refusals = lues = 0
    for entry in iter_entries(transcript_path, reverse=False):
        lues += 1
        att = entry.get("attachment") if isinstance(entry, dict) else None
        if isinstance(att, dict):
            context += _context_chars(att)
        for text in _refusal_texts(entry):
            refusals += 1
            refusal_chars += len(text)
    return {"context_chars": context, "refusal_chars": refusal_chars, "refusals": refusals,
            "tokens_est": (context + refusal_chars) // CHARS_PER_TOKEN, "lues": lues}
