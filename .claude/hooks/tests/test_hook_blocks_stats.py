"""hook-blocks-stats.py — SessionEnd observability: count hook blocks/warns per signature.

Behavior under test (A2 — guardrail-fatigue instrumentation):
- Scan the session transcript for hook BLOCKED:/WARNING: lines.
- Count ONLY real hook output (tool results / non-assistant entries), so that
  Takumi's own citations of "BLOCKED:" in assistant text are NOT counted.
- Ignore template/RECOVERY lines (those containing <...> placeholders).
- Group by a normalized signature (the short reason after BLOCKED:/WARNING:).
- Append one cumulative entry per session to .claude/state/hook-blocks.jsonl.
- NEVER block: this is observability, it must always exit 0.

Tests isolate state by running the hook with cwd set to a temp repo (with a
.git marker) so find_repo_root() resolves there — no pollution of the real
.claude/state/.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "hook-blocks-stats.py"


# --- Helpers ----------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """A temp dir that looks like a git repo so find_repo_root() stops here."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _tool_result(text: str) -> dict:
    """A transcript entry shaped like a tool result (real hook output lands here)."""
    return {"message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def _assistant(text: str) -> dict:
    """A transcript entry shaped like assistant text (Takumi citing a message)."""
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _make_transcript(tmp_path: Path, *entries: dict) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )
    return transcript


def _run(repo: Path, transcript: Path | None, session_id: str) -> subprocess.CompletedProcess:
    payload: dict = {"session_id": session_id}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        cwd=str(repo),
    )


def _journal(repo: Path) -> list[dict]:
    p = repo / ".claude" / "state" / "hook-blocks.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


VEILLE_BLOCK = (
    "BLOCKED: Veille / SKB evidence missing before writing source code.\n"
    "Target: src/x.py\n"
    "RECOVERY: Output one of the strict markers BEFORE retrying:\n"
    "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>"
)


# --- Tests ------------------------------------------------------------------


def test_counts_block_from_tool_result(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    assert len(journal) == 1
    counts = journal[0]["blocks"]
    # one signature derived from the first BLOCKED line, counted once
    assert sum(counts.values()) == 1
    assert any("veille" in sig.lower() for sig in counts)


def test_ignores_assistant_citation(tmp_path):
    repo = _make_repo(tmp_path)
    # Same BLOCKED text, but in ASSISTANT output (Takumi quoting it) -> not counted.
    tr = _make_transcript(tmp_path, _assistant(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    # entry may exist but with zero blocks, or no entry at all
    total = sum(sum(e["blocks"].values()) for e in journal)
    assert total == 0


def test_counts_warning_separately(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(
        tmp_path,
        _tool_result("WARNING: source code write with no sibling test. ACTION: add a test."),
    )
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    journal = _journal(repo)
    assert len(journal) == 1
    assert sum(journal[0]["blocks"].values()) == 0
    assert sum(journal[0]["warns"].values()) == 1


def test_same_signature_accumulates(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK), _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    counts = _journal(repo)[0]["blocks"]
    assert sum(counts.values()) == 2
    # same reason -> single signature key
    assert len(counts) == 1


def test_ignores_template_recovery_lines(tmp_path):
    repo = _make_repo(tmp_path)
    # A message whose ONLY BLOCKED-ish lines are template placeholders must not count.
    template_only = (
        "RECOVERY: Output one of the strict markers:\n"
        "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>"
    )
    tr = _make_transcript(tmp_path, _tool_result(template_only))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    total = sum(sum(e["blocks"].values()) for e in _journal(repo))
    assert total == 0


def test_never_blocks_without_transcript(tmp_path):
    repo = _make_repo(tmp_path)
    res = _run(repo, None, f"s-{uuid.uuid4()}")
    assert res.returncode == 0


def test_summary_on_stderr(tmp_path):
    repo = _make_repo(tmp_path)
    tr = _make_transcript(tmp_path, _tool_result(VEILLE_BLOCK))
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    # a human-readable one-liner is surfaced for the session-end summary
    assert b"veille" in res.stderr.lower() or b"block" in res.stderr.lower()


# --- Overcome (friction) detection wired into the journal + summary ----------


def _tool_use(tool: str, target: str, tid: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": target}}]}}


def _tool_result_id(tid: str, is_error: bool, text: str) -> dict:
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def test_overcome_block_recorded_and_surfaced(tmp_path):
    repo = _make_repo(tmp_path)
    # Block on src/x.py, then a retry on the SAME target succeeds -> overcome.
    tr = _make_transcript(
        tmp_path,
        _tool_use("Edit", "src/x.py", "t1"),
        _tool_result_id("t1", True, VEILLE_BLOCK),
        _tool_use("Edit", "src/x.py", "t2"),
        _tool_result_id("t2", False, "ok"),
    )
    res = _run(repo, tr, f"s-{uuid.uuid4()}")
    assert res.returncode == 0
    entry = _journal(repo)[0]
    assert "overcome" in entry
    assert sum(entry["overcome"].values()) == 1
    assert b"hook-friction" in res.stderr
