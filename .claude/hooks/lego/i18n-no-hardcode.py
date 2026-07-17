#!/usr/bin/env python3
"""Lego Library hook: warn on hardcoded UI strings in JSX/TSX.

Trigger: PreToolUse Write|Edit on .tsx / .jsx
Detects: UI-facing literals that should come from @shinkofa/i18n.

Detection (conservative — minimize false positives):
- JSX text content: `>` then `>=3 words` then `<`
- Common props: placeholder=, title=, label=, aria-label=, alt=
  with a string literal of `>=3 words`.

Exits 1 with WARNING (non-blocking) — legitimate exceptions exist
(developer comments, internal tools, content-pages).

Reference: rules/Quality.md > @shinkofa/i18n.
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

SKIP_SEGMENTS: tuple[str, ...] = (
    "Shinkofa-Shared/packages/",
    "shinkofa-shared/packages/",
    "node_modules/",
    "__tests__/",
    ".storybook/",
    "/dist/",
    "/build/",
    "/docs/",
    "/content/",
)
SKIP_FILE_PATTERNS: tuple[str, ...] = (".test.", ".spec.", ".stories.")

# JSX text: between `>` and `<`. Multiline ok. We exclude `{` (expression) and
# `</` (closing tag).
_JSX_TEXT = re.compile(r">([^<>{}]{3,})<", re.DOTALL)

# Common UI props: prop="..."  or prop='...'  with >=3 words inside.
_UI_PROPS = ("placeholder", "title", "label", "aria-label", "alt")
_PROP_PATTERNS = [
    re.compile(
        rf'\b{p}\s*=\s*(?:"([^"]+)"|\'([^\']+)\')',
        re.IGNORECASE,
    )
    for p in _UI_PROPS
]

# Use of i18n / translation: presence implies the developer is i18n-aware.
_T_USE = re.compile(r"""\b(?:useTranslation|i18next|t\(\s*['"`])""")

# Word counter: a "word" is >=2 alphabetic chars; tokens like `{x}` ignored.
_WORD = re.compile(r"[A-Za-zÀ-ÿ]{2,}")


def _is_skipped(path: str) -> bool:
    norm = path.replace("\\", "/")
    if any(seg in norm for seg in SKIP_SEGMENTS):
        return True
    name = Path(norm).name
    return any(p in name for p in SKIP_FILE_PATTERNS)


def _word_count(text: str) -> int:
    return len(_WORD.findall(text))


def _harvest(content: str) -> list[str]:
    samples: list[str] = []
    for m in _JSX_TEXT.finditer(content):
        text = m.group(1).strip()
        if not text:
            continue
        if _word_count(text) >= 3:
            samples.append(text[:80])
    for pat in _PROP_PATTERNS:
        for m in pat.finditer(content):
            text = (m.group(1) or m.group(2) or "").strip()
            if _word_count(text) >= 3:
                samples.append(text[:80])
    return samples


def main() -> None:
    _, data = read_hook_input()
    path = get_file_path(data)
    if not path:
        pass_through()

    norm = path.replace("\\", "/")
    if not (norm.endswith(".tsx") or norm.endswith(".jsx")):
        pass_through()
    if _is_skipped(norm):
        pass_through()

    content = get_content(data)
    if not content:
        pass_through()

    samples = _harvest(content)
    if not samples:
        pass_through()

    # If the file already uses i18n, lower the strictness: only warn when
    # there are clearly multiple leaks (>=3 distinct samples).
    if _T_USE.search(content):
        unique = list(dict.fromkeys(samples))
        if len(unique) < 3:
            pass_through()
        samples = unique

    preview = " | ".join(samples[:3])
    warn(format_warn(
        reason=f"hardcoded UI text detected ({len(samples)} candidate(s)): {preview}",
        action="extract strings into @shinkofa/i18n keys (FR/EN/ES) and read "
               "via `useTranslation(namespace)`. If this file is internal/admin/"
               "content-page, add a path exception in the hook config.",
        reference="rules/Quality.md > @shinkofa/i18n",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
