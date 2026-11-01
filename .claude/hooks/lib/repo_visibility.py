"""Is this repository KNOWN to be private? (2026-10-30)

Used by guards/end-user-data-guard.py: a note or a commit message in a private repo may name the people of Jay's life
(his decision), while a public repo never carries a user's data. The default stays STRICT: a repository counts as
private only when GitHub says so — directly (`gh api`) or through the cached answer. No GitHub remote, no answer,
a corrupt or ancient cache: False, so the guard behaves exactly as before.

Cache: `<store>/repo-visibility.json` (the guard's own store, outside every repository), one entry per `owner/name`:
{"private": bool, "at": epoch}. Fresh for an hour (a repo made public is seen within the hour); when GitHub does not
answer, an answer up to 30 days old is still trusted — a private repo does not turn public by itself.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from end_user_identifiers import store_dir  # noqa: E402

CACHE_NAME = "repo-visibility.json"
FRESH_SECONDS = 3600
STALE_OK_SECONDS = 7 * 86400
ASK_TIMEOUT = 8
_URL = re.compile(
    r"^(?:https?://(?:[^@/\s]+@)?|ssh://(?:[^@/\s]+@)?|git@)github\.com[:/]+(?P<slug>[\w.-]+/[\w.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def slug_from_url(url: str) -> str | None:
    """`owner/name` of a GitHub remote URL (https, ssh, scp-like, with credentials or `.git`), else None."""
    found = _URL.match((url or "").strip())
    return found.group("slug") if found else None


def _git_output(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _ask_github(slug: str) -> bool | None:
    """True / False when GitHub answers `private`; None for anything else (no `gh`, offline, no right, odd output)."""
    command = os.environ.get("EUI_GH_CMD", "gh")
    try:
        r = subprocess.run([command, "api", f"repos/{slug}", "--jq", ".private"], capture_output=True, text=True,
                           timeout=ASK_TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return {"true": True, "false": False}.get(r.stdout.strip().lower()) if r.returncode == 0 else None


def _read_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}   # no cache yet, or an unreadable one: nothing is known
    return data if isinstance(data, dict) else {}


def _valid_entry(entry: object) -> bool:
    return (isinstance(entry, dict) and isinstance(entry.get("private"), bool)
            and isinstance(entry.get("at"), (int, float)) and not isinstance(entry.get("at"), bool))


def _remember(path: Path, cache: dict, slug: str, answer: bool, now: float) -> None:
    cache[slug] = {"private": answer, "at": now}
    try:
        path.write_text(json.dumps(cache), encoding="utf-8")
    except OSError as err:
        print(f"[DEBUG][repo_visibility] cache not written: {err}", file=sys.stderr)


def _remote_urls(repo: str) -> list[str]:
    """Every fetch and push address of every remote: a repo is as public as its most public address."""
    urls: list[str] = []
    for name in _git_output(repo, "remote").split():
        urls += _git_output(repo, "remote", "get-url", "--all", name).splitlines()
        urls += _git_output(repo, "remote", "get-url", "--push", "--all", name).splitlines()
    return [url.strip() for url in urls if url.strip()]


def is_private(repo: str) -> bool:
    """True only when EVERY remote address of `repo` is a GitHub repository KNOWN to be private (no remote: False)."""
    slugs = [slug_from_url(url) for url in _remote_urls(repo)]
    return bool(slugs) and all(slugs) and all(_slug_is_private(slug) for slug in dict.fromkeys(slugs))


def _slug_is_private(slug: str) -> bool:
    path, now = store_dir() / CACHE_NAME, time.time()
    cache = _read_cache(path)
    entry = cache.get(slug) if _valid_entry(cache.get(slug)) else None
    age = now - entry["at"] if entry else None
    if entry and 0 <= age <= FRESH_SECONDS:
        return entry["private"]
    answer = _ask_github(slug)
    if answer is not None:
        _remember(path, cache, slug, answer, now)
        return answer
    return bool(entry and 0 <= age <= STALE_OK_SECONDS and entry["private"])
