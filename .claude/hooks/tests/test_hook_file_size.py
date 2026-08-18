"""Hook files obey the same size limit they enforce on everyone else.

Quality.md: source file WARNING at 300 lines, BLOCKING above 500. The hooks
are source code — they were exempt in practice only because nothing measured
them. On 2026-08-18 a workspace-wide scan found exactly one offender, and it
was propagated to 33 repositories, counting 33 times in the debt.

This test closes the FAMILY, not the single case: any future hook that grows
past the limit fails here, in the repo that owns the methodology, before the
propagation multiplies it.

Scope: hook implementation files only. Test files are excluded — a table-driven
test file legitimately grows with the number of cases it covers, and Quality.md
counts function length excluding tests for the same reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]

BLOCKING_LINES = 500
WARNING_LINES = 300

EXCLUDED_PARTS = ("__pycache__", "tests", "_archive")


def _hook_files() -> list[Path]:
    return sorted(
        p
        for p in HOOKS_DIR.rglob("*.py")
        if not any(part in EXCLUDED_PARTS for part in p.parts)
    )


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def test_hook_files_are_discovered():
    """Guard against a glob that silently matches nothing — a test that finds
    no file passes forever and proves nothing."""
    files = _hook_files()
    assert len(files) >= 20, f"expected the hook tree, found {len(files)} files"


@pytest.mark.parametrize("path", _hook_files(), ids=lambda p: p.name)
def test_hook_file_stays_under_blocking_limit(path: Path):
    lines = _line_count(path)
    assert lines <= BLOCKING_LINES, (
        f"{path.relative_to(HOOKS_DIR)} has {lines} lines "
        f"(BLOCKING limit {BLOCKING_LINES}). Split it into cohesive modules "
        f"under hooks/lib/ — this file ships to every Shinkofa repo."
    )


def test_report_files_above_warning_threshold():
    """Not a failure — a visible list, so growth is noticed before it blocks."""
    warned = [
        (p.relative_to(HOOKS_DIR).as_posix(), _line_count(p))
        for p in _hook_files()
        if WARNING_LINES < _line_count(p) <= BLOCKING_LINES
    ]
    for name, lines in warned:
        print(f"[WARN] {name}: {lines} lines (> {WARNING_LINES})")
    assert True
