"""End-to-end tests for guards/post-write-guard.py — the real payload shape.

Why this file exists (2026-08-16). `get_file_path()` read `data["file_path"]`
at the top level, while the harness nests it under `tool_input` (same defect
family fixed in write-guard.py 2026-08-07 and pre-code-veille-check.py
2026-08-11). `file_path` was therefore always empty on every real
invocation, and `main()` exits 0 before any check runs — the 500-line
BLOCKING ceiling, the empty-test detector, the UTF-8/BOM checks, all
hook-enforced in name only. Found via a 770-file inventory of files over
500 lines across the workspace (Jay, 2026-08-16).

Unit tests on `check_file_size(path)` cannot catch this — they call the
function directly with a bare path, bypassing `get_file_path()` and
`main()` entirely. Only a subprocess test with the real nested payload
reproduces the failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "post-write-guard.py"


def _run(tmp_path: Path, lines: int):
    target = tmp_path / "big.py"
    target.write_text("x = 1\n" * lines, encoding="utf-8")
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
    )
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )
    return result


def test_file_over_500_lines_is_blocked(tmp_path):
    result = _run(tmp_path, 600)
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr
    assert "500" in result.stderr


def test_file_under_300_lines_passes_silently(tmp_path):
    result = _run(tmp_path, 100)
    assert result.returncode == 0
    assert result.stderr == ""
