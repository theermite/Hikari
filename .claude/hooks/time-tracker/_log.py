"""Shared JSONL logging utilities for the time-tracker hooks.

Storage layout (under <repo>/.claude/state/time-tracker/):

    estimations.jsonl   — append-only: {ts, session_id, hash, minutes, text}
    sessions.jsonl      — append-only: {session_id, started_at, ended_at,
                                        duration_min}
    seen-<session>.json — per-session dedup set for estimation hashes

All files are UTF-8 LF. Stdlib only (no external deps). Append is best-effort:
if the directory is unwritable, the helpers swallow OSError (the timing system
is observability, not a correctness gate — it must never break a session).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import find_repo_root  # noqa: E402

TIME_DIR_NAME = ".claude/state/time-tracker"


def time_dir(repo_root: Path | None = None) -> Path:
    """Return the time-tracker state dir, creating it if missing."""
    root = repo_root or find_repo_root()
    d = root / TIME_DIR_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def now_iso() -> str:
    """UTC ISO-8601 timestamp with seconds precision (e.g. 2026-05-18T10:23:45Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime | None:
    """Parse an ISO timestamp produced by `now_iso`. Return None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def append_jsonl(filename: str, entry: dict, repo_root: Path | None = None) -> bool:
    """Append a single JSON entry to `time-tracker/<filename>`. Returns True on success."""
    p = time_dir(repo_root) / filename
    try:
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def read_jsonl(filename: str, repo_root: Path | None = None) -> list[dict]:
    """Read all entries from `time-tracker/<filename>`. Missing file → []."""
    p = time_dir(repo_root) / filename
    if not p.exists():
        return []
    out: list[dict] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return []
    return out


def hash_snippet(text: str) -> str:
    """Stable 12-char hash for dedup of captured estimation snippets."""
    return hashlib.sha1(text.strip().encode("utf-8", "ignore")).hexdigest()[:12]


def to_minutes(value: float, unit: str) -> float:
    """Normalize a (value, unit) pair to minutes (float). Unknown unit → 0."""
    u = unit.lower().rstrip("s.")
    if u in ("s", "sec", "second", "seconde"):
        return value / 60.0
    if u in ("min", "minute"):
        return float(value)
    if u in ("h", "hr", "hour", "heure"):
        return value * 60.0
    if u in ("d", "day", "jour"):
        return value * 60.0 * 8.0  # 8h working day
    return 0.0
