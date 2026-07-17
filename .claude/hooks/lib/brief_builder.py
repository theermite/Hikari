"""Build and persist handoff briefs from the Claude Code transcript.

Used by:
  - lifecycle/auto-handoff-85.py  -> auto-write brief at ~85% context
  - lifecycle/pre-compact-handoff.py -> snapshot brief just before compaction
  - lifecycle/post-compact-recheck.py -> read brief and surface in resume block

A brief is a plain-text Markdown document persisted at
`<repo>/.claude/state/handoff-<session_id>.md`. It captures the minimum needed
to resume a session after `/clear` or context compaction:

  - Files modified in this session
  - Last user messages (intent)
  - Recent tool calls (work in progress)
  - Last assistant text (current line of thinking)
  - Resume instructions (5-step recovery list)

Stdlib only. Cross-platform (Windows + Linux). LF line endings, UTF-8.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from session_state import state_dir  # type: ignore  # lib/ added to sys.path by hook
from transcript_reader import iter_entries, iter_tool_calls  # type: ignore


BRIEF_NAME_TEMPLATE = "handoff-{session_id}.md"
RECENT_TOOLS_LIMIT = 15
RECENT_USER_MSGS = 3
USER_MSG_PREVIEW = 200
ASSISTANT_TEXT_MAX = 500


def _extract_text(content: Any) -> str:
    """Pull joined text out of an assistant content list or string."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text") or ""
            if text:
                parts.append(text)
    return "\n".join(parts)


def _iter_user_messages(transcript_path: str | Path) -> Iterator[str]:
    """Yield user message text, latest-first."""
    for entry in iter_entries(transcript_path):
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        text = _extract_text(msg.get("content"))
        if text:
            yield text


def _iter_assistant_messages(transcript_path: str | Path) -> Iterator[str]:
    """Yield assistant text, latest-first."""
    for entry in iter_entries(transcript_path):
        msg = entry.get("message") or entry
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        text = _extract_text(msg.get("content"))
        if text:
            yield text


def _collect_files_modified(transcript_path: str | Path) -> list[str]:
    """Return unique file_paths from Write/Edit tool calls, most recent first."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for tool in iter_tool_calls(transcript_path):
        name = tool.get("name", "")
        if name not in ("Write", "Edit"):
            continue
        fp = (tool.get("input") or {}).get("file_path", "") or ""
        if not fp or fp in seen_set:
            continue
        seen.append(fp)
        seen_set.add(fp)
    return seen


def _collect_recent_tool_calls(transcript_path: str | Path, limit: int = RECENT_TOOLS_LIMIT) -> list[str]:
    """Return a list of short tool-call descriptions, most recent first."""
    out: list[str] = []
    for tool in iter_tool_calls(transcript_path):
        if len(out) >= limit:
            break
        name = tool.get("name", "?")
        inp = tool.get("input") or {}
        desc = _describe_tool_call(name, inp)
        out.append(f"{name}: {desc}")
    return out


def _describe_tool_call(name: str, inp: dict[str, Any]) -> str:
    """One-line description of a tool call for the brief."""
    if name in ("Read", "Write", "Edit"):
        return str(inp.get("file_path", "") or "?")
    if name == "Bash":
        cmd = str(inp.get("command", "") or "?")
        return cmd[:120] + ("..." if len(cmd) > 120 else "")
    if name in ("Grep", "Glob"):
        return str(inp.get("pattern", "") or "?")
    if name == "TodoWrite":
        todos = inp.get("todos") or []
        return f"{len(todos)} todo(s)"
    # Generic: first short value
    for v in inp.values():
        if isinstance(v, str) and v:
            return v[:120] + ("..." if len(v) > 120 else "")
    return "(no input)"


def _collect_last_user_messages(transcript_path: str | Path, limit: int = RECENT_USER_MSGS) -> list[str]:
    """Return last user messages (most recent first), truncated."""
    out: list[str] = []
    for text in _iter_user_messages(transcript_path):
        if len(out) >= limit:
            break
        clean = text.strip().replace("\r\n", "\n")
        if not clean:
            continue
        # Skip system-reminder noise
        if clean.startswith("<system-reminder>") or "<system-reminder>" in clean[:200]:
            continue
        preview = clean[:USER_MSG_PREVIEW]
        if len(clean) > USER_MSG_PREVIEW:
            preview += "..."
        out.append(preview)
    return out


def _collect_last_assistant_text(transcript_path: str | Path, max_chars: int = ASSISTANT_TEXT_MAX) -> str:
    """Return the last assistant text (latest)."""
    for text in _iter_assistant_messages(transcript_path):
        clean = text.strip()
        if not clean:
            continue
        if len(clean) > max_chars:
            return clean[:max_chars] + "..."
        return clean
    return ""


def build_brief(transcript_path: str, session_id: str, trigger: str = "auto") -> str:
    """Build a Markdown handoff brief from the current transcript.

    `trigger` labels what fired the brief: "auto-85", "pre-compact", "manual".
    Returns the brief content (UTF-8 string, LF newlines). Caller persists it
    via `write_brief`.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    files = _collect_files_modified(transcript_path)
    user_msgs = _collect_last_user_messages(transcript_path)
    tool_calls = _collect_recent_tool_calls(transcript_path)
    last_asst = _collect_last_assistant_text(transcript_path)

    lines: list[str] = []
    lines.append(f"# Handoff Brief — session {session_id}")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Trigger: {trigger}")
    lines.append("")

    lines.append("## Files Modified This Session")
    if files:
        for f in files[:30]:
            lines.append(f"- `{f}`")
    else:
        lines.append("_(none recorded)_")
    lines.append("")

    lines.append(f"## Last User Messages (latest {len(user_msgs)})")
    if user_msgs:
        for i, msg in enumerate(user_msgs, 1):
            lines.append(f"{i}. {msg}")
            lines.append("")
    else:
        lines.append("_(none recorded)_")
        lines.append("")

    lines.append(f"## Recent Tool Calls (latest {len(tool_calls)})")
    if tool_calls:
        for tc in tool_calls:
            lines.append(f"- {tc}")
    else:
        lines.append("_(none recorded)_")
    lines.append("")

    lines.append("## Last Assistant Text")
    if last_asst:
        lines.append("```")
        lines.append(last_asst)
        lines.append("```")
    else:
        lines.append("_(none recorded)_")
    lines.append("")

    lines.append("## Resume Instructions")
    lines.append("1. Re-read `.claude/CLAUDE.md` to refresh identity + rules.")
    lines.append("2. Re-read this brief in full.")
    lines.append("3. Run `git status` and `git log --oneline -5` to confirm working state.")
    lines.append("4. Review the last user messages above to recover intent.")
    lines.append("5. Continue from the last in-progress task, or ask Jay for redirection.")
    lines.append("")

    return "\n".join(lines)


def write_brief(brief: str, repo_root: Path, session_id: str) -> Path:
    """Persist the brief to `.claude/state/handoff-<session_id>.md` atomically."""
    path = state_dir(repo_root) / BRIEF_NAME_TEMPLATE.format(session_id=session_id)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(brief, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return path


def read_brief(repo_root: Path, session_id: str) -> str:
    """Read an existing brief, or empty string if missing."""
    path = state_dir(repo_root) / BRIEF_NAME_TEMPLATE.format(session_id=session_id)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def brief_path(repo_root: Path, session_id: str) -> Path:
    """Return the canonical brief path for this session."""
    return state_dir(repo_root) / BRIEF_NAME_TEMPLATE.format(session_id=session_id)
