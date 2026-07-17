#!/usr/bin/env python3
"""Unified Write|Edit PreToolUse guard — all checks in one script.

RECOVERY PRINCIPLE: Every BLOCKED/WARNING message MUST include
a concrete recovery action so Takumi knows what to do next.
"""

import json
import os
import re
import sys


def read_input():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    return raw, data


def get_file_info(data):
    file_path = data.get("file_path", "")
    if not file_path:
        return None, None, None, None
    file_path = file_path.replace("\\\\", "/").replace("\\", "/")
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    ext = ext.lstrip(".")
    dirname = os.path.dirname(file_path)
    return file_path, filename, name, ext, dirname


def get_content(data):
    return data.get("new_string", "") or data.get("content", "")


def check_env_guard(filename, dirname):
    if filename in (".env", ".env.local", ".env.production", ".env.prod"):
        example = os.path.join(dirname, ".env.example")
        if not os.path.isfile(example):
            return (
                f"BLOCKED: .env.example must exist alongside {filename}. "
                f"RECOVERY: Create {dirname}/.env.example with placeholder values "
                "(no real secrets), then retry this write."
            )
    return None


def check_localstorage_jwt(raw):
    if re.search(r"localStorage\.(set|get)Item.*(token|jwt|auth|session)", raw, re.IGNORECASE):
        return (
            "BLOCKED: JWT tokens must use httpOnly cookies, not localStorage. "
            "RECOVERY: Replace localStorage with httpOnly cookie-based auth "
            "(set via backend Set-Cookie header). See rules/Security.md."
        )
    return None


