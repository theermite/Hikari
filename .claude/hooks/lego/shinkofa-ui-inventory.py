#!/usr/bin/env python3
"""Lego Library hook: warn when redefining a @shinkofa/ui component locally.

Trigger: PreToolUse Write|Edit on .tsx / .jsx
Detects: a React component declaration whose name matches the @shinkofa/ui
inventory, written in a consumer project, without an import from
'@shinkofa/ui'. Exits 1 with a WARNING (non-blocking) — legitimate exceptions
exist (a project may need a thin wrapper; the library itself defines them).

Reference: rules/Quality.md > Shinkofa Lego Library.
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

# Inventory mirror — kept in sync with rules/Quality.md "@shinkofa/ui"
UI_COMPONENTS: frozenset[str] = frozenset({
    # Primitives
    "Button", "Input", "Textarea", "Badge", "Card", "Skeleton", "Modal", "EmptyState",
    # Shared interactive
    "ThemeProvider", "ThemeToggle", "BackToTop", "RevealOnScroll",
    "LanguageSwitcher", "CookieConsent",
    # Forms & input
    "TagInput", "DictationButton", "CollapsibleCard", "CollapsibleSection",
    "PromptDialog",
    # Feedback
    "SaveIndicator", "ConfirmModal",
    # Media
    "SafeImage",
    # BodyGraph
    "BodyGraph", "BodyGraphCenter", "BodyGraphChannel", "BodyGraphLegend",
    # SEO
    "StructuredData", "ArticleSchema", "BreadcrumbSchema", "FAQSchema",
    "ReviewSchema", "PortfolioSchema", "PortfolioItemSchema",
    "PortfolioListSchema", "ServiceSchema",
    # Planner
    "EnergySlider", "DayScore", "KiGauge", "KiBudgetGauges", "KiCheckIn",
    "SportTracker", "MealTracker", "TaskCard", "SleepTracker",
    # Dashboard
    "KiBudgetMini", "SleepSummaryCard", "EnergyTrendChart", "EnergyPixelMap",
    "TodayTasksList", "QuickActionGrid", "ProfileChipBar",
    # Toast
    "ToastProvider", "Toast",
    # FilePicker
    "FilePicker", "FilePickerUploadZone", "FilePickerBrowseGrid",
    "FilePickerPreview", "ImagePicker", "ImageBrowserModal",
    # Navigation
    "NavShell", "NavLink", "NavGroup",
    # Settings
    "SettingsSection", "RevealToggle", "PasswordChangeForm",
    # Avatar
    "AvatarUpload", "AvatarCropModal",
    # Questionnaire
    "QuestionRenderer", "ProgressTracker", "LoadingStepper", "PhaseCard",
    "LikertOptions", "SingleChoice", "MultiChoice", "OpenText",
    # Gaming
    "DodgeMaster", "SkillshotTrainer", "MultiTask", "ImagePairs",
})

# Paths exempt from this check
SKIP_SEGMENTS: tuple[str, ...] = (
    "Shinkofa-Shared/packages/",
    "shinkofa-shared/packages/",
    "node_modules/",
    "__tests__/",
    ".storybook/",
    "/dist/",
    "/build/",
)
SKIP_FILE_PATTERNS: tuple[str, ...] = (".test.", ".spec.", ".stories.")

# Declaration patterns — match function or const component of capitalized name
_DECL_PATTERNS = [
    # export function Foo(...) | export default function Foo(...)
    re.compile(r"\bexport\s+(?:default\s+)?function\s+([A-Z][A-Za-z0-9_]*)\s*\("),
    # function Foo(...) at top-level
    re.compile(r"^(?:\s{0,3})function\s+([A-Z][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    # const Foo = (...) => | const Foo: FC = (...) => | const Foo = React.forwardRef
    re.compile(
        r"\b(?:export\s+)?const\s+([A-Z][A-Za-z0-9_]*)\s*(?::\s*[^=]+)?=\s*"
        r"(?:React\.)?(?:forwardRef|memo|\(|<|function\b)"
    ),
]

_IMPORT_FROM_UI = re.compile(
    r"""from\s+['"]@shinkofa/ui['"]""",
    re.MULTILINE,
)


def _is_skipped(path: str) -> bool:
    norm = path.replace("\\", "/")
    if any(seg in norm for seg in SKIP_SEGMENTS):
        return True
    name = Path(norm).name
    return any(p in name for p in SKIP_FILE_PATTERNS)


def _declared_components(content: str) -> set[str]:
    names: set[str] = set()
    for pat in _DECL_PATTERNS:
        for m in pat.finditer(content):
            names.add(m.group(1))
    return names


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

    declared = _declared_components(content)
    matches = declared & UI_COMPONENTS
    if not matches:
        pass_through()

    if _IMPORT_FROM_UI.search(content):
        # File already imports from @shinkofa/ui — likely a wrapper, allow.
        pass_through()

    names = ", ".join(sorted(matches))
    warn(format_warn(
        reason=f"component(s) {names} match the @shinkofa/ui inventory "
               f"but the file does not import from '@shinkofa/ui'",
        action=f"prefer `import {{ {sorted(matches)[0]} }} from '@shinkofa/ui'`. "
               "If you intend to create a project-local variant, name it "
               "differently (e.g., AppButton) or add an import line.",
        reference="rules/Quality.md > Shinkofa Lego Library",
    ))
    # Non-blocking warning
    sys.exit(0)


if __name__ == "__main__":
    main()
