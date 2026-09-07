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
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

from common import find_repo_root  # type: ignore  # lib/ added to sys.path by hook


STATE_DIRNAME = ".claude/state"

# Independent review, 2026-09-02: the first version of this lock (below) had
# no ceiling — a holder frozen inside its `with` block (a deadlock elsewhere,
# a hung process) left every other writer waiting forever, silently. The
# mechanism it replaced at least failed loudly after ~10s. A lock is only an
# improvement if trading a collision for a *bounded, observable* wait; an
# unbounded one is a worse failure mode, not a better one.
_LOCK_TIMEOUT_S = 10.0


if sys.platform == "win32":
    import msvcrt

    @contextlib.contextmanager
    def _file_lock(lock_path: Path, timeout: float = _LOCK_TIMEOUT_S) -> Iterator[None]:
        """Hold an OS-level advisory lock on `lock_path` for the block's duration.

        Uses `LK_NBLCK` (non-blocking, single attempt) in a tight poll loop
        instead of `LK_LOCK` — `LK_LOCK` retries internally on its own 1-second
        cadence (up to 10s before raising), which serializes many short writes
        at roughly one per second under contention. A short sleep between
        non-blocking attempts holds the same correctness (still a real,
        exclusive OS lock — no collision window) without that floor.

        Raises `TimeoutError` past `timeout` instead of waiting forever.
        """
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+b") as fh:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"could not acquire lock on {lock_path} within {timeout}s") from None
                    time.sleep(0.001)
            try:
                yield
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    @contextlib.contextmanager
    def _file_lock(lock_path: Path, timeout: float = _LOCK_TIMEOUT_S) -> Iterator[None]:
        """Hold a real advisory lock (`flock`) on `lock_path` for the block's duration.

        Uses `LOCK_NB` (non-blocking, single attempt) in a tight poll loop —
        plain blocking `flock` has no ceiling, so a frozen holder would wedge
        every other writer forever. Raises `TimeoutError` past `timeout`.
        """
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+b") as fh:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"could not acquire lock on {lock_path} within {timeout}s") from None
                    time.sleep(0.001)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

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


def _read_state_at(p: Path) -> dict[str, Any]:
    """Read state JSON from an already-resolved path, {} if missing or malformed."""
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _write_state_at(p: Path, data: dict[str, Any]) -> None:
    """Write state JSON atomically (write to tmp then replace) to an already-
    resolved path. Caller must hold `_file_lock` on `p`'s lock file first.
    """
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(payload + "\n", encoding="utf-8", newline="\n")
    _replace_with_retry(tmp, p)


def read_state(name: str, session_id: str | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    """Read state JSON, return {} if missing or malformed.

    Le lecteur ne prend PAS le verrou. Essaye le 2026-09-06 : lui faire prendre
    le meme verrou exclusif transforme la collision en FAMINE — les ecrivains
    n'obtenaient plus le verrou en 10 s sous charge. Echanger une panne bornee
    contre une attente non bornee est une regression deguisee (lecon 2026-09-02).
    La fermeture de la fenetre se fait cote ecrivain, voir `_replace_with_retry`.
    """
    return _read_state_at(state_path(name, session_id, repo_root))


def write_state(name: str, data: dict[str, Any], session_id: str | None = None, repo_root: Path | None = None) -> None:
    """Write state JSON atomically (write to tmp then replace) with UTF-8 LF.

    Third failure of the same family (independent review 2026-08-18, then
    2026-08-19, then 2026-09-02): concurrent writers colliding on Windows'
    rename-into-target step. The first two fixes each made the RETRY survive
    harder contention (unique temp names, then randomized backoff), and each
    was eventually outrun by more concurrent writers. Per Independent-Review.md,
    a family that survives two corrections gets a structurally different
    approach, not a third retry tuning: writers now hold a real OS-level lock
    (`_file_lock`) for the whole write, so there is no collision left to retry
    — only one writer ever touches `tmp`/`replace()` at a time.
    """
    p = state_path(name, session_id, repo_root)
    lock_path = p.with_name(f"{p.name}.lock")
    with _file_lock(lock_path):
        _write_state_at(p, data)


def _replace_with_retry(tmp: Path, target: Path, attempts: int = 5) -> None:
    """`tmp.replace(target)`, retrying on a transient PermissionError.

    `write_state` now holds `_file_lock` for the whole call, so no other writer
    from this codebase can be touching `target` concurrently — the collision
    this used to defend against cannot happen anymore. The remaining, much
    rarer cause is external (an antivirus or search indexer briefly opening
    the file); a handful of short retries covers that without needing jitter
    tuned for high contention, because there is no contention left to spread out.
    """
    for attempt in range(attempts):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                break
            time.sleep(0.01 * (attempt + 1))

    # QUATRIEME occurrence de la famille (2026-08-18, 08-19, 09-02, puis quatre
    # fois le 2026-09-06 dont deux pendant la propagation). Les trois premiers
    # correctifs ont rendu le RENOMMAGE plus resistant ; chacun a fini depasse.
    #
    # La cause restante n'est pas la contention entre ecrivains — le verrou l'a
    # supprimee. C'est qu'un LECTEUR, qui ne prend aucun verrou, tient le fichier
    # ouvert une fraction de seconde : sur Windows, on ne renomme pas par-dessus
    # un fichier ouvert, quel que soit le nombre de reessais.
    #
    # Faire prendre le verrou aux lecteurs a ete essaye et MESURE : cela cree une
    # famine, les ecrivains n'obtenant plus le verrou en 10 s. On echangeait une
    # panne bornee contre une attente non bornee.
    #
    # Le repli n'est donc pas un quatrieme reglage de reessai : c'est un MECANISME
    # DIFFERENT. On ecrit le contenu EN PLACE, toujours sous le verrou d'ecriture.
    # Un lecteur peut alors voir un fichier a moitie ecrit — deja traite comme
    # vide par `_read_state_at`, degradation connue et benigne, la ou l'echec
    # faisait tomber un garde-fou entier.
    try:
        contenu = tmp.read_bytes()
        with open(target, "wb") as sortie:
            sortie.write(contenu)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def mark_once(name: str, key: str, session_id: str | None = None, repo_root: Path | None = None) -> bool:
    """Return True the first time `key` is seen for `name` (and remember it).

    Subsequent calls with the same key return False. Used to throttle one-shot
    hook actions (e.g. "fire context-warning at 60% only once per session").

    Read-then-write is one locked step, not two: two concurrent callers each
    reading before either writes would both see `key` as new and each write a
    state missing the other's addition — a lost update, distinct from (but in
    the same family as) the collision `write_state` alone used to hit.
    """
    p = state_path(name, session_id, repo_root)
    lock_path = p.with_name(f"{p.name}.lock")
    with _file_lock(lock_path):
        data = _read_state_at(p)
        seen = set(data.get("seen", []))
        if key in seen:
            return False
        seen.add(key)
        data["seen"] = sorted(seen)
        _write_state_at(p, data)
        return True
