"""Contrôle d'interface du garde d'écriture : un composant déjà dans @shinkofa/ui (le texte en dur est jugé par `lego/i18n-no-hardcode.py`).

Sortis de `guards/write-guard.py` le 2026-10-30 (le fichier passait la limite de 500 lignes).
"""

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
    return (
        f"BLOCKED: '{comp}' already exists in @shinkofa/ui. "
        "RECOVERY: Import from @shinkofa/ui instead of redefining "
        "(e.g. `import { " + comp + " } from '@shinkofa/ui'`). "
        "NEVER duplicate a Lego component. See rules/Quality.md Lego Library."
    )