def check_secrets_in_files(raw):
    # Order matters: more specific patterns first so the BLOCKED message
    # names the right provider. Generic `sk-` (OpenAI/DeepSeek) is intentionally
    # placed AFTER `sk-ant-` (Anthropic) so Anthropic keys don't get mislabeled.
    patterns = [
        # Existing
        (r"sk_live_[a-zA-Z0-9]{10,}", "Stripe live key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub token"),
        # AWS
        (r"AKIA[0-9A-Z]{16}", "AWS access key"),
        (r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS secret access key"),
        # Anthropic (must come BEFORE generic sk- catchall)
        (r"sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}", "Anthropic API key"),
        # OpenAI (project keys: sk-proj-..., legacy: sk-<48+>)
        (r"sk-proj-[A-Za-z0-9_\-]{40,}", "OpenAI API key"),
        (r"sk-[A-Za-z0-9]{40,}", "OpenAI/DeepSeek API key"),
        # Groq
        (r"gsk_[A-Za-z0-9]{50,}", "Groq API key"),
        # Slack
        (r"xox[baprs]-[A-Za-z0-9\-]{10,}-[A-Za-z0-9\-]{10,}", "Slack token"),
        # Generic private keys (RSA, OpenSSH, EC, DSA, PGP)
        (r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY( BLOCK)?-----", "Private key"),
        (r"PRIVATE KEY", "Private key"),  # fallback for fragments
    ]
    for pattern, name in patterns:
        if re.search(pattern, raw):
            return (
                f"BLOCKED: {name} detected in code. "
                "RECOVERY: Move to .env file, reference via environment variable, then retry."
            )
    return None


def check_github_actions_sha(file_path, raw):
    if re.search(r"\.github/workflows/.*\.yml$", file_path):
        if re.search(r"uses:.*@(v[0-9]|main|master|latest)", raw):
            return (
                "BLOCKED: GitHub Actions must be pinned to SHA, not tags. "
                "RECOVERY: Find the full commit SHA for the action version on GitHub, "
                "replace the tag with the SHA, then retry."
            )
    return None


def check_stack_versions(filename, content):
    if filename in ("package.json", "requirements.txt", "pyproject.toml"):
        if re.search(r'"[a-z@][^"]*"\s*:\s*"[\^~]?[0-9]+\.[0-9]+', content):
            return (
                f"WARNING: Dependency versions in {filename} detected. "
                "ACTION: Verify versions via npm/pypi/web (training data is months stale). "
                "If already verified, continue."
            )
    if filename.startswith("Dockerfile"):
        if re.search(r"FROM .+:[0-9]+", content):
            return (
                f"WARNING: Docker image version in {filename} detected. "
                "ACTION: Verify version via Docker Hub. If already verified, continue."
            )
    return None


def check_lego_library(file_path, ext, content):
    if ext not in ("tsx", "jsx"):
        return None
    skip_patterns = (
        "Shinkofa-Shared/", "node_modules/", ".test.", ".spec.",
        ".stories.", "__tests__", ".claude/",
    )
    if any(p in file_path for p in skip_patterns):
        return None
    lego_components = (
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
    pattern = rf"(export )?(function|const) ({lego_components})[^a-zA-Z]"
    match = re.search(pattern, content)
    if match:
        comp_name_match = re.search(rf"({lego_components})", match.group(0))
        if comp_name_match:
            comp = comp_name_match.group(1)
            return (
                f"BLOCKED: '{comp}' already exists in @shinkofa/ui. "
                "RECOVERY: Import from @shinkofa/ui instead of redefining "
                "(e.g. `import { " + comp + " } from '@shinkofa/ui'`). "
                "NEVER duplicate a Lego component. See rules/Quality.md Lego Library."
            )
    return None


def check_i18n_hardcoded(file_path, ext, content):
    if ext not in ("tsx", "jsx"):
        return None
    skip_patterns = (
        "Shinkofa-Shared/", "node_modules/", ".test.", ".spec.",
        ".stories.", "__tests__", ".claude/",
    )
    if any(p in file_path for p in skip_patterns):
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


def check_hs256(ext, content, file_path=""):
    check_exts = ("ts", "js", "py", "tsx", "jsx", "env", "yaml", "yml")
    if ext not in check_exts:
        return None
    if re.search(r"\bHS256\b", content):
        return (
            "BLOCKED: HS256 algorithm detected. Use RS256 or ES256 for JWT. "
            "RECOVERY: Replace HS256 with RS256 or ES256. See rules/Security.md."
        )
    return None


def check_bare_except(ext, content, file_path=""):
    """Detect swallowed exceptions: except/catch blocks with no logging."""
    critical_paths = (
        "/auth/", "/authentication/", "/authorization/", "/payment/",
        "/payments/", "/billing/", "/crypto/", "/encryption/",
        "/security/", "/sessions/",
    )
    is_critical = any(p in file_path.lower() for p in critical_paths)

    if ext == "py":
        # except: pass, except Exception: pass, except Exception as e: pass
        if re.search(r"except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*\n\s*(pass|\.\.\.)\s*$", content, re.MULTILINE):
            level = "BLOCKED" if is_critical else "WARNING"
            return (
                f"{level}: Swallowed exception (except/pass) detected. "
                "RECOVERY: Log the exception at appropriate level "
                "(WARNING for critical path errors, DEBUG for expected fallbacks). "
                "Never silently swallow exceptions — they are debugging data."
            )
    elif ext in ("ts", "js", "tsx", "jsx"):
        # catch {}, catch (e) {}, catch (_) {}
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", content):
            level = "BLOCKED" if is_critical else "WARNING"
            return (
                f"{level}: Empty catch block detected. "
                "RECOVERY: Log the error or handle it explicitly. "
                "Never silently swallow exceptions — they are debugging data."
            )
    return None


def check_type_suppression(ext, content):
    """Detect @ts-ignore, @ts-nocheck, # type: ignore — bypasses compiler poka-yoke."""
    if ext in ("ts", "tsx"):
        if re.search(r"@ts-ignore|@ts-nocheck", content):
            return (
                "WARNING: Type suppression (@ts-ignore/@ts-nocheck) detected. "
                "This bypasses the compiler poka-yoke. "
                "ACTION: Fix the type error instead of suppressing it. "
                "If genuinely unavoidable, add a comment explaining why."
            )
    elif ext == "py":
        if re.search(r"#\s*type:\s*ignore", content):
            return (
                "WARNING: Type suppression (# type: ignore) detected. "
                "This bypasses the compiler poka-yoke. "
                "ACTION: Fix the type error instead of suppressing it."
            )
    return None


def check_weak_hash(ext, content):
    if ext not in ("ts", "js", "py", "tsx", "jsx"):
        return None
    patterns = [
        (r"createHash\s*\(\s*[\"']md5", "MD5"),
        (r"createHash\s*\(\s*[\"']sha1", "SHA1"),
        (r"hashlib\.md5", "MD5"),
        (r"hashlib\.sha1", "SHA1"),
    ]
    for pattern, name in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return (
                f"BLOCKED: Weak hash ({name}) detected. "
                "RECOVERY: Use Argon2id for passwords, SHA-256+ for integrity. "
                "See rules/Security.md."
            )
    return None


def check_hook_protection(file_path):
    if ".claude/hooks/" in file_path.replace("\\", "/"):
        return (
            "WARNING: Modifying hook files requires careful review. "
            "ACTION: Test the hook with edge cases before committing."
        )
    return None


def check_uuidv7(file_path, content):
    if not re.search(r"(migration|schema|seed)", file_path, re.IGNORECASE):
        return None
    if re.search(r"uuid_generate_v4|gen_random_uuid|uuid4", content):
        return (
            "WARNING: Use uuidv7() instead of uuid v4 for PostgreSQL IDs. "
            "ACTION: Replace with uuidv7() for sortable, performant IDs."
        )
    return None


def check_tkinter(ext, content):
    if ext != "py":
        return None
    if re.search(r"import tkinter|from tkinter", content):
        return (
            "BLOCKED: tkinter is forbidden. Use PySide6 for desktop apps. "
            "RECOVERY: Replace tkinter imports with PySide6. "
            "See rules/Conventions.md."
        )
    return None


def check_naming(file_path, filename, name, ext):
    exceptions = {
        "README.md", "LICENSE", "CHANGELOG.md", "CLAUDE.md", "SKILL.md",
        "MEMORY.md", "Makefile", ".gitignore", ".gitkeep",
    }
    if filename in exceptions:
        return None
    if filename.startswith(("Dockerfile", ".env", "index.")):
        return None
    if filename.endswith(".lock"):
        return None
    config_patterns = (
        "package.json", "tsconfig.json", "biome.json",
        "vitest.config.", "playwright.config.", "next.config.",
        "tailwind.config.", "postcss.config.",
    )
    if any(filename.startswith(p.split(".")[0]) and p.split(".")[-1] in filename for p in config_patterns):
        return None
    skip_dirs = (".claude/", ".github/", "node_modules/", ".next/", "__pycache__", ".obsidian/", ".vscode/")
    if any(d in file_path for d in skip_dirs):
        return None
    conventions = {
        "py": (r"^[a-z][a-z0-9_]*$", "snake_case"),
        "sh": (r"^[a-z][a-z0-9-]*$", "kebab-case"),
        "ts": (r"^[a-z][a-zA-Z0-9]*$", "camelCase"),
        "js": (r"^[a-z][a-zA-Z0-9]*$", "camelCase"),
        "tsx": (r"^[A-Z][a-zA-Z0-9]*$", "PascalCase"),
        "jsx": (r"^[A-Z][a-zA-Z0-9]*$", "PascalCase"),
    }
    if ext in conventions:
        pattern, convention = conventions[ext]
        if not re.match(pattern, name):
            return (
                f"WARNING: {ext.upper()} files should use {convention}: {filename}. "
                f"ACTION: Rename to {convention} and update imports, then retry."
            )
    if ext == "md":
        parent = os.path.basename(os.path.dirname(file_path))
        if parent not in ("agents", "skills", "hooks"):
            if not re.match(r"^[A-Z][a-zA-Z0-9]*(-[A-Z][a-zA-Z0-9]*)*$", name):
                return (
                    f"WARNING: Markdown docs should use Title-Kebab-Case: {filename}. "
                    "ACTION: Rename to Title-Kebab-Case (e.g., My-Document.md), then retry."
                )
    return None


def main():
    raw, data = read_input()
    info = get_file_info(data)
    if info is None:
        sys.exit(0)
    file_path, filename, name, ext, dirname = info
    content = get_content(data)

    blockers = [
        check_env_guard(filename, dirname),
        check_localstorage_jwt(raw),
        check_secrets_in_files(raw),
        check_github_actions_sha(file_path, raw),
        check_lego_library(file_path, ext, content),
        check_hs256(ext, content, file_path),
        check_weak_hash(ext, content),
        check_tkinter(ext, content),
        check_bare_except(ext, content, file_path),
    ]
    for msg in blockers:
        if msg:
            print(msg, file=sys.stderr)
            sys.exit(2)

    warnings = [
        check_stack_versions(filename, content),
        check_i18n_hardcoded(file_path, ext, content),
        check_naming(file_path, filename, name, ext),
        check_hook_protection(file_path),
        check_uuidv7(file_path, content),
        check_type_suppression(ext, content),
    ]
    for msg in warnings:
        if msg:
            print(msg, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
