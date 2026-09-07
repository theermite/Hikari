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

import re
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


def _ellipsis(texte: str, limite: int = 120) -> str:
    return texte[:limite] + ("..." if len(texte) > limite else "")


# Quel champ decrit l'appel, par outil. Une table se lit et s'etend ; une
# cascade de `if` grossit jusqu'a devenir illisible (complexite mesuree 14).
_CHAMP_PARLANT = {
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "Bash": "command",
    "Grep": "pattern",
    "Glob": "pattern",
}


def _describe_tool_call(name: str, inp: dict[str, Any]) -> str:
    """One-line description of a tool call for the brief."""
    champ = _CHAMP_PARLANT.get(name)
    if champ:
        return _ellipsis(str(inp.get(champ) or "?"))
    if name == "TodoWrite":
        return f"{len(inp.get('todos') or [])} todo(s)"
    premiere = next((v for v in inp.values() if isinstance(v, str) and v), None)
    return _ellipsis(premiere) if premiere else "(no input)"


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


_EN_SUSPENS_RE = re.compile(r"\[EN-SUSPENS\][\s`*_|:>-]*(.+)", re.I)
_RESOLU_RE = re.compile(r"\[RESOLU\][\s`*_|:>-]*(.+)", re.I)


def collect_open_threads(transcript_path: str | Path) -> list[str]:
    """Les objections et fils laisses ouverts, dans l'ordre ou ils sont venus.

    Demande de Jay le 2026-09-06 : ce qu'une reprise a chaud perdrait doit
    entrer dans le resume. Un fil marque `[EN-SUSPENS]` y entre ; le meme texte
    marque `[RESOLU]` en sort.

    Collecte depuis la session, jamais redigee de memoire : un sommaire recopie
    vieillit et ment (mesure du 2026-08-30, trois chiffres contradictoires le
    meme jour pour un meme inventaire).
    """
    ouverts: list[str] = []
    resolus: set[str] = set()
    # L'iterateur rend les messages du plus recent au plus ancien ; un fil se
    # lit dans l'ordre ou il est venu.
    for texte in reversed(list(_iter_assistant_messages(transcript_path))):
        for ligne in texte.splitlines():
            m = _RESOLU_RE.search(ligne)
            if m:
                resolus.add(m.group(1).strip().strip("*`_ "))
                continue
            m = _EN_SUSPENS_RE.search(ligne)
            if m:
                fil = m.group(1).strip().strip("*`_ ")
                if fil and fil not in ouverts:
                    ouverts.append(fil)
    return [f for f in ouverts if f not in resolus]


def build_brief(transcript_path: str, session_id: str, trigger: str = "auto") -> str:
    """Build a Markdown handoff brief from the current transcript.

    `trigger` labels what fired the brief: "auto-85", "pre-compact", "manual".
    Returns the brief content (UTF-8 string, LF newlines). Caller persists it
    via `write_brief`.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = [
        f"# Handoff Brief — session {session_id}",
        "",
        f"- Generated: {now}",
        f"- Trigger: {trigger}",
        "",
    ]

    lines += _corps(transcript_path)
    lines += _instructions_de_reprise()
    return "\n".join(lines)


def _corps(transcript_path: str) -> list[str]:
    """Le corps du resume. Les fils ouverts viennent EN PREMIER.

    C'est ce qu'une reprise a chaud perdrait, et une section qu'on lit apres
    coup ne sert a rien (demande de Jay, 2026-09-06).
    """
    return (
        _section(
            "Fils ouverts / objections en suspens",
            collect_open_threads(transcript_path),
            vide="aucun",
        )
        + _section(
            "Files Modified This Session",
            [f"`{f}`" for f in _collect_files_modified(transcript_path)[:30]],
        )
        + _section(
            "Last User Messages",
            _collect_last_user_messages(transcript_path),
            numerote=True,
        )
        + _section("Recent Tool Calls", _collect_recent_tool_calls(transcript_path))
        + _bloc_texte(
            "Last Assistant Text", _collect_last_assistant_text(transcript_path)
        )
    )


def _section(titre: str, elements, vide: str = "_(none recorded)_",
             numerote: bool = False) -> list[str]:
    """Une section de liste, qui dit toujours quelque chose — jamais rien."""
    lignes = [f"## {titre} ({len(elements)})" if elements else f"## {titre}"]
    if not elements:
        lignes += [vide, ""]
        return lignes
    for i, e in enumerate(elements, 1):
        lignes.append(f"{i}. {e}" if numerote else f"- {e}")
    lignes.append("")
    return lignes


def _bloc_texte(titre: str, texte: str) -> list[str]:
    if not texte:
        return [f"## {titre}", "_(none recorded)_", ""]
    return [f"## {titre}", "```", texte, "```", ""]


def _instructions_de_reprise() -> list[str]:
    return [
        "## Resume Instructions",
        "1. Re-read `.claude/CLAUDE.md` to refresh identity + rules.",
        "2. Re-read this brief in full — the open threads FIRST.",
        "3. Run `git status` and `git log --oneline -5` to confirm working state.",
        "4. Review the last user messages above to recover intent.",
        "5. Continue from the last in-progress task, or ask Jay for redirection.",
        "",
    ]


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
