"""Shared utilities for Claude Code hooks (MNK-GoRin methodology).

This module is the common floor for hooks under .claude/hooks/{guards,lifecycle,
quality,deploy,memory,tests}/. It is intentionally minimal and cross-platform
(Windows + Linux). No external dependencies — stdlib only.

Conventions
-----------
- Use pathlib.Path, never os.path string ops.
- Never shell=True; never os.name branching inside the logic.
- Hooks exit code semantics:
    0 = pass (silent)
    2 = block (stderr message printed)
    other = warning (stderr message printed, do not block)

Recovery principle
------------------
Every BLOCKED/WARNING message MUST tell the caller what to do next.
Use `format_block(...)` / `format_warn(...)` to keep messages consistent.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# --- I/O ----------------------------------------------------------------------


def read_hook_input() -> tuple[str, dict[str, Any]]:
    """Read stdin, return (raw_text, parsed_json_or_empty_dict).

    Hooks receive JSON on stdin from the Claude Code harness. If stdin is
    malformed or empty, return raw='', data={}.
    """
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    return raw, data


def get_tool_input(data: dict[str, Any]) -> dict[str, Any]:
    """Return the tool_input subdict if present, else the flat data."""
    return data.get("tool_input") or data


def get_file_path(data: dict[str, Any]) -> str:
    """Extract the file path Claude is about to write/edit. Empty string if absent."""
    return get_tool_input(data).get("file_path", "") or ""


def get_content(data: dict[str, Any]) -> str:
    """Extract the content payload (for Write) or new_string (for Edit)."""
    ti = get_tool_input(data)
    return ti.get("content") or ti.get("new_string") or ""


def get_command(data: dict[str, Any]) -> str:
    """Extract the bash command (for Bash tool)."""
    return get_tool_input(data).get("command", "") or ""


# --- Exit helpers -------------------------------------------------------------


def block(message: str) -> None:
    """Print message to stderr and exit 2 (block the tool call)."""
    print(message, file=sys.stderr)
    sys.exit(2)


def warn(message: str) -> None:
    """Print warning to stderr without blocking. Caller is responsible for exit 0."""
    print(message, file=sys.stderr)


def pass_through() -> None:
    """Exit 0 silently — the hook authorizes the tool call."""
    sys.exit(0)


# --- Message formatters -------------------------------------------------------


def format_block(reason: str, recovery: str, reference: str | None = None) -> str:
    """Format a BLOCKED message with required RECOVERY section.

    Example:
        format_block(
            "tkinter is forbidden",
            "Use PySide6 instead. Replace `import tkinter` with `from PySide6 ...`",
            reference="rules/Conventions.md")
    """
    msg = f"BLOCKED: {reason}. RECOVERY: {recovery}"
    if reference:
        msg += f" See {reference}."
    return msg


def format_warn(reason: str, action: str, reference: str | None = None) -> str:
    """Format a WARNING message with required ACTION section."""
    msg = f"WARNING: {reason}. ACTION: {action}"
    if reference:
        msg += f" See {reference}."
    return msg


# --- Deploy detection (shared by every pre-deploy gate) -----------------------

# One source of truth for "is this command a deploy?". Previously copy-pasted
# into 8 hooks, each with a slightly different ssh sub-pattern that matched the
# BARE substring docker/deploy/systemctl anywhere after the host — so a grep, an
# rm, or a filename containing "deploy"/"docker" was misread as a deploy and ran
# the (slow, network-probing) gates. The patterns below match deploy ACTIONS,
# never bare tool-name substrings.

_DEPLOY_PATTERNS = [
    re.compile(r"\bdocker(?:-compose)?\s+(?:compose\s+)?up\b"),
    re.compile(r"\bdocker\s+stack\s+deploy\b"),
    re.compile(r"\bdeploy\.sh\b"),
    re.compile(r"\bvercel\s+(?:--prod|deploy)\b"),
    re.compile(r"\bfly\s+deploy\b"),
    re.compile(r"\bnetlify\s+deploy\b"),
    re.compile(r"\brailway\s+up\b"),
    re.compile(r"\bgh\s+workflow\s+run\s+deploy"),
    re.compile(r"\bansible-playbook\b"),
    re.compile(r"\bkubectl\s+apply\b"),
    re.compile(r"\bhelm\s+upgrade\b"),
    re.compile(r"\bsystemctl\s+(?:restart|start|stop)\b"),
    re.compile(r"\bnginx\s+-s\s+reload\b"),
    # Remote deploy over ssh: a real deploy ACTION after the host, not the bare
    # substring docker/deploy/systemctl (which appears in filenames/grep args).
    re.compile(
        r"\bssh\s+\S+\s+.*?(?:"
        r"docker(?:-compose)?\s+(?:compose\s+)?(?:up|restart)|"
        r"docker\s+stack\s+deploy|"
        r"systemctl\s+(?:restart|start|stop)|"
        r"deploy\.sh|"
        r"nginx\s+-s\s+reload)"
    ),
    # git pull chained into a deploy action (not the bare word "restart").
    re.compile(
        r"\bgit\s+pull\b.*?(?:"
        r"docker(?:-compose)?\s+(?:compose\s+)?(?:up|restart)|"
        r"systemctl\s+(?:restart|start|stop)|"
        r"deploy\.sh)"
    ),
]


def looks_like_deploy(cmd: str) -> bool:
    """True when the bash command is a deploy-class action.

    Matches deploy ACTIONS (docker compose up, systemctl restart, deploy.sh,
    ssh host <action>, ...), never a bare docker/deploy/systemctl substring, so
    a grep/rm/filename that merely mentions those words is not a false positive.
    """
    return bool(cmd) and any(p.search(cmd) for p in _DEPLOY_PATTERNS)


# --- Paths --------------------------------------------------------------------


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) until a `.git` directory is found.

    Returns the repo root. If no .git found, returns the starting point
    (caller must handle gracefully).
    """
    here = (start or Path.cwd()).resolve()
    for parent in [here, *here.parents]:
        if (parent / ".git").exists():
            return parent
    return here


def canonical_project_name(start: Path | None = None) -> str:
    """Project name that stays stable inside a git worktree.

    A worktree dir is branch-named, so `find_repo_root().name` is wrong there
    and broke the Obsidian gate (looked for a note that never exists).
    `git rev-parse --git-common-dir` points at the main repo's shared `.git`;
    its parent name is the canonical project. Falls back to the local dir
    name when git is unavailable — never raises.
    """
    repo = find_repo_root(start)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            common = Path(out.stdout.strip())
            if not common.is_absolute():
                common = (repo / common).resolve()
            name = common.parent.name
            if name:
                return name
    except Exception:
        pass
    return repo.name if repo else "<project>"
