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


# --- 2026-09-06: SECOND failure of the same family, so the approach changes ---
# The two previous fixes both tuned a RETRY BUDGET: fixed exponential backoff
# (2026-08-18), then randomized jitter (2026-08-19). Each closed the reported
# load level and reopened the family at the next one — the test above failed
# again inside the full 756-test suite (1 PermissionError out of 320 writes),
# where real disk contention widens the collision window. A budget can always
# be exhausted; that is what a budget IS.
#
# So the mechanism changes from "collide, then retry" to "never collide": the
# rename-into-target step is now serialized. The test below states that
# PROPERTY instead of the absence of a symptom — a symptom test can only ever
# be flaky, and a flaky test cannot prove a fix.


def test_only_one_writer_at_a_time_reaches_the_rename(tmp_path, monkeypatch):
    real_replace = st._replace_with_retry
    inside = 0
    peak = 0
    counter = threading.Lock()

    def observed(tmp: Path, target: Path, *args, **kwargs):
        nonlocal inside, peak
        with counter:
            inside += 1
            peak = max(peak, inside)
        try:
            # Widen the window an unsynchronized writer would need to overlap.
            time.sleep(0.002)
            return real_replace(tmp, target, *args, **kwargs)
        finally:
            with counter:
                inside -= 1

    monkeypatch.setattr(st, "_replace_with_retry", observed)

    def writer(n: int) -> None:
        st.write_state("veille-skips", {"skip_count": n}, session_id="sessA", repo_root=tmp_path)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(32)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak == 1, f"{peak} writers were inside the rename at once — the step is not serialized"
