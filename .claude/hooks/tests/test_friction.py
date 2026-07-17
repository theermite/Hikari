"""Tests for lib/friction.py — overcome-block detection.

An "overcome" block = a tool call blocked by a hook (tool_result is_error with
"BLOCKED:") where a LATER call on the SAME target then succeeded. That retry-and-
pass is the strongest transcript signal of friction (the block was satisfied by a
retry, so it either false-positived or forced throwaway work). It is a proxy, not
proof — a legitimate read-first gate is also "overcome" by complying.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib" / "friction.py"
_spec = importlib.util.spec_from_file_location("friction", LIB)
friction = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(friction)


def _use(tool: str, target: str, tid: str) -> dict:
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": target}}]}}


def _result(tid: str, is_error: bool, text: str) -> dict:
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "is_error": is_error, "content": text}]}}


def _write(tmp_path: Path, *entries: dict) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def test_block_then_retry_passes_is_overcome(tmp_path):
    t = _write(
        tmp_path,
        _use("Edit", "X.py", "t1"),
        _result("t1", True, "BLOCKED: veille / skb evidence missing before writing source code\nTarget: X.py"),
        _use("Edit", "X.py", "t2"),
        _result("t2", False, "ok"),
    )
    out = friction.detect_overcome_blocks(str(t))
    assert out == {"veille / skb evidence missing before writing source code": 1}


def test_block_never_retried_is_not_overcome(tmp_path):
    t = _write(
        tmp_path,
        _use("Edit", "X.py", "t1"),
        _result("t1", True, "BLOCKED: sensitive change detected"),
    )
    assert friction.detect_overcome_blocks(str(t)) == {}


def test_block_then_success_on_other_target_is_not_overcome(tmp_path):
    t = _write(
        tmp_path,
        _use("Edit", "X.py", "t1"),
        _result("t1", True, "BLOCKED: sensitive change detected"),
        _use("Edit", "Y.py", "t2"),
        _result("t2", False, "ok"),
    )
    assert friction.detect_overcome_blocks(str(t)) == {}


def test_repeated_block_then_pass_counts_once_per_target(tmp_path):
    t = _write(
        tmp_path,
        _use("Edit", "X.py", "t1"),
        _result("t1", True, "BLOCKED: maintainability function over the limit"),
        _use("Edit", "X.py", "t2"),
        _result("t2", True, "BLOCKED: maintainability function over the limit"),
        _use("Edit", "X.py", "t3"),
        _result("t3", False, "ok"),
    )
    assert friction.detect_overcome_blocks(str(t)) == {"maintainability function over the limit": 1}


def test_clean_session_has_no_overcome(tmp_path):
    t = _write(
        tmp_path,
        _use("Edit", "X.py", "t1"),
        _result("t1", False, "ok"),
    )
    assert friction.detect_overcome_blocks(str(t)) == {}


def test_missing_transcript_returns_empty():
    assert friction.detect_overcome_blocks("") == {}
