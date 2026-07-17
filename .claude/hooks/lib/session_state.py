"""Per-session JSON state for hooks (one-shot markers, throttles, counters).

Hooks are stateless processes — they re-spawn at every tool call. When a hook
needs "remember-once-per-session" behavior (e.g. mandatory-read gate checked
once, context-awareness warning fired once per threshold), it persists a tiny
JSON file under `<repo>/.claude/state/`.

State files are tied to `session_id` from the hook input when available.
The directory is created on demand. Files are LF-encoded UTF-8. Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import find_repo_root  # type: ignore  # lib/ added to sys.path by hook


STATE_DIRNAME = ".claude/state"


def state_dir(repo_root: Path | None = None) -> Path:
    """Return the state directory, creating it if missing."""
    root = repo_root or find_repo_root()
    d = root / STATE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(name: str, session_id: str | None = None, repo_root: Path | None = None) -> Path:
    """Return the state file path for `name` (per-session if session_id given)."""
    d = state_dir(repo_root)
    suffix = f"-{session_id}" if session_id else ""
    return d / f"{name}{suffix}.json"


def read_state(name: str, session_id: str | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    """Read state JSON, return {} if missing or malformed."""
    p = state_path(name, session_id, repo_root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def write_state(name: str, data: dict[str, Any], session_id: str | None = None, repo_root: Path | None = None) -> None:
    """Write state JSON atomically (write to tmp then replace) with UTF-8 LF."""
    p = state_path(name, session_id, repo_root)
    tmp = p.with_suffix(".json.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(payload + "\n", encoding="utf-8", newline="\n")
    tmp.replace(p)


def mark_once(name: str, key: str, session_id: str | None = None, repo_root: Path | None = None) -> bool:
    """Return True the first time `key` is seen for `name` (and remember it).

    Subsequent calls with the same key return False. Used to throttle one-shot
    hook actions (e.g. "fire context-warning at 60% only once per session").
    """
    data = read_state(name, session_id, repo_root)
    seen = set(data.get("seen", []))
    if key in seen:
        return False
    seen.add(key)
    data["seen"] = sorted(seen)
    write_state(name, data, session_id, repo_root)
    return True
