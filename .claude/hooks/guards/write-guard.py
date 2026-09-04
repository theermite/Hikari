#!/usr/bin/env python3
"""Unified Write|Edit PreToolUse guard — all checks in one script.

RECOVERY PRINCIPLE: Every BLOCKED/WARNING message MUST include
a concrete recovery action so Takumi knows what to do next.

2026-08-07 — this guard had never blocked anything. Two defects compounding:
`get_file_info` read `data["file_path"]` at the top level while the harness
nests it under `tool_input`, so the path was always empty; and the empty branch
returned a 4-tuple where `main` unpacks 5, which raised a ValueError before any
check ran. Every rule below was therefore hook-enforced in name only. Covered
now by end-to-end tests in `tests/test_write_guard.py` — a unit test on a check
function cannot catch a guard that dies before calling it.

The long pattern tables live at module level rather than inside their checks:
they are data, and keeping them out of the functions is what lets each one stay
readable (Quality.md, Maintainability).
"""

import json
import os
import re
import sys

from ui_checks import check_i18n_hardcoded, check_lego_library


# Order matters: more specific patterns first so the BLOCKED message names the
# right provider. Generic `sk-` (OpenAI/DeepSeek) sits AFTER `sk-ant-`
# (Anthropic) so Anthropic keys are not mislabeled.
SECRET_PATTERNS = [
    (r"sk_live_[a-zA-Z0-9]{10,}", "Stripe live key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS secret access key"),
    (r"sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}", "Anthropic API key"),
    (r"sk-proj-[A-Za-z0-9_\-]{40,}", "OpenAI API key"),
    (r"sk-[A-Za-z0-9]{40,}", "OpenAI/DeepSeek API key"),
    (r"gsk_[A-Za-z0-9]{50,}", "Groq API key"),
    (r"xox[baprs]-[A-Za-z0-9\-]{10,}-[A-Za-z0-9\-]{10,}", "Slack token"),
    (r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY( BLOCK)?-----", "Private key"),
    (r"PRIVATE KEY", "Private key"),  # fallback for fragments
]

WEAK_HASH_PATTERNS = [
    (r"createHash\s*\(\s*[\"']md5", "MD5"),
    (r"createHash\s*\(\s*[\"']sha1", "SHA1"),
    (r"hashlib\.md5", "MD5"),
    (r"hashlib\.sha1", "SHA1"),
]

# A file that SHOWS a forbidden pattern is not doing it: a security test asserts
# on a fake key, a doc teaches the counter-example. Blocking those blocks exactly
# the files that document the rule (independent review, 2026-08-11 — the day this
# guard came back to life and blocked its own test file).
EXAMPLE_PATTERNS = (".test.", ".spec.", "__tests__", "/tests/", ".stories.")
DOC_PATTERNS = (".md", "/docs/")


def _is_example_file(file_path):
    return any(p in file_path.lower() for p in EXAMPLE_PATTERNS)


def _teaches_rather_than_runs(file_path):
    """Test fixtures AND documentation: both quote patterns to explain them."""
    lowered = file_path.lower()
    return _is_example_file(file_path) or any(p in lowered for p in DOC_PATTERNS)


NAMING_EXCEPTIONS = {
    "README.md", "LICENSE", "CHANGELOG.md", "CLAUDE.md", "SKILL.md",
    "MEMORY.md", "Makefile", ".gitignore", ".gitkeep",
}

NAMING_CONFIG_PATTERNS = (
    "package.json", "tsconfig.json", "biome.json",
    "vitest.config.", "playwright.config.", "next.config.",
    "tailwind.config.", "postcss.config.",
)

NAMING_SKIP_DIRS = (
    ".claude/", ".github/", "node_modules/", ".next/", "__pycache__",
    ".obsidian/", ".vscode/",
)

NAMING_CONVENTIONS = {
    "py": (r"^[a-z][a-z0-9_]*$", "snake_case"),
    "sh": (r"^[a-z][a-z0-9-]*$", "kebab-case"),
    "ts": (r"^[a-z][a-zA-Z0-9]*$", "camelCase"),
    "js": (r"^[a-z][a-zA-Z0-9]*$", "camelCase"),
    "tsx": (r"^[A-Z][a-zA-Z0-9]*$", "PascalCase"),
    "jsx": (r"^[A-Z][a-zA-Z0-9]*$", "PascalCase"),
}

CRITICAL_PATHS = (
    "/auth/", "/authentication/", "/authorization/", "/payment/",
    "/payments/", "/billing/", "/crypto/", "/encryption/",
    "/security/", "/sessions/",
)


def read_input():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    return raw, data


def _tool_input(data):
    """The payload the harness nests under `tool_input`.

    The flat shape stays as a fallback so an older caller (or a manual
    invocation) keeps working.
    """
    nested = data.get("tool_input")
    return nested if isinstance(nested, dict) else data


def get_file_info(data):
    file_path = _tool_input(data).get("file_path", "") or ""
    if not file_path:
        # `None`, never a tuple of Nones: the caller tests `info is None`, and a
        # 4-tuple is truthy — which is how the arity mismatch stayed invisible.
        return None
    file_path = file_path.replace("\\\\", "/").replace("\\", "/")
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    ext = ext.lstrip(".")
    dirname = os.path.dirname(file_path)
    return file_path, filename, name, ext, dirname


def get_content(data):
    payload = _tool_input(data)
    return payload.get("new_string", "") or payload.get("content", "")


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


def check_localstorage_jwt(raw, file_path=""):
    if _teaches_rather_than_runs(file_path):
        return None  # a doc or a test showing the anti-pattern is not doing it
    if re.search(r"localStorage\.(set|get)Item.*(token|jwt|auth|session)", raw, re.IGNORECASE):
        return (
            "BLOCKED: JWT tokens must use httpOnly cookies, not localStorage. "
            "RECOVERY: Replace localStorage with httpOnly cookie-based auth "
            "(set via backend Set-Cookie header). See rules/Security.md."
        )
    return None


def check_secrets_in_files(raw, file_path=""):
    # A test fixture invents keys; a doc may quote a REAL one by accident, so a
    # document stays under watch — only test files are excused.
    if _is_example_file(file_path):
        return None
    for pattern, name in SECRET_PATTERNS:
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
    is_critical = any(p in file_path.lower() for p in CRITICAL_PATHS)
    level = "BLOCKED" if is_critical else "WARNING"

    if ext == "py":
        # except: pass, except Exception: pass, except Exception as e: pass
        swallowed = re.search(
            r"except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*\n\s*(pass|\.\.\.)\s*$", content, re.MULTILINE
        )
        if swallowed:
            return (
                f"{level}: Swallowed exception (except/pass) detected. "
                "RECOVERY: Log the exception at appropriate level "
                "(WARNING for critical path errors, DEBUG for expected fallbacks). "
                "Never silently swallow exceptions — they are debugging data."
            )
    elif ext in ("ts", "js", "tsx", "jsx"):
        # catch {}, catch (e) {}, catch (_) {}
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", content):
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
    for pattern, name in WEAK_HASH_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return (
                f"BLOCKED: Weak hash ({name}) detected. "
                "RECOVERY: Use Argon2id for passwords, SHA-256+ for integrity. "
                "See rules/Security.md."
            )
    return None


def check_state_protection(file_path):
    """`.claude/state/` holds guard-owned counters (e.g. the VEILLE-SKIP
    threshold). Only a hook's own session_state.write_state() has a
    legitimate reason to touch it; a direct Write/Edit is exactly how the
    counter gets zeroed out from under the guard it protects (independent
    review, 2026-08-18 — brief 'Couche-Etat-Hooks-Defauts')."""
    if "/.claude/state/" in f"/{file_path}":
        return (
            "BLOCKED: .claude/state/ is machine-managed guard state, not hand-edited. "
            "RECOVERY: if a counter is stuck, fix the hook that maintains it "
            "(lib/session_state.py), never the state file directly."
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


def _naming_is_exempt(file_path, filename):
    if filename in NAMING_EXCEPTIONS:
        return True
    if filename.startswith(("Dockerfile", ".env", "index.")):
        return True
    if filename.endswith(".lock"):
        return True
    if any(
        filename.startswith(p.split(".")[0]) and p.split(".")[-1] in filename
        for p in NAMING_CONFIG_PATTERNS
    ):
        return True
    return any(d in file_path for d in NAMING_SKIP_DIRS)


def _check_code_naming(filename, name, ext):
    if ext not in NAMING_CONVENTIONS:
        return None
    pattern, convention = NAMING_CONVENTIONS[ext]
    if re.match(pattern, name):
        return None
    return (
        f"WARNING: {ext.upper()} files should use {convention}: {filename}. "
        f"ACTION: Rename to {convention} and update imports, then retry."
    )


def _check_doc_naming(file_path, filename, name):
    parent = os.path.basename(os.path.dirname(file_path))
    if parent in ("agents", "skills", "hooks"):
        return None
    if re.match(r"^[A-Z][a-zA-Z0-9]*(-[A-Z][a-zA-Z0-9]*)*$", name):
        return None
    return (
        f"WARNING: Markdown docs should use Title-Kebab-Case: {filename}. "
        "ACTION: Rename to Title-Kebab-Case (e.g., My-Document.md), then retry."
    )


def check_naming(file_path, filename, name, ext):
    if _naming_is_exempt(file_path, filename):
        return None
    if ext == "md":
        return _check_doc_naming(file_path, filename, name)
    return _check_code_naming(filename, name, ext)


def _blockers(raw, file_path, filename, name, ext, dirname, content):
    # A check that returns a "WARNING:" message is advising, not refusing — it belongs in
    # the warning stream whatever list it was called from. Without this, a check that
    # softens for a documented exemption would still stop the write, and the exemption
    # would exist in the text only (measured 2026-09-04: the Lego exemption printed its
    # WARNING and still exited 2).
    return [
        message
        for message in _blocker_checks(raw, file_path, filename, name, ext, dirname, content)
        if message and not message.startswith("WARNING:")
    ]


def _blocker_warnings(raw, file_path, filename, name, ext, dirname, content):
    """Advisory messages produced by checks that live in the blocker list."""
    return [
        message
        for message in _blocker_checks(raw, file_path, filename, name, ext, dirname, content)
        if message and message.startswith("WARNING:")
    ]


def _blocker_checks(raw, file_path, filename, name, ext, dirname, content):
    return [
        check_state_protection(file_path),
        check_env_guard(filename, dirname),
        check_localstorage_jwt(raw, file_path),
        check_secrets_in_files(raw, file_path),
        check_github_actions_sha(file_path, raw),
        check_lego_library(file_path, ext, content),
        check_hs256(ext, content, file_path),
        check_weak_hash(ext, content),
        check_tkinter(ext, content),
        check_bare_except(ext, content, file_path),
    ]


def _warnings(file_path, filename, name, ext, content):
    return [
        check_stack_versions(filename, content),
        check_i18n_hardcoded(file_path, ext, content),
        check_naming(file_path, filename, name, ext),
        check_hook_protection(file_path),
        check_uuidv7(file_path, content),
        check_type_suppression(ext, content),
    ]


def main():
    raw, data = read_input()
    info = get_file_info(data)
    if info is None:
        sys.exit(0)
    file_path, filename, name, ext, dirname = info
    content = get_content(data)

    for msg in _blockers(raw, file_path, filename, name, ext, dirname, content):
        if msg:
            print(msg, file=sys.stderr)
            sys.exit(2)

    advisories = _blocker_warnings(raw, file_path, filename, name, ext, dirname, content)
    for msg in advisories + _warnings(file_path, filename, name, ext, content):
        if msg:
            print(msg, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
