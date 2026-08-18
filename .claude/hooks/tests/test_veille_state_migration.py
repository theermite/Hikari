"""A state file written before the digest change must not cost a false block.

On 2026-08-18 the marker fingerprint changed algorithm (Security.md refuses
weak hashes). The skip counter uses that fingerprint to count a given marker
exactly ONCE per session: `last_marker_hash != marker_hash` means "new marker,
increment".

After the change that comparison is true for a STRICTLY IDENTICAL marker —
only the algorithm moved. Any session live at deployment saw its counter jump
one step for nothing, and a session already at 2 skips was blocked on the spot.
An independent review reproduced it (verdict FAIL, 2026-08-18).

The rule enforced here: a state with no `digest_algo` field is a pre-migration
state. Its stored fingerprint is not comparable, so the first marker seen after
the migration never increments the counter. One uncounted skip at the boundary
is cheap; a false block mid-session is not.

The tests seed a fingerprint of the OLD shape without computing a weak hash —
its value is irrelevant, only the missing `digest_algo` marks the state legacy.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
HOOK = HOOKS_DIR / "guards" / "pre-code-veille-check.py"
REPO_ROOT = HOOKS_DIR.parents[1]
STATE_DIR = REPO_ROOT / ".claude" / "state"

SKIP_MARKER = "[VEILLE-SKIP] motif: typo"
OTHER_MARKER = "[VEILLE-SKIP] motif: test-only"

# 16 hex chars, the stored shape. Stands for "a fingerprint this hook can no
# longer recompute", which is exactly what a pre-migration value is.
LEGACY_FINGERPRINT = "f9eb9e25cc7261c2"


def _write_transcript(tmp_path: Path, text: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    transcript = tmp_path / "transcript.jsonl"
    entry = {"role": "assistant", "content": [{"type": "text", "text": text}]}
    transcript.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return transcript


def _seed_state(session_id: str, payload: dict) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"veille-skips-{session_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(transcript: Path, session_id: str, file_path: str) -> subprocess.CompletedProcess:
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "x = 1\n"},
        "session_id": session_id,
        "transcript_path": str(transcript),
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


def test_legacy_state_does_not_false_block(tmp_path):
    """2 skips already counted + a pre-migration fingerprint = no 3rd count."""
    session_id = f"legacy-{uuid.uuid4().hex[:12]}"
    state = _seed_state(
        session_id,
        {"skip_count": 2, "last_marker_hash": LEGACY_FINGERPRINT, "veille_seen": False},
    )
    try:
        transcript = _write_transcript(tmp_path, SKIP_MARKER)
        result = _run(transcript, session_id, str(tmp_path / "probe.py"))
        assert result.returncode == 0, (
            "a pre-migration fingerprint must not be read as a new marker: "
            f"{result.stderr!r}"
        )
        saved = json.loads(state.read_text(encoding="utf-8"))
        assert saved["skip_count"] == 2, (
            f"counter moved to {saved['skip_count']} without a new skip from Jay"
        )
        assert saved["digest_algo"] == "sha256", "the state must record its algorithm"
    finally:
        state.unlink(missing_ok=True)


def test_migration_is_granted_once_then_the_counter_resumes(tmp_path):
    """The lenient path applies to the first marker only, not to the session."""
    session_id = f"legacy-{uuid.uuid4().hex[:12]}"
    state = _seed_state(
        session_id,
        {"skip_count": 1, "last_marker_hash": LEGACY_FINGERPRINT, "veille_seen": False},
    )
    try:
        first = _run(_write_transcript(tmp_path, SKIP_MARKER), session_id, str(tmp_path / "a.py"))
        assert first.returncode == 0, f"1 skip is under the threshold: {first.stderr!r}"
        after_first = json.loads(state.read_text(encoding="utf-8"))
        assert after_first["skip_count"] == 1, "the migration call must not count"

        second = _run(
            _write_transcript(tmp_path / "b", OTHER_MARKER), session_id, str(tmp_path / "b.py")
        )
        assert second.returncode == 0, f"2 skips is still under the threshold: {second.stderr!r}"
        after_second = json.loads(state.read_text(encoding="utf-8"))
        assert after_second["skip_count"] == 2, (
            "a genuinely different marker must be counted once the state is migrated"
        )
    finally:
        state.unlink(missing_ok=True)


def test_threshold_still_blocks_on_a_migrated_state(tmp_path):
    """The lenient path must not disarm the skip counter for normal sessions."""
    session_id = f"modern-{uuid.uuid4().hex[:12]}"
    state = _seed_state(
        session_id,
        {
            "skip_count": 2,
            "last_marker_hash": "0" * 16,
            "veille_seen": False,
            "digest_algo": "sha256",
        },
    )
    try:
        transcript = _write_transcript(tmp_path, SKIP_MARKER)
        result = _run(transcript, session_id, str(tmp_path / "probe.py"))
        assert result.returncode == 2, "the 3rd consecutive skip must still block"
        assert b"threshold" in result.stderr.lower()
    finally:
        state.unlink(missing_ok=True)
