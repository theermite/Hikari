#!/usr/bin/env python3
"""Deploy hook: warn if deploy proceeds without nginx maintenance pages.

Trigger: PreToolUse Bash on commands that look like deploy.

For each repo containing an nginx config (or referencing nginx in
docker-compose), the methodology requires custom 502/503/504 pages
with branded content (rules/Workflows.md > Nginx Maintenance Pages).

This hook scans the repo for either:
- A directory `maintenance/` (or `nginx/maintenance/`) with 502/503/504 HTML
- An nginx config snippet referencing `error_page 502` AND a static file path

If neither is found and the project has nginx markers, warn with recovery.
Once per session (mark_once).
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

STATE_NAME = "deploy-maintenance"


def _has_nginx_marker(root: Path) -> bool:
    for candidate in ("nginx.conf", "nginx", "deploy/nginx"):
        if (root / candidate).exists():
            return True
    compose = root / "docker-compose.yml"
    if compose.exists():
        try:
            txt = compose.read_text(encoding="utf-8", errors="ignore")
            if "nginx" in txt.lower():
                return True
        except OSError:
            return False
    return False


def _has_maintenance_pages(root: Path) -> bool:
    candidates = [
        root / "maintenance",
        root / "nginx" / "maintenance",
        root / "deploy" / "maintenance",
        root / "public" / "maintenance",
    ]
    for d in candidates:
        if d.is_dir():
            files = {p.name for p in d.iterdir() if p.is_file()}
            if {"502.html", "503.html", "504.html"} & files:
                return True
    # Or: nginx config referencing error_page 502/503/504 + a real path
    for cfg_name in ("nginx.conf", "nginx/default.conf", "deploy/nginx.conf"):
        cfg = root / cfg_name
        if cfg.exists():
            try:
                txt = cfg.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"error_page\s+50[234]", txt):
                    return True
            except OSError:
                continue
    return False


def main() -> None:
    _, data = read_hook_input()
    cmd = get_command(data)
    if not cmd or not looks_like_deploy(cmd):
        pass_through()

    root = find_repo_root()
    if not _has_nginx_marker(root):
        # No nginx in this project — not applicable.
        pass_through()
    if _has_maintenance_pages(root):
        pass_through()

    sid = data.get("session_id") or None
    if not mark_once(STATE_NAME, "warned", sid):
        pass_through()

    warn(format_warn(
        reason="deploy detected but no nginx maintenance pages "
               "(502/503/504) found in this repo",
        action="add static 502.html / 503.html / 504.html under "
               "`maintenance/` (or `nginx/maintenance/`) with branded "
               "Shinkofa content (Dignity-compliant: factual, no 'Oops!', "
               "no guilt-trip). Reference them in nginx config via "
               "`error_page 502 /502.html;` blocks.",
        reference="rules/Workflows.md > Nginx Maintenance Pages",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
