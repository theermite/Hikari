"""session_state.py — state files stay inside .claude/state/.

`session_id` arrives from hook stdin and becomes part of a filename. An
independent cross-model review (2026-07-29) reproduced a real file write OUTSIDE
the state directory by sending `session_id="../../../../pwned-poc"` to
simple-language-check.py. These tests pin the fix: a traversing or otherwise
malformed id degrades to "no per-session suffix", never to a path outside.

Well-formed ids must keep working — the per-session isolation is the whole point
of the suffix, so the fix is worthless if it silently collapses every session
onto one shared file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))

import session_state as st  # type: ignore  # noqa: E402


TRAVERSING_IDS = [
    "../../../../pwned-poc",
    "..",
    "../sibling",
    "a/b",
    "a\\b",
    "/absolute",
    "C:/windows/temp/x",
    "with space",
    "semi;colon",
    "null\x00byte",
    "x" * 129,  # over the length ceiling
    "",
]

WELLFORMED_IDS = [
    "a06c3bf2-9f99-4a27-a449-054389c7ae2e",
    "a57c9581dd38b0f5b",
    "session_42",
    "A-b_9",
]


@pytest.mark.parametrize("bad", TRAVERSING_IDS)
def test_malformed_session_id_is_rejected(bad):
    assert st.safe_session_id(bad) is None, f"{bad!r} must not shape a filename"


@pytest.mark.parametrize("good", WELLFORMED_IDS)
def test_wellformed_session_id_is_kept(good):
    assert st.safe_session_id(good) == good


@pytest.mark.parametrize("bad", TRAVERSING_IDS)
def test_state_path_never_escapes_state_dir(tmp_path, bad):
    p = st.state_path("marker", session_id=bad, repo_root=tmp_path)
    expected_dir = (tmp_path / st.STATE_DIRNAME).resolve()
    assert p.parent == expected_dir, f"{bad!r} escaped to {p}"
    assert p.name == "marker.json", "a rejected id must fall back to the shared file"


@pytest.mark.parametrize("good", WELLFORMED_IDS)
def test_state_path_keeps_per_session_isolation(tmp_path, good):
    p = st.state_path("marker", session_id=good, repo_root=tmp_path)
    assert p.name == f"marker-{good}.json"


def test_write_state_with_traversing_id_writes_inside_only(tmp_path):
    # End-to-end: the write must land in .claude/state/, and nothing may appear
    # at the traversal target (repo root here).
    st.write_state("marker", {"seen": ["x"]}, session_id="../../../../pwned-poc", repo_root=tmp_path)
    inside = (tmp_path / st.STATE_DIRNAME / "marker.json")
    assert inside.exists(), "the state write must still happen, just confined"
    escaped = list(tmp_path.glob("pwned-poc*")) + list(tmp_path.glob("*/pwned-poc*"))
    assert escaped == [], f"file(s) written outside the state dir: {escaped}"


def test_read_write_roundtrip_unaffected(tmp_path):
    st.write_state("counter", {"n": 3}, session_id="sess1", repo_root=tmp_path)
    assert st.read_state("counter", session_id="sess1", repo_root=tmp_path) == {"n": 3}
    # A different session must not see it (isolation still real).
    assert st.read_state("counter", session_id="sess2", repo_root=tmp_path) == {}


def test_mark_once_still_fires_exactly_once(tmp_path):
    assert st.mark_once("gate", "k", session_id="sess1", repo_root=tmp_path) is True
    assert st.mark_once("gate", "k", session_id="sess1", repo_root=tmp_path) is False
