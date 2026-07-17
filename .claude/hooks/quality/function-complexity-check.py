#!/usr/bin/env python3
"""function-complexity-check.py — Maintainability gate (per-function).

Closes the only robust gap found by the F1 BLOCKING inventory (2026-06-13):
- function length > 30 lines  (rules/Quality.md Maintainability)
- cyclomatic complexity > 10  (rules/Quality.md Maintainability)

Already covered elsewhere (NOT re-done here):
- file length 300/500 -> post-write-guard.py
- try/except/pass, empty catch -> write-guard.py

Event: PostToolUse Write|Edit. Reads the WRITTEN file from disk (always the full,
parseable file — an Edit's new_string is only a fragment). Python only: the
stdlib `ast` parser is robust; TS/JS has no stdlib parser, so per-function checks
there would need a fragile brace-counter (rejected — file-length already guards
TS/JS). Test files are excluded per the rule ("Max 30 lines per function,
excluding tests").

Exit codes: 0 pass, 2 block (mirrors post-write-guard.py).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
# <project>/.claude/hooks/quality -> <project>. This gate governs THIS project only.
PROJECT_ROOT = HOOK_DIR.parents[2]
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

import common  # noqa: E402

MAX_FUNC_LINES = 30
MAX_COMPLEXITY = 10

# Nodes that add one decision point to cyclomatic complexity.
_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.IfExp,        # ternary
    ast.ExceptHandler,
    ast.match_case,   # each match arm (Python 3.10+)
)
# Nested callables are measured on their own; do not recurse into them.
_NESTED_CALLABLE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _is_test_file(path: Path) -> bool:
    name = path.name
    parts = {p.lower() for p in path.parts}
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or "tests" in parts
        or "__tests__" in parts
    )


def _complexity(fn: ast.AST) -> int:
    """Cyclomatic complexity of a function's OWN body (nested callables excluded)."""
    count = 1

    def walk(node: ast.AST) -> None:
        nonlocal count
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _NESTED_CALLABLE):
                continue  # measured separately
            if isinstance(child, _BRANCH_NODES):
                count += 1
            elif isinstance(child, ast.BoolOp):
                count += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                count += 1 + len(child.ifs)  # the loop + each filter
            walk(child)

    walk(fn)
    return count


def _function_length(fn: ast.AST) -> int:
    end = getattr(fn, "end_lineno", None)
    if end is None:
        return 0
    return end - fn.lineno + 1


def _is_tooling(path: Path) -> bool:
    """Internal automation under scripts/ is exempt — orchestration, not product
    code (e.g. propagate-methodology.py). Mirrors the test-file exemption."""
    return "scripts" in {p.lower() for p in path.parts}


def _eligible_source(data: dict) -> str | None:
    """Return the source to analyze, or None if the file is out of scope."""
    file_path = common.get_file_path(data)
    if not file_path or not file_path.endswith(".py"):
        return None
    path = Path(file_path)
    # Out of scope: files in another repo edited during this session (e.g. a
    # vendored fork like ACE-Step-Studio). A project's quality gate must not
    # police code it does not own.
    try:
        path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return None
    if _is_test_file(path) or _is_tooling(path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _collect_violations(tree: ast.AST) -> list[str]:
    """One line per function over a threshold (length or complexity)."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = _function_length(node)
        if length > MAX_FUNC_LINES:
            violations.append(
                f"  - `{node.name}` (line {node.lineno}): {length} lines (max {MAX_FUNC_LINES})"
            )
        cc = _complexity(node)
        if cc > MAX_COMPLEXITY:
            violations.append(
                f"  - `{node.name}` (line {node.lineno}): cyclomatic complexity {cc} (max {MAX_COMPLEXITY})"
            )
    return violations


def main() -> int:
    _, data = common.read_hook_input()
    source = _eligible_source(data)
    if source is None:
        return 0
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0  # fragment / invalid — cannot analyze, never false-block

    violations = _collect_violations(tree)
    if not violations:
        return 0

    common.block(
        common.format_block(
            "Maintainability: function over the limit\n" + "\n".join(violations),
            "Split the function into smaller cohesive units (one concept each). "
            "A 30-line function with low complexity reads better than a clever dense one.",
            reference="rules/Quality.md (Maintainability)",
        )
    )
    return 2  # unreached (common.block exits), kept for clarity


if __name__ == "__main__":
    sys.exit(main())
