"""Configuration shared by the veille / SKB evidence guards.

Extracted from guards/pre-code-veille-check.py on 2026-08-18 (the file had
grown to 634 lines, above the 500-line BLOCKING limit it helps enforce).
Values are unchanged — this module holds data, no behaviour.

Stdlib only. Cross-platform (Windows + Linux).
"""

from __future__ import annotations

import re
import sys

CODE_EXT = {"ts", "tsx", "js", "jsx", "py", "ex", "exs", "rs", "go"}

# Paths that do NOT require veille evidence
SKIP_PATH_PARTS = (
    "/.claude/",
    "/node_modules/",
    "/dist/",
    "/build/",
    "/.next/",
    "/__pycache__/",
    "/coverage/",
    "/.venv/",
    "/venv/",
    "/target/",
    "/_build/",
    "/deps/",
    "/docs/",
    "/mnk/",
    "/rules/",
    "/__tests__/",
)

# Filename patterns that do NOT require veille evidence.
# Test files legitimately import the framework (pytest, vitest) and the module
# under test — both may be external — so they are exempt by design, like a
# `[VEILLE-SKIP] motif: test-only`. Covers .test./.spec. plus the pytest naming
# conventions test_*.py / test-*.py / *_test.py (Jay 2026-06-24 friction).
SKIP_FILENAME_PATTERNS = (
    r"\.test\.",
    r"\.spec\.",
    r"\.stories\.",
    r"__tests__",
    r"conftest\.py",
    r"setup\.py",
    r"setup\.cfg",
    r"^test_",
    r"^test-",
    r"_test\.py$",
)

# Layer A — closed enum of acceptable SKIP motifs
ALLOWED_SKIP_MOTIFS = {
    "typo",
    "internal-refactor-no-new-deps",
    "hotfix-known-root-cause",
    "test-only",
    "methodology-edit",
    "generated-artifact",
}

# Layer B — dependency manifest filenames
DEPENDENCY_MANIFESTS = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "Pipfile.lock",
    "mix.exs",
    "mix.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
}

# Layer B — version pin patterns (caught on new diff lines)
VERSION_PIN_RE = re.compile(
    r"""
    (?: @ \d+\.\d+(?:\.\d+)? )            # @1.2.3 npm scoped
  | (?: \^ \d+\.\d+ )                     # ^1.2
  | (?: ~= ?\d+\.\d+ )                    # ~= 1.2
  | (?: ~> ?\d+\.\d+ )                    # ~> 1.2 (mix.exs)
  | (?: >= ?\d+\.\d+(?:,\s*<\s*\d+)? )    # >=1.2,<2 (Python)
    """,
    re.VERBOSE,
)

# Python stdlib names (3.10+ exposes sys.stdlib_module_names)
PY_STDLIB = set(getattr(sys, "stdlib_module_names", ()))

# Marker scan. The prefix class accepts a backtick so a marker wrapped in
# markdown code-span backticks (`[VEILLE-SKIP] motif: typo`) is still detected
# (Jay 2026-06-13, session 004 — backtick-wrapped marker silently missed).
MARKER_RE = re.compile(
    r"(?:^|[\s`])\[(VEILLE|SKB|VEILLE-SKIP)\][^\n]+",
    re.MULTILINE,
)
SKIP_MOTIF_RE = re.compile(
    r"\[VEILLE-SKIP\]\s+motif\s*:\s*([a-zA-Z0-9_\-]+)",
)
TRANSCRIPT_SCAN_LIMIT = 200
SKIP_COUNT_THRESHOLD = 3

# Lines that are clearly our own recovery / block messages — never scan them
# for markers (otherwise the hook re-matches its own template strings and
# produces cascading false blocks). Jay 2026-05-31 bug report.
RECOVERY_LINE_HINTS = ("BLOCKED:", "RECOVERY:")

# Chantier D — proof of web veille. A [VEILLE] marker on a SENSITIVE change
# must be backed by a REAL web tool call in the session, not just the text.
# Match known web tools by exact name + substring (alias-tolerant per the
# 2026-06-08 cross-project lesson: never bind to a single literal tool name).
WEB_TOOL_NAMES_EXACT = {"WebSearch", "WebFetch"}
WEB_TOOL_SUBSTRINGS = (
    "websearch", "web_search", "webfetch", "web_fetch",
    "searxng", "tavily", "brave",
)
