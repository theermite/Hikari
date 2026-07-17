#!/usr/bin/env python3
"""D4 — UserPromptSubmit guard: warn when README is stale at /session-end.

Trigger
-------
UserPromptSubmit whose prompt contains `/session-end`.

Action
------
1. Compute the set of files changed since the session start (using the
   session's `started_at` recorded by the time-tracker hook, or a 24h
   fallback).
2. Evaluate the 5 README-update criteria (cf. Plan Phase D / B2):
   1. New public command/feature shipped (new file in `commands/` or
      `.claude/commands/` or commit with `feat(commands` / `feat(public`)
   2. Install/run steps changed (dependency manifest, `.env*`, compose,
      Dockerfile, port refs)
   3. Major stack/version bump (manifest version field changed)
   4. Breaking change (`!:` in commit subject or `BREAKING CHANGE:` in body)
   5. Section README factually obsolete (subjective — out of scope here)
3. If at least one criterion matches AND README.md is NOT in the diff:
   exit 1 with WARN stderr.
4. Otherwise pass through silently.

Non-blocking by design: missing README update is a friction, not a hazard.

Reference: docs/Briefs/Plan-Implementation-Phases-A-F (Phase D4 + B2).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_warn,
    pass_through,
    read_hook_input,
    warn,
)

# --- Trigger detection -------------------------------------------------------

_SESSION_END_RE = re.compile(r"(?:^|\s)/session-end\b")


def _is_session_end_prompt(prompt: str) -> bool:
    return bool(prompt) and bool(_SESSION_END_RE.search(prompt))


# --- Git helpers -------------------------------------------------------------


def _git(args: list[str]) -> str:
    """Run a git command, return stdout or empty on error."""
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout or ""


def _session_start_sha(session_id: str) -> str:
    """Best-effort: SHA of the first commit since the session started.

    Falls back to `HEAD~10` if no session marker / no commits since.
    """
    # Try to read the time-tracker session state file
    started_at = ""
    try:
        repo_root = Path(_git(["rev-parse", "--show-toplevel"]).strip() or ".")
        state_file = repo_root / ".claude" / "state" / f"time-session-{session_id}.json"
        if state_file.exists():
            import json
            data = json.loads(state_file.read_text(encoding="utf-8"))
            started_at = (data.get("started_at") or "").strip()
    except (OSError, ValueError):
        started_at = ""

    if started_at:
        out = _git(["log", f"--since={started_at}", "--reverse", "--pretty=format:%H"]).strip()
        first = out.splitlines()[0] if out else ""
        if first:
            return first

    # Fallback: HEAD~10 or root
    out = _git(["rev-list", "-n", "1", "HEAD~10"]).strip()
    return out or "HEAD"


def _changed_files_since(sha: str) -> list[str]:
    out = _git(["diff", "--name-only", f"{sha}..HEAD"]).strip()
    return [line for line in out.splitlines() if line]


def _commit_messages_since(sha: str) -> str:
    return _git(["log", "--pretty=format:%B", f"{sha}..HEAD"])


# --- Criteria evaluation -----------------------------------------------------

_MANIFEST_FILES = {
    "package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock",
    "pyproject.toml", "requirements.txt", "uv.lock",
    "mix.exs", "mix.lock",
    "Cargo.toml", "Cargo.lock",
    "go.mod", "go.sum",
    "Gemfile", "Gemfile.lock",
    "composer.json", "composer.lock",
}

_INFRA_PATTERNS = (
    re.compile(r"(^|/)\.env"),                  # .env, .env.example, sub/.env
    re.compile(r"(^|/)docker-compose.*\.ya?ml$"),
    re.compile(r"(^|/)Dockerfile($|\.)"),
)

_COMMAND_PATH_PATTERNS = (
    re.compile(r"^\.claude/commands/"),
    re.compile(r"(^|/)commands/[^/]+\.(md|py|ex|exs|ts|js|sh)$"),
)

_BREAKING_SUBJECT_RE = re.compile(r"^[a-z]+(\([^)]*\))?!:", re.MULTILINE)
_BREAKING_BODY_RE = re.compile(r"BREAKING CHANGE:", re.MULTILINE)
_FEAT_COMMANDS_RE = re.compile(r"^feat\((?:commands|public|cli)\b", re.MULTILINE)


def _criterion_new_command(files: list[str], log: str) -> bool:
    for f in files:
        for pat in _COMMAND_PATH_PATTERNS:
            if pat.search(f):
                return True
    if _FEAT_COMMANDS_RE.search(log):
        return True
    return False


def _criterion_install_run_changed(files: list[str]) -> bool:
    for f in files:
        base = f.rsplit("/", 1)[-1]
        if base in _MANIFEST_FILES:
            return True
        for pat in _INFRA_PATTERNS:
            if pat.search(f):
                return True
    return False


def _criterion_breaking_change(log: str) -> bool:
    if _BREAKING_SUBJECT_RE.search(log):
        return True
    if _BREAKING_BODY_RE.search(log):
        return True
    return False


def _readme_in_diff(files: list[str]) -> bool:
    for f in files:
        if f.rsplit("/", 1)[-1].lower() == "readme.md":
            return True
    return False


# --- Main --------------------------------------------------------------------


def main() -> None:
    _, data = read_hook_input()
    prompt = (data.get("prompt") or "").strip()
    if not _is_session_end_prompt(prompt):
        pass_through()

    session_id = data.get("session_id") or ""
    sha = _session_start_sha(session_id)
    files = _changed_files_since(sha)
    log = _commit_messages_since(sha)

    matched: list[str] = []
    if _criterion_new_command(files, log):
        matched.append("new public command/feature")
    if _criterion_install_run_changed(files):
        matched.append("install/run steps changed (deps/env/compose)")
    if _criterion_breaking_change(log):
        matched.append("breaking change detected")

    if not matched:
        pass_through()

    if _readme_in_diff(files):
        # README already updated this session — no warning.
        pass_through()

    reasons = "; ".join(matched)
    warn(format_warn(
        reason=f"README.md not updated this session but criteria matched: {reasons}",
        action="review README and update sections impacted by the above changes "
               "(install steps, commands list, breaking notes) before closing.",
        reference="Plan Phase D4 + B2 (5 criteria)",
    ))
    sys.exit(1)


if __name__ == "__main__":
    main()
