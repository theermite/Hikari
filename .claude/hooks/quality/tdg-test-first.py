#!/usr/bin/env python3
"""TDG Test-First gate — PreToolUse Write|Edit.

Enforces Quality.md "Test-Driven Generation": before writing implementation
source code, a corresponding test file MUST exist in the repo OR have been
written/edited in the current session.

Heuristic:
  - Target = source file under src/, lib/, app/, packages/, or root (.ts/.tsx/.js/.jsx/.py/.ex/.rs)
  - Look for sibling test file by convention OR session-recent test write
  - WARN (not BLOCK) — TDG is a process discipline, not a hard gate; the
    overall test coverage is enforced at CI level.

Skip cases:
  - Test files themselves (.test.*, .spec.*, _test.*, test_*.py)
  - Configs (.config.*, package.json, tsconfig.json)
  - Docs (.md, .mdx)
  - Hooks, .claude/, methodology files
  - Generated/build outputs
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import get_file_path, pass_through, read_hook_input, warn  # type: ignore
from transcript_reader import iter_tool_calls  # type: ignore

SOURCE_EXT = {"ts", "tsx", "js", "jsx", "py", "ex", "rs"}

SKIP_PATH_PARTS = (
    "/.claude/",
    "\\.claude\\",
    "/node_modules/",
    "\\node_modules\\",
    "/dist/",
    "\\dist\\",
    "/build/",
    "\\build\\",
    "/.next/",
    "\\.next\\",
    "/__pycache__/",
    "\\__pycache__\\",
    "/coverage/",
    "\\coverage\\",
    "/.venv/",
    "\\.venv\\",
    "/target/",
    "\\target\\",
    "/_build/",
    "\\_build\\",
    "/docs/",
    "\\docs\\",
    "/mnk/",
    "\\mnk\\",
    "/rules/",
    "\\rules\\",
    "/scripts/",
    "\\scripts\\",
    "/migrations/",
    "\\migrations\\",
)

SKIP_FILENAME_PATTERNS = (
    r"\.test\.",
    r"\.spec\.",
    r"_test\.",
    r"^test_",
    r"__tests__",
    r"conftest\.py",
    r"\.config\.",
    r"\.d\.ts$",
    r"^index\.",
)


def needs_test(file_path: str, filename: str, ext: str) -> bool:
    if ext not in SOURCE_EXT:
        return False
    norm = file_path.replace("\\", "/").lower()
    for part in SKIP_PATH_PARTS:
        if part.replace("\\", "/").lower() in norm:
            return False
    for pat in SKIP_FILENAME_PATTERNS:
        if re.search(pat, filename, re.IGNORECASE):
            return False
    return True


def find_sibling_test(file_path: str) -> bool:
    """Check if a sibling test file exists on disk."""
    p = Path(file_path)
    if not p.parent.exists():
        return False
    stem = p.stem
    parent = p.parent
    candidates = [
        parent / f"{stem}.test{p.suffix}",
        parent / f"{stem}.spec{p.suffix}",
        parent / "__tests__" / f"{stem}.test{p.suffix}",
        parent / "__tests__" / f"{stem}{p.suffix}",
        parent / f"test_{stem}.py",
        parent / "tests" / f"test_{stem}.py",
    ]
    # Walk up for test/ or tests/ dirs
    for ancestor in [parent, *parent.parents][:4]:
        for test_dir_name in ("tests", "test", "__tests__"):
            test_dir = ancestor / test_dir_name
            if test_dir.is_dir():
                for c in test_dir.rglob(f"*{stem}*"):
                    if c.is_file():
                        return True
    return any(c.exists() for c in candidates)


def session_wrote_test(transcript_path: str, target_stem: str) -> bool:
    """Check if a test file mentioning target_stem was Write|Edit'd in session."""
    if not transcript_path:
        return False
    for blk in iter_tool_calls(transcript_path):
        name = blk.get("name")
        if name not in ("Write", "Edit"):
            continue
        fp = (blk.get("input") or {}).get("file_path", "") or ""
        fp_norm = fp.replace("\\", "/").lower()
        if not fp:
            continue
        # Test file convention check
        is_test_file = any(
            marker in fp_norm
            for marker in (".test.", ".spec.", "_test.", "/test_", "__tests__", "/tests/")
        )
        if is_test_file and target_stem.lower() in fp_norm:
            return True
    return False


def main() -> None:
    _, data = read_hook_input()
    file_path = get_file_path(data)
    if not file_path:
        pass_through()

    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    ext = ext.lstrip(".").lower()

    if not needs_test(file_path, filename, ext):
        pass_through()

    if find_sibling_test(file_path):
        pass_through()

    stem = os.path.splitext(filename)[0]
    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    if session_wrote_test(transcript_path, stem):
        pass_through()

    warn(
        f"WARNING: TDG — no test found for {filename}. "
        "ACTION: Write a failing test FIRST (red), then implement (green). "
        "If this is intentional (refactor of tested code, prototype), continue. "
        "See rules/Quality.md 'Test-Driven Generation'."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
