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
import subprocess
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


def _functions(node: ast.AST, prefix: str = ""):
    """(qualified name, function node) for every function, classes and enclosing functions in the name."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + child.name, child
            yield from _functions(child, prefix + child.name + ".")
        elif isinstance(child, ast.ClassDef):
            yield from _functions(child, prefix + child.name + ".")
        else:
            yield from _functions(child, prefix)


def _measure(tree: ast.AST) -> list[tuple[str, str, int, int]]:
    """(name, kind, value, line) for every function over a threshold; kind is "length" or "complexity"."""
    found: list[tuple[str, str, int, int]] = []
    for name, node in _functions(tree):
        length = _function_length(node)
        if length > MAX_FUNC_LINES:
            found.append((name, "length", length, node.lineno))
        cc = _complexity(node)
        if cc > MAX_COMPLEXITY:
            found.append((name, "complexity", cc, node.lineno))
    return found


def _describe(name: str, kind: str, value: int, line: int) -> str:
    if kind == "length":
        return f"  - `{name}` (line {line}): {value} lines (max {MAX_FUNC_LINES})"
    return f"  - `{name}` (line {line}): cyclomatic complexity {value} (max {MAX_COMPLEXITY})"


def _parse(source: str | None) -> ast.AST | None:
    try:
        return ast.parse(source) if source is not None else None
    except SyntaxError:
        return None


def split_violations(source: str, committed: str | None) -> tuple[list[str], list[str]]:
    """(new, inherited) violation lines. Inherited = already over the limit in the committed
    version and not worse now: the edit did not cause it, so it is reported, not blocked."""
    tree = _parse(source)
    if tree is None:
        return [], []
    before_tree = _parse(committed)
    before: dict[tuple[str, str], int] = {}
    for name, kind, value, _line in (_measure(before_tree) if before_tree is not None else []):
        before[(name, kind)] = max(value, before.get((name, kind), 0))
    new, inherited = [], []
    for name, kind, value, line in _measure(tree):
        target = inherited if value <= before.get((name, kind), 0) else new
        target.append(_describe(name, kind, value, line))
    return new, inherited


def _committed_source(file_path: str) -> str | None:
    """The file as committed at HEAD, or None (untracked, no git, unreadable)."""
    try:
        rel = Path(file_path).resolve().relative_to(PROJECT_ROOT).as_posix()
        out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(PROJECT_ROOT),
                             capture_output=True, timeout=10)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def main() -> int:
    _, data = common.read_hook_input()
    source = _eligible_source(data)
    if source is None:
        return 0
    new, inherited = split_violations(source, _committed_source(common.get_file_path(data)))
    if inherited:
        common.warn(common.format_warn(
            "function already over the limit before this edit (not made worse)\n" + "\n".join(inherited),
            "not blocking; split it when you next work on it.",
            reference="rules/Quality.md (Maintainability)"))
    if not new:
        return 0

    common.block(
        common.format_block(
            "Maintainability: function over the limit\n" + "\n".join(new),
            "Split the function into smaller cohesive units (one concept each). "
            "A 30-line function with low complexity reads better than a clever dense one.",
            reference="rules/Quality.md (Maintainability)",
        )
    )
    return 2  # unreached (common.block exits), kept for clarity


if __name__ == "__main__":
    sys.exit(main())
