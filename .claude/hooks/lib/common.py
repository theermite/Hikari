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

import atexit
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# --- I/O ----------------------------------------------------------------------


_EVENT = ""             # the harness event of this run, learned when the input is read
_PENDING: list[str] = []  # warnings waiting to be handed to the model at exit
# The events whose `additionalContext` the harness gives to the model. Elsewhere (Stop, SessionEnd...) the field
# does not exist: printing it would only be noise, so those warnings stay on stderr.
_CONTEXT_EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart")


def read_hook_input() -> tuple[str, dict[str, Any]]:
    """Read stdin, return (raw_text, parsed_json_or_empty_dict).

    Hooks receive JSON on stdin from the Claude Code harness. If stdin is
    malformed or empty, return raw='', data={}.
    """
    global _EVENT
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    _EVENT = str(data.get("hook_event_name") or "") if isinstance(data, dict) else ""
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


def emit_context(event: str, messages: list[str]) -> None:
    """Hand `messages` to the model as ONE `additionalContext` document (read only on exit 0).

    Why (2026-10-30): a warning on stderr with exit 0 is seen in a journal, never by the model — the Lego and
    translation warnings were mute while 362 files carried hard-coded text.
    """
    if messages and event in _CONTEXT_EVENTS:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                                 "additionalContext": "\n".join(messages)}}))
        sys.stdout.flush()


def _flush_pending() -> None:
    emit_context(_EVENT, _PENDING)
    _PENDING.clear()


def warn(message: str) -> None:
    """Warn without blocking: on stderr for the human AND, at exit, to the model. Caller exits 0."""
    print(message, file=sys.stderr)
    if not _PENDING:
        atexit.register(_flush_pending)
    _PENDING.append(message)


def pass_through() -> None:
    """Exit 0 silently — the hook authorizes the tool call."""
    sys.exit(0)


# --- Message formatters -------------------------------------------------------


RECOVERY_ANNEX = ".claude/rules-ondemand/Debug-Et-Blocage.md"

# Les seize anciennes règles (rules-archives/) et où est passé chacun de leurs sujets. Les messages de
# blocage de plus de trente garde-fous citent encore `rules/Quality.md` & co.: au lieu de réécrire chaque
# message, la table est appliquée ici, à l'entonnoir. Un seul endroit à tenir.
ANCIENNES_REGLES = {
    "Interpretation-Protocol.md": ".claude/rules/01-Lecture.md",
    "Mandate.md": ".claude/rules/01-Lecture.md",
    "Workflows.md": ".claude/rules/02-Parcours.md (+ annexe Conduite)",
    "Quality.md": ".claude/rules/03-Qualite.md (+ annexes Tests-Et-Mesures, Interface, Socle-Minimal)",
    "Monozukuri.md": ".claude/rules/03-Qualite.md",
    "Autonomous-Session.md": ".claude/rules-ondemand/Session-Autonome.md",
    "QE-V2-Retroactive.md": ".claude/rules-ondemand/Conduite.md",
    "Honesty.md": ".claude/rules/04-Verite.md",
    "Non-Technical-Advice.md": ".claude/rules/04-Verite.md",
    "Memory.md": ".claude/rules/05-Savoir.md (+ annexe Memoire-Format)",
    "Content-Provenance.md": ".claude/rules-ondemand/Provenance-Du-Contenu.md",
    "Confidentiality.md": ".claude/rules/07-Securite.md (+ annexe Confidentialite-Detail)",
    "Identity.md": ".claude/rules-ondemand/Identite-Et-Strategie.md",
    "Strategic-Context.md": ".claude/rules-ondemand/Identite-Et-Strategie.md",
    "Conventions.md": ".claude/rules-ondemand/Conventions-Et-Pile.md",
    "Dignity.md": ".claude/rules-ondemand/Interface.md",
    # Trois règles périmées de l'ancien Michi-no-Kata, archivées le 2026-10-26 (décision de Jay).
    # Destinations = fichiers PROPAGUES seulement : un receveur n'a ni docs/ ni le CLAUDE.md de Kata.
    "Agents-Models.md": ".claude/rules-ondemand/Conduite.md",
    "Quality-Security.md": ".claude/rules/03-Qualite.md (+ règle 07-Securite)",
    "Static-Analysis.md": ".claude/rules-ondemand/Tests-Et-Mesures.md",
}
_REF_ANCIENNE = re.compile(r"(?:\.claude/)?rules/(" + "|".join(re.escape(n) for n in ANCIENNES_REGLES) + ")")


def reference_actuelle(reference: str) -> str:
    """`rules/Quality.md > Lego Library` -> `.claude/rules/03-Qualite.md (+ annexes …) > Lego Library`."""
    return _REF_ANCIENNE.sub(lambda m: ANCIENNES_REGLES[m.group(1)], reference)


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
        msg += f" See {reference_actuelle(reference)}."
    # Seul porteur de l'annexe de reprise: aucun événement d'outil ne dit « un blocage vient d'avoir lieu ».
    return msg + f" After any block: {RECOVERY_ANNEX}."


def format_warn(reason: str, action: str, reference: str | None = None) -> str:
    """Format a WARNING message with required ACTION section."""
    msg = f"WARNING: {reason}. ACTION: {action}"
    if reference:
        msg += f" See {reference_actuelle(reference)}."
    return msg


# --- Deploy detection (shared by every pre-deploy gate) -----------------------

# One source of truth for "is this command a deploy?". Previously copy-pasted
# into 8 hooks, each with a slightly different ssh sub-pattern that matched the
# BARE substring docker/deploy/systemctl anywhere after the host — so a grep, an
# rm, or a filename containing "deploy"/"docker" was misread as a deploy and ran
# the (slow, network-probing) gates. The patterns below match deploy ACTIONS,
# never bare tool-name substrings.

# Options may sit between `compose` and the verb: `docker compose -f prod.yml up`, `--profile prod up`.
_COMPOSE_OPTS = r"(?:-\S+\s+(?:[^\s-]\S*\s+)?)*"
# Options globales de docker AVANT « compose » : `docker --context vps compose up`, `docker -H tcp://h:2376 compose up`.
_DOCKER_GLOBAL_OPTS = _COMPOSE_OPTS

_DEPLOY_PATTERNS = [
    re.compile(r"\bdocker(?:-compose)?\s+" + _DOCKER_GLOBAL_OPTS + r"(?:compose\s+)?" + _COMPOSE_OPTS + r"up\b"),
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
        r"docker(?:-compose)?\s+(?:compose\s+)?" + _COMPOSE_OPTS + r"(?:up|restart)|"
        r"docker\s+stack\s+deploy|"
        r"systemctl\s+(?:restart|start|stop)|"
        r"deploy\.sh|"
        r"nginx\s+-s\s+reload)"
    ),
    # git pull chained into a deploy action (not the bare word "restart").
    re.compile(
        r"\bgit\s+pull\b.*?(?:"
        r"docker(?:-compose)?\s+(?:compose\s+)?" + _COMPOSE_OPTS + r"(?:up|restart)|"
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
