"""session_state.py — concurrent writers to the same state file must not crash.

Why this file exists (2026-08-18, independent review on commits 67818d3 +
b6af44f). `write_state` derived its temp file name from the state name alone
(`p.with_suffix(".json.tmp")`) — identical for every process writing the same
state. Under the method's own 4-concurrent-subagent ceiling (Workflows.md),
several guards fire at once for the same session and race on that one temp
path. On Windows, `Path.replace()` then raises `PermissionError [WinError 32]`
because a sibling process already holds or has removed the file. The guard's
contract only knows exit 0 (pass) and 2 (block); an uncaught exception exits 1
and can let a write through unchecked.

Reproduced by the reviewer with 8 concurrent calls to the veille guard on one
session: `returncodes: [0, 1, 1, 1, 1, 1, 2, 1]`.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))

import session_state as st  # type: ignore  # noqa: E402


def test_concurrent_writers_to_same_state_do_not_raise(tmp_path):
    errors: list[BaseException] = []

    def writer(n: int) -> None:
        try:
            st.write_state("veille-skips", {"skip_count": n}, session_id="sessA", repo_root=tmp_path)
        except BaseException as exc:  # noqa: BLE001 — the crash itself is the defect
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"write_state raised under concurrency: {errors!r}"


def test_concurrent_writers_leave_one_valid_final_state(tmp_path):
    def writer(n: int) -> None:
        st.write_state("veille-skips", {"skip_count": n}, session_id="sessA", repo_root=tmp_path)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = st.read_state("veille-skips", session_id="sessA", repo_root=tmp_path)
    assert final != {}, "the state file must contain valid JSON from one of the writers"
    assert 0 <= final["skip_count"] < 16


def test_no_leftover_tmp_files_after_concurrent_writes(tmp_path):
    def writer(n: int) -> None:
        st.write_state("veille-skips", {"skip_count": n}, session_id="sessA", repo_root=tmp_path)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    leftovers = list((tmp_path / st.STATE_DIRNAME).glob("*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


# --- independent review 2026-08-19: the retry budget held at 16 concurrent ---
# writers (above) but not under SUSTAINED contention. The commit claimed the
# fix holds "quel que soit le nombre de sous-agents" — an overclaim: the
# original fixed-step exponential backoff let threads retry in lockstep,
# resynchronizing collisions instead of dispersing them. Reproduced by the
# reviewer at 64 threads x 5 writes each (320 total) with a real failure rate,
# verified here before the fix and expected to hold after it.


def test_sustained_concurrent_writers_do_not_exhaust_the_retry_budget(tmp_path):
    errors: list[BaseException] = []
    lock = threading.Lock()

    def writer(n: int) -> None:
        for i in range(5):
            try:
                st.write_state(
                    "veille-skips", {"skip_count": n, "i": i}, session_id="sessA", repo_root=tmp_path
                )
            except BaseException as exc:  # noqa: BLE001 — exhausting retries is the defect
                with lock:
                    errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(64)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"retry budget exhausted under sustained load: {errors[:3]!r} ({len(errors)} total)"


# --- independent review 2026-09-02: third failure of the same family. The ---
# randomized-backoff fix above flaked 3 times out of 5 runs on this exact
# test, under real (non-mocked) Windows contention rather than an injected
# fault — no fixed retry budget survives enough concurrent writers forever,
# only removing the collision does. Fixed by a real OS-level lock
# (`_file_lock`) instead of a third retry tuning. Run at higher and more
# sustained load than the flake needed (96 threads x 8 writes = 768 total,
# vs. 320 above) to demonstrate the fix holds by a margin, not by luck.


def test_locked_writers_hold_under_load_that_flaked_the_retry_based_fix(tmp_path):
    errors: list[BaseException] = []
    lock = threading.Lock()

    def writer(n: int) -> None:
        for i in range(8):
            try:
                st.write_state(
                    "veille-skips", {"skip_count": n, "i": i}, session_id="sessB", repo_root=tmp_path
                )
            except BaseException as exc:  # noqa: BLE001 — any exception is the defect
                with lock:
                    errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(96)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"lock-based write_state still failed under load: {errors[:3]!r} ({len(errors)} total)"

    leftovers = list((tmp_path / st.STATE_DIRNAME).glob("*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


# --- independent review 2026-09-02, second pass: the lock itself had no ---
# ceiling — a holder frozen inside its `with` block left every other writer
# waiting forever, silently. Prove the timeout fires instead of hanging.


def test_frozen_lock_holder_times_out_instead_of_hanging_forever(tmp_path):
    lock_path = tmp_path / "frozen.lock"
    release = threading.Event()
    holder_acquired = threading.Event()

    def hold_forever() -> None:
        with st._file_lock(lock_path):
            holder_acquired.set()
            release.wait(timeout=5)  # released by the test after the assertion

    holder = threading.Thread(target=hold_forever)
    holder.start()
    assert holder_acquired.wait(timeout=2), "holder never acquired the lock"

    start = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            with st._file_lock(lock_path, timeout=0.2):
                pass
    finally:
        elapsed = time.monotonic() - start
        release.set()
        holder.join(timeout=5)

    assert elapsed < 2.0, f"timeout took {elapsed:.2f}s — not bounded as expected"


def test_mark_once_under_concurrency_never_loses_a_key(tmp_path):
    """The read-then-write in `mark_once` used to be two unlocked steps: two
    concurrent callers could both read `key` as new and each write a state
    missing the other's key — a lost update. Every one of 64 distinct keys,
    marked concurrently, must survive.
    """
    results: list[bool] = []
    lock = threading.Lock()

    def marker(n: int) -> None:
        r = st.mark_once("veille-skips", f"key-{n}", session_id="sessC", repo_root=tmp_path)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=marker, args=(n,)) for n in range(64)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(results), "every first-time key must return True"

    final = st.read_state("veille-skips", session_id="sessC", repo_root=tmp_path)
    assert set(final.get("seen", [])) == {f"key-{n}" for n in range(64)}, "a concurrent lost update dropped a key"
