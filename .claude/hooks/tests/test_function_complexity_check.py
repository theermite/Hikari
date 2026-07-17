"""Tests for quality/function-complexity-check.py — Maintainability gate (F1 §4).

Closes the only robust gap found by the F1 inventory: per-function length
(> 30 lines) and cyclomatic complexity (> 10). File length is already guarded
by post-write-guard.py; try/except/pass by write-guard.py. This hook adds the
per-function dimension for Python via the stdlib `ast` parser.

PostToolUse Write|Edit: reads the written file from disk (always the full file,
always parseable — unlike an Edit fragment), parses it, and BLOCKS (exit 2) on
any function over the thresholds. Test files are excluded (rule: "excluding
tests"). Non-Python files pass (file-length guard covers them).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "function-complexity-check.py"


def _run(file_path: Path) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"file_path": str(file_path)}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
    )


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- pass cases -------------------------------------------------------------


def test_short_simple_function_passes(tmp_path):
    f = _write(tmp_path / "ok.py", "def f(x):\n    return x + 1\n")
    res = _run(f)
    assert res.returncode == 0


def test_non_python_passes(tmp_path):
    # 40 lines of TS — file-length guard covers it, this hook must not parse it.
    body = "function f() {\n" + "  doThing();\n" * 40 + "}\n"
    f = _write(tmp_path / "big.ts", body)
    res = _run(f)
    assert res.returncode == 0


def test_unparseable_python_passes(tmp_path):
    # An Edit fragment / syntactically invalid file must not false-block.
    f = _write(tmp_path / "frag.py", "def f(:\n    retur")
    res = _run(f)
    assert res.returncode == 0


def test_missing_file_passes(tmp_path):
    res = _run(tmp_path / "does-not-exist.py")
    assert res.returncode == 0


# --- block: function too long ----------------------------------------------


def test_long_function_blocks(tmp_path):
    body = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(31))
    f = _write(tmp_path / "long.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"big" in res.stderr
    assert b"30" in res.stderr


def test_function_exactly_30_lines_passes(tmp_path):
    # def line + 29 body lines = 30 total -> at the limit, allowed.
    body = "def edge():\n" + "".join(f"    x{i} = {i}\n" for i in range(29))
    f = _write(tmp_path / "edge.py", body)
    res = _run(f)
    assert res.returncode == 0


# --- block: complexity too high --------------------------------------------


def test_high_complexity_blocks(tmp_path):
    # 11 if-statements -> CC = 1 + 11 = 12 > 10. Few lines, so length is fine:
    # isolates the complexity signal.
    body = "def branchy(a):\n" + "".join(f"    if a == {i}:\n        a += 1\n" for i in range(11))
    f = _write(tmp_path / "cc.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"branchy" in res.stderr
    assert b"complex" in res.stderr.lower()


def test_boolean_operators_count_toward_complexity(tmp_path):
    # one if with 11 `or` operands -> CC = 1 + 1(if) + 10(extra bool operands) = 12.
    cond = " or ".join(f"a == {i}" for i in range(11))
    body = f"def booly(a):\n    if {cond}:\n        return 1\n    return 0\n"
    f = _write(tmp_path / "bool.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"booly" in res.stderr


# --- exclusions & per-function isolation ------------------------------------


def test_test_file_excluded(tmp_path):
    body = "def test_big():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(tmp_path / "test_something.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_conftest_excluded(tmp_path):
    body = "def fixture_heavy():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(tmp_path / "conftest.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_scripts_tooling_excluded(tmp_path):
    # Internal automation under scripts/ is exempt (like tests): orchestration
    # scripts legitimately have long functions, they are not product code.
    # (Jay 2026-06-13 — adding a project to propagate-methodology.py must not
    #  trip the gate on that legacy script's pre-existing long functions.)
    body = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(tmp_path / "scripts" / "propagate.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_complexity_is_per_function_not_summed(tmp_path):
    # outer has 6 ifs (CC 7), nested inner has 6 ifs (CC 7). Neither exceeds 10.
    # If nested decisions leaked into outer, outer would be 13 -> false block.
    inner = "    def inner(b):\n" + "".join(f"        if b == {i}:\n            b += 1\n" for i in range(6))
    outer = "def outer(a):\n" + "".join(f"    if a == {i}:\n        a += 1\n" for i in range(6)) + inner
    f = _write(tmp_path / "nested.py", outer)
    res = _run(f)
    assert res.returncode == 0
