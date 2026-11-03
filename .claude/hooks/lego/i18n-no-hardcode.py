#!/usr/bin/env python3
"""Lego Library hook: hardcoded UI text in JSX/TSX is REFUSED where the project has an i18n library.

Trigger: PreToolUse Write|Edit on .tsx / .jsx
Detects: UI-facing literals that should come from @shinkofa/i18n — JSX text content of >=3 words (right after an
opening tag) and the usual UI props (placeholder, title, label, aria-label, alt) set to a literal of >=3 words.

Blocks when the project declares an i18n library (@shinkofa/i18n, next-intl, react-i18next, i18next — in this or
any parent package.json up to the repo root). Warns otherwise: refusing every interface edit in a project that has
no translation library installed would make the guard unusable, and an unplugged guard guards nothing.

Why it blocks (Jay 2026-10-30): measured 362 of 3 695 UI files carrying raw text despite a warning — and the
warning never reached the model (see lib/common.py `warn`). A reminder nobody acts on is not a rule.

Way out, closed list: a comment `// I18N-OK: <motif>` (or `{/* I18N-OK: <motif> */}`) in the new text OR already in
the file, motif one of MOTIFS. An open motif becomes « pas le temps » within a week.

Reference: rules/Quality.md > @shinkofa/i18n.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    format_block,
    format_warn,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)

SKIP_SEGMENTS: tuple[str, ...] = (
    "Shinkofa-Shared/packages/",
    "shinkofa-shared/packages/",
    "Toolbox/typescript/packages/",
    "toolbox/typescript/packages/",
    "node_modules/",
    "__tests__/",
    ".storybook/",
    "/dist/",
    "/build/",
    "/docs/",
    "/content/",
    "/mock/",
    "/mocks/",
    "/mockups/",
)
# A mockup shows invented content on purpose: a translated key there would only hide the mockup.
SKIP_FILE_PATTERNS: tuple[str, ...] = (".test.", ".spec.", ".stories.", "mock-")

I18N_LIBRARIES: tuple[str, ...] = ("@shinkofa/i18n", "next-intl", "react-i18next", "i18next", "next-i18next",
                                   "react-intl", "@formatjs/intl", "@lingui/core", "@lingui/react")
MOTIFS: tuple[str, ...] = ("internal-tool", "editorial-content", "already-translated")
_ESCAPE = re.compile(r"(?://|/\*)[ \t]*I18N-OK:[ \t]*(?P<motif>[a-z-]+)\b", re.IGNORECASE)

# JSX text: right after an OPENING tag (`<p>texte<`), so a comparison like `a > b && c < d` is never read as text.
# Not a generic (`useState<Row[]>(…)`: the `<` follows an identifier) and not a self-closing tag (`<Foo />`).
# `{name}` inside the text is part of the sentence (« Bonjour {name}, bienvenue… »): braces are allowed one level deep.
_JSX_TEXT = re.compile(r"(?<![\w$])<[A-Za-z][^<>]*?(?<!/)>((?:[^<>{}]|\{[^{}]*\}){3,})<", re.DOTALL)
_EXPRESSION = re.compile(r"\{[^{}]*\}")
_ENTITY = re.compile(r"&#?\w+;")
# What code looks like and prose does not: an assignment, a statement end, an arrow.
_CODE_CHARS = re.compile(r"[;=]")

# Common UI props, only inside a tag: `const title = "..."` is code, not interface text.
_UI_PROPS = ("placeholder", "title", "label", "aria-label", "alt")
_PROP_PATTERNS = [
    re.compile(rf'(?<![\w$])<[A-Za-z][^<>]*?\b{p}\s*=\s*(?:"([^"]+)"|\'([^\']+)\')', re.IGNORECASE)
    for p in _UI_PROPS
]

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
        text = _EXPRESSION.sub(" ", _ENTITY.sub(" ", m.group(1))).strip()
        if text and _word_count(text) >= 3 and not _CODE_CHARS.search(text):
            samples.append(text[:80])
    for pat in _PROP_PATTERNS:
        for m in pat.finditer(content):
            text = (m.group(1) or m.group(2) or "").strip()
            if _word_count(text) >= 3:
                samples.append(text[:80])
    return list(dict.fromkeys(samples))


def _declares_i18n(manifest: Path) -> bool:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    wanted = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})} if isinstance(data, dict) else {}
    return any(lib in wanted for lib in I18N_LIBRARIES)


def _project_uses_i18n(path: Path) -> bool:
    """True when this package.json or any parent one, up to the repo root (`.git`), declares an i18n library."""
    for folder in list(path.parents)[:12]:
        if _declares_i18n(folder / "package.json"):
            return True
        if (folder / ".git").exists():
            return False
    return False


def _has_motif(text: str) -> bool:
    return any(m.group("motif").lower() in MOTIFS for m in _ESCAPE.finditer(text))


def _escaped(content: str, path: Path) -> bool:
    """The motif is in the new text, or already in the file being edited."""
    if _has_motif(content):
        return True
    try:
        return _has_motif(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def _refusal(samples: list[str]) -> str:
    return format_block(
        reason=f"hardcoded UI text in a project that has an i18n library ({len(samples)} candidate(s): "
               f"{' | '.join(samples[:3])})",
        recovery="extract the text into @shinkofa/i18n keys (FR source, EN, ES) and read it via "
                 "`useTranslation(namespace)`. If the file is not user-facing text, add `// I18N-OK: <motif>` "
                 f"(or `{{/* I18N-OK: <motif> */}}`) with motif one of: {' | '.join(MOTIFS)}",
        reference="rules/Quality.md > @shinkofa/i18n",
    )


def _changes(data: dict) -> list[tuple[str, str]]:
    """(new text, old text) for each change the tool makes: Write has no old text, Edit and MultiEdit do."""
    tool_input = data.get("tool_input") or {}
    edits = tool_input.get("edits") if isinstance(tool_input.get("edits"), list) else [tool_input]
    return [(str(e.get("content") or e.get("new_string") or ""), str(e.get("old_string") or ""))
            for e in edits if isinstance(e, dict)]


def _new_samples(changes: list[tuple[str, str]]) -> list[str]:
    """The raw text the whole change ADDS: what was already in ANY old text is not the writer's doing (a class edit on a
    line that already carries text, or a MultiEdit that moves a sentence, must not force an extraction)."""
    known = {sample for _, old in changes if old for sample in _harvest(old)}
    found = [sample for new, _ in changes if new for sample in _harvest(new) if sample not in known]
    return list(dict.fromkeys(found))


def main() -> None:
    _, data = read_hook_input()
    path = get_file_path(data)
    norm = path.replace("\\", "/")
    if not (norm.endswith(".tsx") or norm.endswith(".jsx")) or _is_skipped(norm):
        pass_through()
    changes = _changes(data)
    samples = _new_samples(changes)
    if not samples or any(_escaped(new, Path(norm)) for new, _ in changes if new):
        pass_through()
    if _project_uses_i18n(Path(norm)):
        block(_refusal(samples))
    warn(format_warn(
        reason=f"hardcoded UI text detected ({len(samples)} candidate(s)): {' | '.join(samples[:3])}",
        action="this project has no i18n library yet: install @shinkofa/i18n and read the text via "
               "`useTranslation(namespace)`, or add `// I18N-OK: <motif>` if the file is not user-facing text.",
        reference="rules/Quality.md > @shinkofa/i18n",
    ))
    sys.exit(0)


if __name__ == "__main__":
    main()
