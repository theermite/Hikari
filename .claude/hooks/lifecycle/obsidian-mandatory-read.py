#!/usr/bin/env python3
"""Shinzo mandatory-read gate — PreToolUse(Edit|Write|Bash).

Companion to session-start-obsidian.py reminder. Workflows.md declares
Shinzo sync BLOCKING at session start: project notes MUST be loaded from
Shinzo 02-Projets/ via the Read tool before any state-mutating tool.

Primary source: Read tool calls on Shinzo/02-Projets/ files (portable,
no MCP dependency). Obsidian MCP aliases kept as fallback during
transition (vault_read / get_note).

This hook scans the transcript and verifies 3 MANDATORY files were read
(by name substring):
  1. _Cross-Project        (cross-project decisions, infra, blockers)
  2. _Index                (project inventory)
  3. <project>             (current project file)

A 4th file (<project>-Notes-Jay) is RECOMMENDED but not blocking.

After all 3 mandatory patterns are detected, a state marker is written
and subsequent mutating tools pass through silently.

Skip cases:
  - Tool is not Edit/Write/Bash (Read/Glob/Grep/etc. always pass)
  - Read-only Bash commands (ls, cd, git status, etc.)
  - State marker already set this session
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import (  # noqa: E402
    block,
    canonical_project_name,
    find_repo_root,
    format_block,
    get_command,
    pass_through,
    read_hook_input,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import iter_tool_calls  # noqa: E402


MUTATING_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit"}
# The Obsidian MCP read tool has shipped under several names across versions.
# Match ANY of these aliases so the gate is satisfiable whichever one the
# active MCP server exposes. Add new aliases here, never replace.
# Primary: Read tool on Shinzo/02-Projets/ files (portable, no MCP needed).
# Fallback: Obsidian MCP aliases kept for backward compatibility.
SHINZO_READ_TOOL_NAMES = (
    "Read",
    "mcp__obsidian-vault__vault_read",
    "mcp__obsidian-vault__get_note",
)

# Read-only Bash prefixes that don't need the Obsidian gate.
# git pull/fetch are session-start bootstrap mechanics, not work — never gate them.
READ_ONLY_BASH = (
    "ls", "cd", "pwd", "cat", "head", "tail", "grep", "find", "echo",
    "which", "wc", "git status", "git log", "git diff", "git branch",
    "git show", "git remote", "git pull", "git fetch",
)


def _collect_read_paths(transcript_path: str) -> list[str]:
    """Return file paths read via Read tool or any known Obsidian MCP alias."""
    if not transcript_path:
        return []
    paths: list[str] = []
    aliases = set(SHINZO_READ_TOOL_NAMES)
    try:
        for call in iter_tool_calls(transcript_path):
            if call.get("name") not in aliases:
                continue
            input_data = call.get("input") or {}
            path = input_data.get("path") or input_data.get("file_path") or ""
            if path:
                paths.append(path)
    except Exception:
        return []
    return paths


def _missing_patterns(read_paths: list[str], required: list[str]) -> list[str]:
    """Return required patterns that don't match any read path (case-insensitive)."""
    joined = " ".join(read_paths).lower()
    return [p for p in required if p.lower() not in joined]


def _should_pass_early(tool_name: str, data: dict) -> bool:
    """True when this tool call never needs the Obsidian gate."""
    if tool_name not in MUTATING_TOOLS:
        return True
    if tool_name == "Bash":
        cmd = get_command(data).strip()
        if any(cmd.startswith(p) for p in READ_ONLY_BASH):
            return True
    return False


def _block_missing(project, missing, required, session_id, repo) -> None:
    """Reset the marker so the gate re-fires, then emit the block (no return)."""
    from session_state import read_state, write_state  # local import
    st = read_state("obsidian-sync-checked", session_id=session_id, repo_root=repo)
    st["seen"] = []
    write_state("obsidian-sync-checked", st, session_id=session_id, repo_root=repo)

    listing = (
        f"\n  1. [SHINZO]/02-Projets/_Cross-Project.md"
        f"\n  2. [SHINZO]/02-Projets/_Index.md"
        f"\n  3. [SHINZO]/02-Projets/{project}.md"
        f"\n  (4. optional: [SHINZO]/02-Projets/{project}-Notes-Jay.md if it exists)"
        f"\n  [SHINZO] = D:/30-Dev-Projects/Shinzo (local) | ~/Shinzo (VPS)"
    )
    loaded = len(required) - len(missing)
    block(format_block(
        f"MANDATORY FIRST READ not satisfied — {loaded}/{len(required)} file(s) unread",
        "Read the missing file(s) from Shinzo 02-Projets/ via the Read tool "
        f"before any Edit/Write/Bash:{listing}\n"
        f"Missing patterns: {', '.join(missing)}\n"
        "These are the BLOCKING files declared in CLAUDE.md (Interpretation-Protocol, Confidentiality, Monozukuri). "
        "They define how Takumi reads every other rule See CLAUDE.md MANDATORY FIRST READ.",
        reference="Workflows.md 'Sync Shinzo project notes'",
    ))


def main() -> None:
    raw, data = read_hook_input()
    tool_name = data.get("tool_name") or ""

    if _should_pass_early(tool_name, data):
        pass_through()

    session_id = data.get("session_id", "") or "no-session"
    transcript_path = data.get("transcript_path", "")
    repo = find_repo_root()
    # Canonical name, NOT repo.name: inside a worktree the dir is branch-named
    # and the project note would never match -> permanent unsatisfiable block.
    project = canonical_project_name()

    # 3 mandatory patterns: cross-project, index, project file
    required = ["_Cross-Project", "_Index", project]

    # One-shot per session
    if not mark_once("obsidian-sync-checked", "checked", session_id=session_id):
        pass_through()

    read_paths = _collect_read_paths(transcript_path)
    missing = _missing_patterns(read_paths, required)

    if missing:
        _block_missing(project, missing, required, session_id, repo)

    pass_through()


if __name__ == "__main__":
    main()
