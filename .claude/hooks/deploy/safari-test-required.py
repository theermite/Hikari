#!/usr/bin/env python3
"""Deploy hook: enforce Safari/cross-browser readiness before public deploy.

Trigger: PreToolUse Bash on deploy commands.

Checks:
1. `.browserslistrc` file exists in the repo root (cross-browser target
   declaration is mandatory per rules/Workflows.md).
2. The current assistant turn contains a Safari-test announce marker
   `[SAFARI-OK]` (free-form: e.g. `[SAFARI-OK] manual check on iOS 17`)
   or a `[SAFARI-SKIP]` marker with a reason.

If `.browserslistrc` is missing AND no skip marker → WARNING (one-shot
per session). Origin: Session 2026-05-06 — Kakusei and Shizen broken on
Safari mobile because of `color-mix()`, `crypto.randomUUID()`,
`AbortSignal.timeout()` without fallback.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    find_repo_root,
    format_warn,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402

STATE_NAME = "deploy-safari"


_PUBLIC_HINTS = re.compile(r"--prod\b|\b(?:production|live|public)\b", re.IGNORECASE)

_SAFARI_OK = re.compile(r"\[SAFARI-OK\]", re.IGNORECASE)
_SAFARI_SKIP = re.compile(r"\[SAFARI-SKIP\]", re.IGNORECASE)


def _has_browserslistrc(root: Path) -> bool:
    if (root / ".browserslistrc").exists():
        return True
    pkg = root / "package.json"
    if pkg.exists():
        try:
            txt = pkg.read_text(encoding="utf-8", errors="ignore")
            if '"browserslist"' in txt:
                return True
        except OSError:
            return False
    return False


def _has_safari_marker(transcript_path: str | None) -> tuple[bool, bool]:
    """Return (ok_marker, skip_marker) found in recent assistant text."""
    if not transcript_path:
        return False, False
    try:
        chunks = list(iter_assistant_text(transcript_path, limit=40))
    except Exception:
        return False, False
    blob = "\n".join(chunks)
    return bool(_SAFARI_OK.search(blob)), bool(_SAFARI_SKIP.search(blob))


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd or not looks_like_deploy(cmd):
        pass_through()
    if not _PUBLIC_HINTS.search(cmd):
        # Local/staging deploys don't trigger this check.
        pass_through()

    root = find_repo_root()
    has_blist = _has_browserslistrc(root)
    transcript_path = data.get("transcript_path") or ""
    ok, skip = _has_safari_marker(transcript_path)

    if has_blist and (ok or skip):
        pass_through()

    sid = data.get("session_id") or None
    if not mark_once(STATE_NAME, "warned", sid):
        pass_through()

    reasons: list[str] = []
    if not has_blist:
        reasons.append("no `.browserslistrc` (nor browserslist in package.json)")
    if not ok and not skip:
        reasons.append("no [SAFARI-OK] / [SAFARI-SKIP] marker in this session")

    warn(format_warn(
        reason="public deploy detected — " + " AND ".join(reasons),
        action="(1) add `.browserslistrc` with `defaults, iOS >= 15.4, "
               "Safari >= 15.4`; (2) before deploy, test on real Safari "
               "(iOS or macOS) and announce `[SAFARI-OK] <what you checked>`. "
               "Use `[SAFARI-SKIP] <reason>` only for backend-only deploys.",
        reference="rules/Workflows.md > Cross-Browser Compatibility",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
