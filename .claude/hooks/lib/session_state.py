"""Per-session JSON state for hooks (one-shot markers, throttles, counters).

Hooks are stateless processes — they re-spawn at every tool call. When a hook
needs "remember-once-per-session" behavior (e.g. mandatory-read gate checked
once, context-awareness warning fired once per threshold), it persists a tiny
JSON file under `<repo>/.claude/state/`.

State files are tied to `session_id` from the hook input when available.
The directory is created on demand. Files are LF-encoded UTF-8. Stdlib only.
"""

from __future__ import annotations

import contextlib
import json
import os
import random
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from common import find_repo_root  # type: ignore  # lib/ added to sys.path by hook


STATE_DIRNAME = ".claude/state"

# session_id arrives from hook stdin and becomes part of a FILE NAME. Kept to a
# tight allow-list so a value like "../../../x" can never write outside the
# state directory (cross-model review 2026-07-29 reproduced that write).
SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def safe_session_id(session_id: str | None) -> str | None:
    """Return session_id when it is a safe filename fragment, else None.

    None means "no per-session suffix" — the same shared-file behaviour hooks
    already use when the harness sends no session_id at all.
    """
    if not session_id or not isinstance(session_id, str):
        return None
    return session_id if SAFE_SESSION_ID.match(session_id) else None


def state_dir(repo_root: Path | None = None) -> Path:
    """Return the state directory, creating it if missing."""
    root = repo_root or find_repo_root()
    d = root / STATE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _strip_extended_prefix(path_str: str) -> str:
    r"""Drop Windows' `\\?\` extended-length marker so two resolutions of the
    same directory compare equal whether or not either carries it.

    `Path.resolve()` calls `_getfinalpathname` on Windows when the target
    exists, which prepends `\\?\` — but only when the OS call actually
    resolves an existing path at that instant. Under concurrent access to a
    freshly-created directory, one caller's resolve() can win that race and
    another's can lose it, so `p.resolve()` and `d.resolve()` come back with
    mismatched prefixes for the SAME directory (independent review,
    2026-08-19: `state_path` raised a false 'escapes' error under concurrent
    write_state() traffic — not a real escape, a comparison artifact).
    """
    if path_str.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path_str[8:]
    if path_str.startswith("\\\\?\\"):
        return path_str[4:]
    return path_str


def state_path(name: str, session_id: str | None = None, repo_root: Path | None = None) -> Path:
    """Return the state file path for `name` (per-session if session_id given).

    `name` is hook-authored (never user input) ; `session_id` comes from stdin
    and is therefore validated before it can shape a filename.
    """
    d = state_dir(repo_root)
    sid = safe_session_id(session_id)
    suffix = f"-{sid}" if sid else ""
    p = (d / f"{name}{suffix}.json").resolve()
    # Defense in depth: whatever `name` and `sid` contain, the result stays in
    # d. Compared as normalized strings, not Path.parents — see
    # _strip_extended_prefix for why a plain resolve()-vs-resolve() compare
    # is not safe here.
    d_norm = os.path.normcase(_strip_extended_prefix(str(d.resolve())))
    p_norm = os.path.normcase(_strip_extended_prefix(str(p)))
    if not p_norm.startswith(d_norm + os.sep):
        raise ValueError(f"state path escapes {STATE_DIRNAME}: {p}")
    return p


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
    """Write state JSON atomically (write to tmp then replace) with UTF-8 LF.

    The temp name carries the writer's own pid + a random suffix — several
    guards racing on the same state file (the method allows up to 4 concurrent
    sub-agents, each spawning its own guard processes) must never target the
    same temp path, or `replace()` collides on Windows (independent review,
    2026-08-18: `PermissionError [WinError 32]`, reproduced with 8 concurrent
    writers).
    """
    p = state_path(name, session_id, repo_root)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(payload + "\n", encoding="utf-8", newline="\n")
    with _exclusive(p):
        _replace_with_retry(tmp, p)


# One lock object per target path, shared by every thread of this process.
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(target: Path) -> threading.Lock:
    key = os.path.normcase(str(target))
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[key] = lock
        return lock


def _open_sidecar(target: Path) -> int | None:
    """Open `<target>.lock`, or None when the filesystem refuses it.

    None is not a failure: the thread lock still holds inside this process,
    and `_replace_with_retry` stays as the net across processes.
    """
    try:
        return os.open(str(target.with_name(target.name + ".lock")), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        return None


# Why a lock and not a longer retry budget (2026-09-06): the two previous fixes
# both tuned a budget — fixed exponential backoff (2026-08-18), then randomized
# jitter (2026-08-19) — and each reopened the same family one load level later.
# The full 756-test suite still produced one `PermissionError` out of 320
# concurrent writes. A budget can always be exhausted; that is what a budget IS.
# Writers now queue instead of colliding, so there is no budget left to exhaust.
#
# Two layers, because the collisions come from two places:
#   - threads of one hook process → `threading.Lock` (a Windows byte-range lock
#     does NOT exclude two handles owned by the same process) ;
#   - separate guard processes, up to the method's 4-subagent ceiling → an OS
#     lock on a sidecar `.lock` file. The OS drops it when the process dies, so
#     a crashed guard can never leave a lock behind — the reason this is not a
#     hand-rolled lock file with a stale-entry problem.
@contextlib.contextmanager
def _exclusive(target: Path):
    """Serialize the rename-into-`target` step across threads AND processes."""
    with _thread_lock_for(target):
        fd = _open_sidecar(target)
        try:
            if fd is not None:
                _lock_fd(fd)
            yield
        finally:
            if fd is not None:
                _unlock_fd(fd)
                os.close(fd)


if os.name == "nt":
    import msvcrt

    def _lock_fd(fd: int) -> None:
        # LK_LOCK blocks, retrying for ~10 s before raising. Locking one byte
        # past EOF is legal on Windows and never touches the file's content.
        with contextlib.suppress(OSError):
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

    def _unlock_fd(fd: int) -> None:
        with contextlib.suppress(OSError):
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_fd(fd: int) -> None:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_fd(fd: int) -> None:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)


def _replace_with_retry(tmp: Path, target: Path, attempts: int = 30) -> None:
    """`tmp.replace(target)`, retrying on a transient Windows PermissionError.

    Two writers can each hold a distinct, uniquely-named tmp file and still
    collide on the shared rename-into-`target` step — Windows briefly denies
    access to a destination another thread/process is mid-replace on. Each
    writer holds a distinct final state (it wrote its own tmp), so losing a
    race and retrying is safe: the last writer to succeed wins, same as an
    uncontended write.

    The backoff is RANDOMIZED, not fixed-step exponential: a deterministic
    delay lets every retrying thread wake up at the same instant and collide
    again, which is exactly what let sustained contention exhaust a 5-attempt
    fixed-backoff budget (independent review, 2026-08-19 — 64 threads x 5
    writes each still failed after the first fix). Jitter spreads retries out
    in time instead of resynchronizing them.
    """
    ceiling = 0.005
    for attempt in range(attempts):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(random.uniform(0, ceiling))
            ceiling = min(ceiling * 1.5, 0.08)


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
