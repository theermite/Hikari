#!/usr/bin/env python3
"""Deploy hook: require axe-core a11y check before public deploy.

Trigger: PreToolUse Bash on deploy commands with `--prod / production /
live / public` hints.

The methodology mandates zero axe violations at AA before any public
deploy. Verifying this exhaustively in a hook would require running
axe-core itself (heavy, external). Instead, this hook enforces an
ANNOUNCE protocol: the assistant must have output one of these markers
in the current session before deploying:

  [AXE-OK] passed 0 violations on <route or build>
  [AXE-SKIP] motif: <reason>  # e.g., "API-only deploy, no UI"

If neither marker is present → WARNING (one-shot per session).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_warn,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402

STATE_NAME = "deploy-axe"

_PUBLIC_HINTS = re.compile(r"--prod\b|\b(?:production|live|public)\b", re.IGNORECASE)

_AXE_OK = re.compile(r"\[AXE-OK\]", re.IGNORECASE)
_AXE_SKIP = re.compile(r"\[AXE-SKIP\]", re.IGNORECASE)


def _scan_markers(transcript_path: str) -> tuple[bool, bool]:
    if not transcript_path:
        return False, False
    try:
        chunks = list(iter_assistant_text(transcript_path, limit=60))
    except Exception:
        return False, False
    blob = "\n".join(chunks)
    return bool(_AXE_OK.search(blob)), bool(_AXE_SKIP.search(blob))


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd or not looks_like_deploy(cmd):
        pass_through()
    if not _PUBLIC_HINTS.search(cmd):
        pass_through()

    ok, skip = _scan_markers(data.get("transcript_path") or "")
    if ok or skip:
        pass_through()

    sid = data.get("session_id") or None
    if not mark_once(STATE_NAME, "warned", sid):
        pass_through()

    warn(format_warn(
        reason="public deploy detected but no [AXE-OK] / [AXE-SKIP] marker "
               "found in this session",
        action="run axe-core against the build (e.g., `npx @axe-core/cli "
               "https://staging.example.com` or in-test via @axe-core/playwright). "
               "Then announce `[AXE-OK] 0 violations on <route>`. Use "
               "`[AXE-SKIP] motif: <reason>` for backend-only or non-UI deploys.",
        reference="rules/Quality.md > Accessibility (BLOCKING) — 0 axe violations",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
