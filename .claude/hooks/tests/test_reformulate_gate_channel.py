"""reformulate-gate.py — the reformulation must reach the gate by a channel
the harness always records (2026-09-26).

Split from test_reformulate_gate.py (500-line ceiling); reuses its builders.
"""

from __future__ import annotations

from pathlib import Path

from test_reformulate_gate import (
    _assistant_tool,
    _one_prior_write,
    _run,
    _tool_result,
    _user,
    _write_transcript,
)

# --- The harness drops the text, never the tool call (2026-09-26) ------------
#
# Measured on the 60 latest transcripts: 391 assistant messages whose thinking
# is split into two entries, and ZERO of them keep a text block — the text the
# model wrote before its tool call is shown to Jay but never reaches the
# journal. 2203 messages with a single thinking entry keep theirs. A tool_use,
# by contrast, is always recorded. The fixture below reproduces the real
# 2026-09-25 Michi-Shinkofa shape: the model "said" REFORMULATION three times,
# the journal holds only thinking + tool_use.


def _assistant_split_thinking_then_tool(name: str, tid: str, inp: dict) -> list[dict]:
    """One real message as the harness journals it: two thinking entries, the
    text block gone, then the tool call."""
    return [
        {"role": "assistant", "content": [{"type": "thinking", "thinking": ""}]},
        {"role": "assistant", "content": [{"type": "thinking", "thinking": "je reformule"}]},
        _assistant_tool(name, tid, inp),
    ]


STATE_FILE = "D:/repo/.claude/state/reformulation.md"


def test_dropped_text_blocks_as_in_the_real_journal(tmp_path):
    entries = _one_prior_write() + _assistant_split_thinking_then_tool(
        "Write", "w2", {"file_path": "/repo/src/b.py", "content": "b"}
    )
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 2


def test_reformulation_written_to_state_file_unlocks_the_gate(tmp_path):
    entries = _one_prior_write() + _assistant_split_thinking_then_tool(
        "Write", "r1",
        {"file_path": STATE_FILE, "content": "REFORMULATION\n1. Compris ...\n4. Fichiers : b.py"},
    ) + [_tool_result("r1")]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"state-file reformulation should pass: {r.stderr!r}"


def test_state_file_edit_counts_too(tmp_path):
    entries = _one_prior_write() + [
        _assistant_tool("Edit", "r1", {
            "file_path": r"C:\repo\.claude\state\reformulation-s1.md",
            "old_string": "a", "new_string": "REFORMULATION : fichiers b.py",
        }),
        _tool_result("r1"),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"state-file edit should pass: {r.stderr!r}"


def test_state_file_write_that_errored_does_not_unlock(tmp_path):
    # 3rd independent review: a refused write left no reformulation anywhere.
    entries = _one_prior_write() + [
        _assistant_tool("Write", "r1", {"file_path": STATE_FILE,
                                        "content": "REFORMULATION fichiers b.py"}),
        _tool_result("r1", is_error=True),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    assert _run(transcript).returncode == 2


def test_state_file_write_in_the_same_message_still_counts(tmp_path):
    # Results land after every tool call of the message: the state-file write
    # has no result yet when the real write's hook fires.
    entries = _one_prior_write() + [
        {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Write", "id": "r1",
             "input": {"file_path": STATE_FILE, "content": "REFORMULATION fichiers b.py"}},
            {"type": "tool_use", "name": "Write", "id": "w2",
             "input": {"file_path": "/repo/src/b.py", "content": "b"}},
        ]},
    ]
    transcript = _write_transcript(tmp_path, *entries)
    r = _run(transcript)
    assert r.returncode == 0, f"in-flight state write should count: {r.stderr!r}"


def test_state_file_without_a_marker_does_not_unlock(tmp_path):
    entries = _one_prior_write() + [
        _assistant_tool("Write", "r1", {"file_path": STATE_FILE, "content": "rien"}),
        _tool_result("r1"),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    assert _run(transcript).returncode == 2


def test_marker_in_an_ordinary_file_does_not_unlock(tmp_path):
    # Only the dedicated channel counts: code that happens to contain the word
    # must never open the gate.
    entries = [
        _user("go"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py",
                                        "content": "# REFORMULATION plan files"}),
        _tool_result("w1"),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    assert _run(transcript).returncode == 2


def test_state_file_before_a_new_instruction_does_not_count(tmp_path):
    entries = [
        _assistant_tool("Write", "r1", {"file_path": STATE_FILE,
                                        "content": "REFORMULATION fichiers a.py"}),
        _tool_result("r1"),
    ] + [
        _user("maintenant une autre tache"),
        _assistant_tool("Write", "w1", {"file_path": "/repo/src/a.py", "content": "a"}),
        _tool_result("w1"),
    ]
    transcript = _write_transcript(tmp_path, *entries)
    assert _run(transcript).returncode == 2


def test_plan_file_is_exempt(tmp_path):
    # Plan mode's plan IS the reformulation awaiting approval: blocking its
    # file left no recovery at all on 2026-09-25.
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    plan = Path.home() / ".claude" / "plans" / "composed-swimming-boole.md"
    r = _run(transcript, file_path=str(plan))
    assert r.returncode == 0, f"plan file must pass: {r.stderr!r}"


def test_a_project_folder_named_plans_stays_gated(tmp_path):
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    r = _run(transcript, file_path="/repo/packages/foo/.claude/plans/real-code.js")
    assert r.returncode == 2


def test_dot_segments_cannot_walk_out_of_an_exempt_folder(tmp_path):
    # 2nd independent review: `~/.claude/plans/../../repo/src/x.py` passed as a
    # plan file. Paths are compared in canonical form, exemptions included.
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    escapes = (
        str(Path.home() / ".claude" / "plans" / ".." / ".." / "repo" / "src" / "x.py"),
        "/repo/.claude/state/../../src/x.py",
    )
    for path in escapes:
        assert _run(transcript, file_path=path).returncode == 2, path


def test_a_look_alike_state_path_does_not_unlock(tmp_path):
    # Only `.claude/state/reformulation*.md` itself counts, not a path that
    # merely contains the string.
    for decoy in ("/repo/.claude/state/reformulation/notes.py",
                  "/repo/.claude/state/reformulation.py",
                  "/repo/src/.claude/state-reformulation.md"):
        entries = _one_prior_write() + [
            _assistant_tool("Write", "r1", {"file_path": decoy,
                                            "content": "REFORMULATION fichiers b.py"}),
            _tool_result("r1"),
        ]
        transcript = _write_transcript(tmp_path, *entries)
        assert _run(transcript).returncode == 2, decoy


def test_block_message_names_the_channel_that_survives(tmp_path):
    transcript = _write_transcript(tmp_path, *_one_prior_write())
    r = _run(transcript)
    assert r.returncode == 2
    assert b".claude/state/reformulation" in r.stderr
