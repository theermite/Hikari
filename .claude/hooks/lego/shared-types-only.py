#!/usr/bin/env python3
"""Lego Library hook: warn on local redefinition of @shinkofa/types models.

Trigger: PreToolUse Write|Edit on .ts / .tsx
Detects: a `type Foo = ...` or `interface Foo { ... }` declaration whose
identifier matches the @shinkofa/types shared inventory, without an
`import ... from '@shinkofa/types'` in the same file.

Exits 1 with WARNING (non-blocking) — legitimate exceptions exist (the
shared package itself, internal extensions named with a project prefix).

Reference: rules/Quality.md > @shinkofa/types.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    format_warn,
    get_content,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)

# Shared type names that MUST come from @shinkofa/types.
SHARED_TYPES: frozenset[str] = frozenset({
    "Ki",
    "Task",
    "Priority",
    "Wellness",
    "EnergyLevel",
    "TaskStatus",
    "TaskCategory",
    "KiBudget",
    "SleepEntry",
    "MealEntry",
    "SportEntry",
    "UserProfile",
    "Theme",
    "Locale",
})

SKIP_SEGMENTS: tuple[str, ...] = (
    "Shinkofa-Shared/packages/",
    "shinkofa-shared/packages/",
    "node_modules/",
    "__tests__/",
    "/dist/",
    "/build/",
)
SKIP_FILE_PATTERNS: tuple[str, ...] = (".test.", ".spec.", ".d.ts")

_DECL_TYPE = re.compile(r"\b(?:export\s+)?type\s+([A-Z][A-Za-z0-9_]*)\s*=")
_DECL_INTERFACE = re.compile(r"\b(?:export\s+)?interface\s+([A-Z][A-Za-z0-9_]*)\b")
_IMPORT_FROM_TYPES = re.compile(r"""from\s+['"]@shinkofa/types['"]""")


def _is_skipped(path: str) -> bool:
    norm = path.replace("\\", "/")
    if any(seg in norm for seg in SKIP_SEGMENTS):
        return True
    name = Path(norm).name
    return any(p in name for p in SKIP_FILE_PATTERNS)


def _declared_names(content: str) -> set[str]:
    names: set[str] = set()
    for m in _DECL_TYPE.finditer(content):
        names.add(m.group(1))
    for m in _DECL_INTERFACE.finditer(content):
        names.add(m.group(1))
    return names


def main() -> None:
    _, data = read_hook_input()
    path = get_file_path(data)
    if not path:
        pass_through()

    norm = path.replace("\\", "/")
    if not (norm.endswith(".ts") or norm.endswith(".tsx")):
        pass_through()
    if _is_skipped(norm):
        pass_through()

    content = get_content(data)
    if not content:
        pass_through()

    declared = _declared_names(content)
    matches = declared & SHARED_TYPES
    if not matches:
        pass_through()

    if _IMPORT_FROM_TYPES.search(content):
        pass_through()

    names = ", ".join(sorted(matches))
    first = sorted(matches)[0]
    warn(format_warn(
        reason=f"shared type name(s) redeclared locally: {names}",
        action=f"import from the shared package instead: "
               f"`import type {{ {first} }} from '@shinkofa/types'`. "
               "If you need a project-local variant, prefix the name "
               "(e.g., AppTask) to avoid drift.",
        reference="rules/Quality.md > @shinkofa/types",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
