"""Checks that apply to UI source files: Lego duplication and hardcoded copy.

Split out of `write-guard.py` on 2026-09-04, which had reached its 500-line ceiling
with these four functions and their two tables inside. One concept per file: these are
the checks that read a `.tsx`/`.jsx` and judge what it SHOWS to a user, not what it
does to the machine. No rule changed in the move.
"""

import os
import re

LEGO_COMPONENTS = (
    "Button|Input|Textarea|Badge|Card|Skeleton|Modal|EmptyState|"
    "ThemeProvider|ThemeToggle|BackToTop|RevealOnScroll|LanguageSwitcher|"
    "CookieConsent|TagInput|DictationButton|CollapsibleCard|PromptDialog|"
    "SaveIndicator|ConfirmModal|SafeImage|BodyGraph|BodyGraphCenter|"
    "BodyGraphChannel|BodyGraphLegend|StructuredData|ArticleSchema|"
    "BreadcrumbSchema|FAQSchema|ReviewSchema|PortfolioSchema|"
    "PortfolioItemSchema|PortfolioListSchema|ServiceSchema|"
    "ToastProvider|Toast|"
    "FilePicker|FilePickerUploadZone|FilePickerBrowseGrid|"
    "FilePickerPreview|ImagePicker|ImageBrowserModal|"
    "NavShell|NavLink|NavGroup|"
    "SettingsSection|RevealToggle|PasswordChangeForm|"
    "AvatarUpload|AvatarCropModal|"
    "EnergySlider|DayScore|KiGauge|KiBudgetGauges|KiCheckIn|"
    "SportTracker|MealTracker|TaskCard|SleepTracker|"
    "KiBudgetMini|SleepSummaryCard|EnergyTrendChart|EnergyPixelMap|"
    "TodayTasksList|QuickActionGrid|ProfileChipBar|"
    "QuestionRenderer|ProgressTracker|LoadingStepper|PhaseCard|"
    "CollapsibleSection|LikertOptions|SingleChoice|MultiChoice|OpenText|"
    "DodgeMaster|SkillshotTrainer|MultiTask|ImagePairs"
)

# Generated / vendored / test material: a Lego duplicate or a hardcoded string
# there is not the defect these checks exist to catch.
UI_SKIP_PATTERNS = (
    "Shinkofa-Shared/", "node_modules/", ".test.", ".spec.",
    ".stories.", "__tests__", ".claude/",
)


def _skips_ui_check(file_path, ext):
    if ext not in ("tsx", "jsx"):
        return True
    return any(p in file_path for p in UI_SKIP_PATTERNS)


def _lego_exempt():
    """True when this repo documents a Lego exemption in `.claude/rules/Lego-Hikari.md`.

    Driven by the rule FILE, never hardcoded: an exemption living only in the guard would
    drift from its written reasons. No file, no exemption — every other project is unaffected.
    """
    # This file sits in `.claude/hooks/guards/`, so the rules live THREE levels up, not
    # two. A first attempt looked in `.claude/hooks/rules/` — a directory that does not
    # exist — and the exemption silently never applied while the guard kept blocking.
    here = os.path.abspath(__file__)
    dot_claude = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.isfile(os.path.join(dot_claude, "rules", "Lego-Hikari.md"))


def check_lego_library(file_path, ext, content):
    if _skips_ui_check(file_path, ext):
        return None
    pattern = rf"(export )?(function|const) ({LEGO_COMPONENTS})[^a-zA-Z]"
    match = re.search(pattern, content)
    if not match:
        return None
    comp_name_match = re.search(rf"({LEGO_COMPONENTS})", match.group(0))
    if not comp_name_match:
        return None
    comp = comp_name_match.group(1)
    if _lego_exempt():
        # A WARNING, never a silent pass: the name collision stays visible, so a component
        # copied from the library keeps being noticed and attributed.
        return (
            f"WARNING: '{comp}' also exists in @shinkofa/ui; this project is exempt "
            "(GPL + public repo — see .claude/rules/Lego-Hikari.md). ACTION: write it "
            "locally, or copy the library source WITH its provenance and licence line. "
            "Never add the package as a dependency."
        )
    return (
        f"BLOCKED: '{comp}' already exists in @shinkofa/ui. "
        "RECOVERY: Import from @shinkofa/ui instead of redefining "
        "(e.g. `import { " + comp + " } from '@shinkofa/ui'`). "
        "NEVER duplicate a Lego component. See rules/Quality.md Lego Library."
    )


def check_i18n_hardcoded(file_path, ext, content):
    if _skips_ui_check(file_path, ext):
        return None
    messages = []
    if re.search(r'(title|placeholder|aria-label|alt)="[A-Z][a-zA-Z ]{3,}"', content):
        messages.append(
            "WARNING: Hardcoded user-facing string in JSX attribute. "
            "ACTION: Replace with @shinkofa/i18n key via labels prop pattern."
        )
    if re.search(r">[A-Z][a-zA-Z ]{3,}<", content):
        messages.append(
            "WARNING: Hardcoded user-facing text in JSX. "
            "ACTION: Replace with {t('namespace:key')} from @shinkofa/i18n."
        )
    return "\n".join(messages) if messages else None
