#!/usr/bin/env python3
"""Deploy hook: scan CSS for a11y essentials before public deploy.

Trigger: PreToolUse Bash on deploy commands with public hints.

Static, low-cost checks performed on repo CSS files (not exhaustive —
axe-violations.py is the heavy check). This hook covers:

1. `prefers-reduced-motion` rule is present somewhere in the CSS.
2. At least one touch-target sized rule (min-width/height >= 44px) on
   buttons/links — heuristic, signals mobile a11y consideration.

Both checks are non-blocking WARNs (one-shot per session). Skips when
the repo has no CSS files.
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

STATE_NAME = "deploy-a11y"

_PUBLIC_HINTS = re.compile(r"--prod\b|\b(?:production|live|public)\b", re.IGNORECASE)

_REDUCED_MOTION = re.compile(r"@media\s*\([^)]*prefers-reduced-motion", re.IGNORECASE)
# Touch target: min-(width|height) with value >= 44px (or 2.75rem)
_TOUCH_TARGET = re.compile(
    r"min-(?:width|height)\s*:\s*(?:4[4-9]|[5-9]\d|\d{3,})px|"
    r"min-(?:width|height)\s*:\s*(?:2\.[7-9]\d?|[3-9])rem",
    re.IGNORECASE,
)

# Limits to keep the scan cheap.
_MAX_CSS_FILES = 50
_MAX_BYTES_PER_FILE = 200_000


def _collect_css_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for pattern in ("**/*.css", "**/*.scss"):
        for p in root.glob(pattern):
            # Skip vendored / build output
            parts = {part.lower() for part in p.parts}
            if {"node_modules", "dist", "build", ".next", ".turbo"} & parts:
                continue
            out.append(p)
            if len(out) >= _MAX_CSS_FILES:
                return out
    return out


def _scan(files: list[Path]) -> tuple[bool, bool, bool]:
    """Return (any_css, reduced_motion_seen, touch_target_seen)."""
    has_css = bool(files)
    rm = False
    tt = False
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")[:_MAX_BYTES_PER_FILE]
        except OSError:
            continue
        if not rm and _REDUCED_MOTION.search(txt):
            rm = True
        if not tt and _TOUCH_TARGET.search(txt):
            tt = True
        if rm and tt:
            break
    return has_css, rm, tt


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd or not looks_like_deploy(cmd):
        pass_through()
    if not _PUBLIC_HINTS.search(cmd):
        pass_through()

    root = find_repo_root()
    files = _collect_css_files(root)
    has_css, rm, tt = _scan(files)
    if not has_css:
        # API-only or non-UI project — not applicable.
        pass_through()

    issues: list[str] = []
    if not rm:
        issues.append("no `@media (prefers-reduced-motion)` rule found")
    if not tt:
        issues.append("no touch-target rule (min-width/height >= 44px) found")

    if not issues:
        pass_through()

    sid = data.get("session_id") or None
    if not mark_once(STATE_NAME, "warned", sid):
        pass_through()

    warn(format_warn(
        reason="public deploy detected — a11y CSS scan flagged: "
               + " | ".join(issues),
        action="add a `@media (prefers-reduced-motion: reduce) { ... }` block "
               "that disables animations; set `min-width: 44px; min-height: 44px` "
               "on interactive elements (buttons, links). These are WCAG 2.2 AA "
               "minimums for mobile accessibility.",
        reference="rules/Quality.md > Accessibility (BLOCKING) + ND-Friendly UX",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
