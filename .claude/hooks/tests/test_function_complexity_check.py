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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "quality" / "function-complexity-check.py"
# .claude/hooks/tests/<this file> -> <project>. Mirrors the hook's own PROJECT_ROOT.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def project_tmp():
    """A scratch dir INSIDE the project.

    The gate only polices files it owns (parents[2] filter). A fixture writing
    to the OS temp dir puts every case out of scope, so the hook exits 0 and the
    assertions stop proving anything. `tmp/` is gitignored.
    """
    base = PROJECT_ROOT / "tmp" / "hook-tests"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(dir=base))
    yield scratch
    shutil.rmtree(scratch, ignore_errors=True)


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


def _long_function(name: str = "big", lines: int = 31) -> str:
    return f"def {name}():\n" + "".join(f"    x{i} = {i}\n" for i in range(lines))


# --- pass cases -------------------------------------------------------------


def test_short_simple_function_passes(project_tmp):
    f = _write(project_tmp / "ok.py", "def f(x):\n    return x + 1\n")
    res = _run(f)
    assert res.returncode == 0


def test_non_python_passes(project_tmp):
    # 40 lines of TS — file-length guard covers it, this hook must not parse it.
    body = "function f() {\n" + "  doThing();\n" * 40 + "}\n"
    f = _write(project_tmp / "big.ts", body)
    res = _run(f)
    assert res.returncode == 0


def test_unparseable_python_passes(project_tmp):
    # An Edit fragment / syntactically invalid file must not false-block.
    f = _write(project_tmp / "frag.py", "def f(:\n    retur")
    res = _run(f)
    assert res.returncode == 0


def test_missing_file_passes(project_tmp):
    res = _run(project_tmp / "does-not-exist.py")
    assert res.returncode == 0


# --- block: function too long ----------------------------------------------


def test_long_function_blocks(project_tmp):
    body = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(31))
    f = _write(project_tmp / "long.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"big" in res.stderr
    assert b"30" in res.stderr


def test_function_exactly_30_lines_passes(project_tmp):
    # def line + 29 body lines = 30 total -> at the limit, allowed.
    body = "def edge():\n" + "".join(f"    x{i} = {i}\n" for i in range(29))
    f = _write(project_tmp / "edge.py", body)
    res = _run(f)
    assert res.returncode == 0


# --- block: complexity too high --------------------------------------------


def test_high_complexity_blocks(project_tmp):
    # 11 if-statements -> CC = 1 + 11 = 12 > 10. Few lines, so length is fine:
    # isolates the complexity signal.
    body = "def branchy(a):\n" + "".join(f"    if a == {i}:\n        a += 1\n" for i in range(11))
    f = _write(project_tmp / "cc.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"branchy" in res.stderr
    assert b"complex" in res.stderr.lower()


def test_boolean_operators_count_toward_complexity(project_tmp):
    # one if with 11 `or` operands -> CC = 1 + 1(if) + 10(extra bool operands) = 12.
    cond = " or ".join(f"a == {i}" for i in range(11))
    body = f"def booly(a):\n    if {cond}:\n        return 1\n    return 0\n"
    f = _write(project_tmp / "bool.py", body)
    res = _run(f)
    assert res.returncode == 2
    assert b"booly" in res.stderr


# --- exclusions & per-function isolation ------------------------------------


def test_test_file_excluded(project_tmp):
    body = "def test_big():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(project_tmp / "test_something.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_conftest_excluded(project_tmp):
    body = "def fixture_heavy():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(project_tmp / "conftest.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_scripts_tooling_excluded(project_tmp):
    # Internal automation under scripts/ is exempt (like tests): orchestration
    # scripts legitimately have long functions, they are not product code.
    # (Jay 2026-06-13 — adding a project to propagate-methodology.py must not
    #  trip the gate on that legacy script's pre-existing long functions.)
    body = "def big():\n" + "".join(f"    x{i} = {i}\n" for i in range(40))
    f = _write(project_tmp / "scripts" / "propagate.py", body)
    res = _run(f)
    assert res.returncode == 0


def test_file_outside_project_passes(tmp_path):
    # A vendored fork or a third-party repo opened in the same session is not
    # ours to police (Jay 2026-07-12: the gate broke editing ACE-Step-Studio,
    # whose upstream engine legitimately exceeds 30 lines). `tmp_path` is the OS
    # temp dir -> outside PROJECT_ROOT on purpose. This is the ONLY case here
    # allowed to live outside the project.
    f = _write(tmp_path / "vendored.py", _long_function("upstream_engine"))
    res = _run(f)
    assert res.returncode == 0


def test_complexity_is_per_function_not_summed(project_tmp):
    # outer has 6 ifs (CC 7), nested inner has 6 ifs (CC 7). Neither exceeds 10.
    # If nested decisions leaked into outer, outer would be 13 -> false block.
    inner = "    def inner(b):\n" + "".join(f"        if b == {i}:\n            b += 1\n" for i in range(6))
    outer = "def outer(a):\n" + "".join(f"    if a == {i}:\n        a += 1\n" for i in range(6)) + inner
    f = _write(project_tmp / "nested.py", outer)
    res = _run(f)
    assert res.returncode == 0
