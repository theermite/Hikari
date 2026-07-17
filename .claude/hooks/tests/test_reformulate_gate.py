"""reformulate-gate.py — PreToolUse Write|Edit reformulation gate.

Behavior under test:
- 1st write of the turn -> always pass
- 2nd+ write without a reformulation marker AND without an approved plan -> BLOCK
- 2nd+ write WITH a reformulation marker in assistant text -> pass (regression)
- 2nd+ write WITH an approved plan (ExitPlanMode tool_result, is_error=False)
  anywhere in the session -> pass (Chantier C)
- A REJECTED plan (ExitPlanMode tool_result is_error=True) does NOT count
- An IN-FLIGHT plan (ExitPlanMode tool_use with no result yet) does NOT count

Transcript shape mirrors the Claude Code JSONL: top-level {role, content}.
Real user messages carry string (or non-tool_result) content and act as the
turn boundary; tool_result deliveries are role=user but carry tool_result
blocks and must NOT cut the turn short.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "reformulate-gate.py"


# --- Transcript builders -----------------------------------------------------


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_tool(name: str, tid: str, inp: dict | None = None) -> dict:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "name": name, "id": tid, "input": inp or {}}],
    }


def _tool_result(tid: str, is_error: bool = False) -> dict:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": is_error}],
    }


def _write_transcript(tmp_path: Path, *entries: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )
    return transcript


def _run(
    transcript: Path,
    file_path: str = "/repo/src/foo.py",
    agent_id: str | None = None,
) -> subprocess.CompletedProcess:
    """Fire the hook. `transcript` is always the PARENT's journal — that is what
    the harness passes, even to a sub-agent (measured 2026-07-16). Passing
    agent_id reproduces a sub-agent call."""
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "x = 1"},
        "transcript_path": str(transcript),
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
        payload["agent_type"] = "general-purpose"
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


def _write_subagent_transcript(parent: Path, agent_id: str, *entries: dict) -> Path:
    """Create the sub-agent journal where the harness really puts it:
    <parent-without-suffix>/subagents/agent-<agent_id>.jsonl (measured)."""
    d = parent.with_suffix("") / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    j = d / f"agent-{agent_id}.jsonl"
    j.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return j


# A completed, non-error Write earlier in the turn -> makes this attempt the 2nd.
def _one_prior_write() -> list[dict]:
    return [
        _user("go"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1", is_error=False),
    ]


# --- 1st write always passes -------------------------------------------------


def test_first_write_passes(tmp_path):
    transcript = _write_transcript(tmp_path, _user("go"))
    r = _run(transcript)
    assert r.returncode == 0
    assert r.stderr == b""


def test_skip_path_passes(tmp_path):
    # A file under .next/ is exempt regardless of count.
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    r = _run(transcript, file_path="/repo/.next/server/x.js")
    assert r.returncode == 0


# --- 2nd write blocks without reformulation or plan --------------------------


def test_second_write_blocks_without_marker_or_plan(tmp_path):
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    r = _run(transcript)
    assert r.returncode == 2
    assert b"BLOCKED" in r.stderr
    assert b"reformulation" in r.stderr.lower()


# --- 2nd write passes with a reformulation marker (regression) ---------------


def test_second_write_passes_with_reformulation_text(tmp_path):
    entries = _one_prior_write() + [
        _assistant_text("REFORMULATION: j'ai compris, fichiers touches: a.py b.py"),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"reformulation text should pass: {r.stderr!r}"


# --- 2nd write passes with an APPROVED plan (Chantier C) ---------------------


def test_second_write_passes_with_approved_plan(tmp_path):
    entries = _one_prior_write() + [
        _assistant_tool("ExitPlanMode", "p1", {"plan": "do bricks 1-3"}),
        _tool_result("p1", is_error=False),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"approved plan should pass: {r.stderr!r}"
    assert r.stderr == b""


# --- A rejected plan does NOT count ------------------------------------------


def test_rejected_plan_does_not_count(tmp_path):
    entries = _one_prior_write() + [
        _assistant_tool("ExitPlanMode", "p1", {"plan": "do bricks"}),
        _tool_result("p1", is_error=True),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 2, "rejected plan must not satisfy the gate"


# --- An in-flight plan (no result yet) does NOT count ------------------------


def test_inflight_plan_does_not_count(tmp_path):
    entries = _one_prior_write() + [
        _assistant_tool("ExitPlanMode", "p1", {"plan": "do bricks"}),
        # no tool_result for p1
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 2, "in-flight plan must not satisfy the gate"


# --- Continuation nudges must NOT re-arm the window (Jay 2026-06-16) ----------
# A relance ("go", "reprends", "gelé ?") sent mid-build is a continuation, not
# a new instruction. It must NOT reset the write counter / reformulation window:
# the reformulation made before the nudge still covers the writes that follow,
# until Jay gives a genuinely new instruction.


def test_continuation_nudge_does_not_rearm_window(tmp_path):
    # Real instruction -> reformulation -> nudge "go" -> 1 completed write.
    # This attempt is the 2nd write AFTER the nudge. Under the old behavior the
    # nudge was the boundary (marker behind it -> BLOCK). It must now PASS.
    entries = [
        _user("corrige le hook reformulate et la veille"),
        _assistant_text("REFORMULATION: j'ai compris, fichiers touches: a.py b.py"),
        _user("go"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1", is_error=False),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"a nudge must not re-arm the gate: {r.stderr!r}"


def test_jay_relances_are_continuations(tmp_path):
    for nudge in ("gelé ?", "reprends", "tu es là ?", "continue", "vas-y"):
        entries = [
            _user("corrige le hook X"),
            _assistant_text("REFORMULATION: compris, fichiers touches: a.py"),
            _user(nudge),
            _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
            _tool_result("w1", is_error=False),
        ]
        transcript = _write_transcript(tmp_path, *entries)
        r = _run(transcript)
        assert r.returncode == 0, f"{nudge!r} must be a continuation: {r.stderr!r}"


def test_new_instruction_still_resets_window(tmp_path):
    # A genuinely new instruction (not a nudge) MUST reset the window: the
    # reformulation made for the previous task does not cover the new one.
    entries = [
        _user("corrige le hook X"),
        _assistant_text("REFORMULATION: compris, fichiers touches: a.py"),
        _assistant_tool("Write", "w0", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w0", is_error=False),
        _user("maintenant refais completement la fonction main du module Y"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/y.py", "content": "y"}),
        _tool_result("w1", is_error=False),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 2, "a new instruction must re-arm the gate"


# --- Sub-agents (bug fixed 2026-07-16) ---------------------------------------
# A hook fired from a sub-agent receives the PARENT's transcript_path. Before the
# fix the gate counted the parent's writes against the sub-agent AND looked for
# the sub-agent's reformulation in the parent journal, where its text is never
# written -> every sub-agent write blocked forever (Sakusen B2 run lost).


def test_subagent_with_own_reformulation_passes(tmp_path):
    # THE REAL SCENARIO: parent journal has 1 completed write; the sub-agent has
    # reformulated in ITS OWN journal. Its write must pass.
    parent = _write_transcript(tmp_path, *_one_prior_write())
    _write_subagent_transcript(
        parent,
        "a57c9581dd38b0f5b",
        _user("implement brick B2"),
        _assistant_text("REFORMULATION: compris, fichiers touches: engine.ts"),
        _assistant_tool("Write", "s1", {"file_path": "/repo/src/e.ts", "content": "e"}),
        _tool_result("s1", is_error=False),
    )
    r = _run(parent, agent_id="a57c9581dd38b0f5b")
    assert r.returncode == 0, f"sub-agent reformulation must be honored: {r.stderr!r}"


def test_subagent_does_not_inherit_parent_write_count(tmp_path):
    # Property 1: two distinct threads of work. The parent's write must never
    # arm the gate for a sub-agent whose own journal shows no completed write.
    parent = _write_transcript(tmp_path, *_one_prior_write())
    _write_subagent_transcript(
        parent,
        "agent42",
        _user("do the thing"),
    )
    r = _run(parent, agent_id="agent42")
    assert r.returncode == 0, f"parent's counter must not leak: {r.stderr!r}"


def test_subagent_gate_still_fires_in_its_own_context(tmp_path):
    # The gate keeps its value INSIDE the sub-agent: 2nd write of its own thread
    # with no reformulation of its own -> BLOCK. The fix removes the false
    # positive, never the gate.
    parent = _write_transcript(tmp_path, _user("go"))
    _write_subagent_transcript(
        parent,
        "agent42",
        _user("do the thing"),
        _assistant_tool("Write", "s1", {"file_path": "/repo/src/a.ts", "content": "a"}),
        _tool_result("s1", is_error=False),
    )
    r = _run(parent, agent_id="agent42")
    assert r.returncode == 2, "the gate must still fire inside the sub-agent's own thread"


def test_subagent_without_readable_journal_passes(tmp_path):
    # Property 2: no trustworthy context -> pass, never block. The other Ring 0
    # gates (veille, secrets, tests, complexity) still fire on this write.
    parent = _write_transcript(tmp_path, *_one_prior_write())
    # no sub-agent journal written at all
    r = _run(parent, agent_id="ghost")
    assert r.returncode == 0, f"unreadable sub-agent context must pass: {r.stderr!r}"
    assert r.stderr == b""


def test_parent_write_unaffected_by_the_fix(tmp_path):
    # Property 3: with no agent_id, behaviour is exactly as before — even if a
    # sub-agent journal happens to exist next to the parent's.
    parent = _write_transcript(tmp_path, *_one_prior_write())
    _write_subagent_transcript(
        parent,
        "a57c9581dd38b0f5b",
        _user("x"),
        _assistant_text("REFORMULATION: compris, fichiers touches: e.ts"),
    )
    r = _run(parent)  # no agent_id -> parent
    assert r.returncode == 2, "a sub-agent's reformulation must not unlock the parent"


# --- Robustness: empty / malformed input -------------------------------------


def test_empty_stdin_passes():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0
