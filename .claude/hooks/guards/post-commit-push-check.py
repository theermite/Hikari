#!/usr/bin/env python3
"""D1 — PostToolUse Bash: auto-push after git commit (with skip conditions).

Trigger
-------
PostToolUse on a Bash tool call whose command matched `git commit ...`
(excluding `--amend` rewrites, which are intentional and often local-only).

Action
------
Auto-execute `git push` to keep remote + VPS in sync. Jay works alone — manual
push after every commit is friction that adds zero quality. The BLOCKING
pre-commit hooks (bash-guard, write-guard, atomic-commit-check) already catch
secrets, destructive patterns, and oversized commits, so the push itself does
not bypass any quality gate.

Skip conditions (no push, exit 0)
---------------------------------
1. Commit message contains `[WIP]` or `[NO-PUSH]` (case-insensitive) → WARN
   explaining why the push was skipped, then exit. Lets Takumi or Jay hold
   intentionally local commits when needed.
2. Detached HEAD (branch == "HEAD") → silent.
3. No upstream tracking on current branch → silent (cannot push without
   knowing where).
4. `ahead == 0` → silent (nothing to push, in sync with upstream).
5. `ahead > 5` → WARN, do not push. An accumulation that large is a signal
   (offline session, deliberate batching, recovery state) that deserves
   Jay's eyeballs before a mass push hits the remote.

Otherwise → run `git push`. Emit a single-line stderr summary so Jay sees
in the terminal what just happened.

Reference: rules/Workflows.md > "Fix = Deploy" + Phase D brief.
Origin: 2026-05-31 — Jay's frustration #6 (manual push reminders).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_warn,
    get_command,
    pass_through,
    read_hook_input,
    warn,
)

_COMMIT_RE = re.compile(r"\bgit\s+commit\b")
_AMEND_RE = re.compile(r"\bgit\s+commit\b[^&;|]*(?<![\w-])--amend\b")
_STATUS_AHEAD_RE = re.compile(r"\[ahead (\d+)(?:,|\])")
_SKIP_MARKER_RE = re.compile(r"\[(WIP|NO-PUSH)\]", re.IGNORECASE)

_AHEAD_THRESHOLD = 5  # >this → WARN instead of pushing


def _looks_like_commit(cmd: str) -> bool:
    if not _COMMIT_RE.search(cmd):
        return False
    if _AMEND_RE.search(cmd):
        return False
    return True


def _git(*args: str, timeout: int = 5) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)
    return result.returncode, result.stdout, result.stderr


def _ahead_count() -> int | None:
    """Return ahead count from `git status -sb`, or None when no upstream / error."""
    rc, out, _ = _git("status", "-sb")
    if rc != 0:
        return None
    first_line = out.splitlines()[0] if out else ""
    if "..." not in first_line:
        return None  # no upstream tracked
    m = _STATUS_AHEAD_RE.search(first_line)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _current_branch() -> str:
    """Return current branch name, or 'HEAD' if detached, or '' on error."""
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        return ""
    return out.strip()


def _last_commit_message() -> str:
    """Return the last commit's full message, or '' on error."""
    rc, out, _ = _git("log", "-1", "--pretty=%B")
    if rc != 0:
        return ""
    return out


def _resolve_push_context(cmd: str) -> tuple[str, int] | None:
    """Return (branch, ahead) when a push should be considered, else None.

    None covers the silent skips: not a push-worthy commit (Skip 1 amend via
    _looks_like_commit), detached HEAD (Skip 2), no upstream (Skip 3), or
    nothing to push (Skip 4).
    """
    if not cmd or not _looks_like_commit(cmd):
        return None
    branch = _current_branch()
    if not branch or branch == "HEAD":
        return None
    ahead = _ahead_count()
    if ahead is None or ahead == 0:
        return None
    return branch, ahead


def _held_by_marker_or_threshold(branch: str, ahead: int) -> bool:
    """Emit a WARN and return True when the push must be held.

    Skip 1 (WIP/NO-PUSH marker in the SUBJECT line only — scanning the full
    message would false-positive on commits documenting the marker syntax) or
    Skip 5 (accumulation beyond the threshold deserves Jay's eyeballs).
    """
    subject = (_last_commit_message().splitlines() or [""])[0]
    if _SKIP_MARKER_RE.search(subject):
        warn(format_warn(
            reason=f"commit on {branch} carries [WIP]/[NO-PUSH] marker; "
                   f"auto-push skipped ({ahead} commit(s) held local)",
            action="run `git push` manually when ready, or amend the commit "
                   "message to remove the marker.",
            reference="rules/Workflows.md > Fix = Deploy",
        ))
        return True
    if ahead > _AHEAD_THRESHOLD:
        warn(format_warn(
            reason=f"branch {branch} is {ahead} commit(s) ahead of upstream "
                   f"(threshold {_AHEAD_THRESHOLD}); auto-push withheld",
            action="review the pending commits with `git log @{u}..HEAD`, "
                   "then push manually if intended.",
            reference="rules/Workflows.md > Fix = Deploy",
        ))
        return True
    return False


def _do_push(branch: str, ahead: int) -> None:
    """Run `git push` and emit a single-line stderr summary of the outcome."""
    rc, _, err = _git("push", timeout=30)
    if rc == 0:
        warn(f"[auto-push] {branch}: {ahead} commit(s) pushed to upstream")
    else:
        warn(format_warn(
            reason=f"auto-push failed on {branch} (exit {rc})",
            action=f"check remote state; git stderr: {err.strip()[:200]}",
            reference="rules/Workflows.md > Fix = Deploy",
        ))


def main() -> None:
    _, data = read_hook_input()
    context = _resolve_push_context(get_command(data))
    if context is None:
        pass_through()

    branch, ahead = context
    if _held_by_marker_or_threshold(branch, ahead):
        sys.exit(0)

    _do_push(branch, ahead)
    sys.exit(0)


if __name__ == "__main__":
    main()
