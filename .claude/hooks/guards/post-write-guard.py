#!/usr/bin/env python3
"""Unified Write|Edit PostToolUse guard — all checks in one script.

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
    return data


def get_file_path(data):
    file_path = data.get("file_path", "")
    if not file_path:
        return None
    return file_path.replace("\\\\", "/").replace("\\", "/")


_SIZE_EXEMPT_EXTENSIONS = ("md", "json", "lock", "svg", "csv", "sql")

_SIZE_EXEMPT_PATTERNS = (
    ".test.", ".spec.", ".stories.",
    "migrations/", "migration/", "seed/", "fixture/",
    "config.", ".config.",
    "/dist/",
    "validation",
    ".d.ts",
    "schema", "types/",
)


def _is_size_exempt(file_path, ext):
    if ext in _SIZE_EXEMPT_EXTENSIONS:
        return True
    return any(p in file_path for p in _SIZE_EXEMPT_PATTERNS)


def _count_lines(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _size_blocked_msg(file_path, lines):
    return (
        f"BLOCKED: File {file_path} has {lines} lines (max 500). "
        "RECOVERY: Split this file into smaller, cohesive modules. "
        "Extract logical sections into separate files, update imports. "
        "Principle: readability over size — each file = one concept."
    )


def _size_warning_msg(file_path, lines):
    return (
        f"WARNING: File {file_path} has {lines} lines (ideal: <300). "
        "ACTION: Consider if this file can be split into more cohesive modules. "
        "If the file is logically cohesive (one concept, low complexity), continue. "
        "BLOCKING threshold is 500 lines."
    )


def check_file_size(file_path):
    """WARNING at 300 lines, BLOCKING at 500 lines.
    Exempt: .md, .json, type schemas, configs, tests, migrations, generated.
    """
    ext = os.path.splitext(file_path)[1].lstrip(".")
    if _is_size_exempt(file_path, ext):
        return None
    if not os.path.isfile(file_path):
        return None

    lines = _count_lines(file_path)
    if lines is None:
        return None

    if lines > 500:
        return _size_blocked_msg(file_path, lines)
    if lines > 300:
        return _size_warning_msg(file_path, lines)
    return None


def check_utf8_bom(file_path):
    try:
        with open(file_path, "rb") as f:
            header = f.read(3)
    except OSError:
        return None

    if header == b"\xef\xbb\xbf":
        return (
            f"BLOCKED: UTF-8 BOM detected in {file_path}. "
            "RECOVERY: Re-write the file content without BOM. "
            "Use Write tool with the same content (Claude Code writes UTF-8 without BOM by default)."
        )
    if header[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return (
            f"BLOCKED: Non-UTF-8 encoding detected in {file_path} (UTF-16). "
            "RECOVERY: Re-write the file using the Write tool (outputs UTF-8 by default)."
        )
    return None


def check_utf8_validity(file_path):
    text_extensions = (
        "ts", "tsx", "js", "jsx", "py", "sh", "md",
        "json", "yaml", "yml", "toml", "css", "scss", "html", "sql",
    )
    ext = os.path.splitext(file_path)[1].lstrip(".")
    if ext not in text_extensions:
        return None

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return (
            f"BLOCKED: Invalid UTF-8 sequences in {file_path}. "
            "RECOVERY: Read the file, identify non-UTF-8 characters, "
            "replace with proper UTF-8 equivalents, re-write the file."
        )
    except OSError:
        pass
    return None


def _flatten_keys(obj, prefix=""):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys |= _flatten_keys(v, full)
            else:
                keys.add(full)
    return keys


def _load_locales(base_dir, filename):
    locales = {}
    for locale in ("fr", "en", "es"):
        locale_file = f"{base_dir}{locale}/{filename}"
        if os.path.isfile(locale_file):
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    locales[locale] = _flatten_keys(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
    return locales


def _compute_missing_keys(locales):
    all_keys = set()
    for keys in locales.values():
        all_keys |= keys

    missing = {}
    for locale, keys in locales.items():
        diff = all_keys - keys
        if diff:
            missing[locale] = sorted(diff)[:5]
    return missing


def check_i18n_locales(file_path):
    normalized = file_path.replace("\\", "/")
    match = re.search(r"(.+/locales/)(fr|en|es)/(.+\.json)$", normalized)
    if not match:
        return None
    base_dir, filename = match.group(1), match.group(3)

    locales = _load_locales(base_dir, filename)
    if len(locales) < 2:
        return None

    missing = _compute_missing_keys(locales)
    if not missing:
        return None

    details = "; ".join(
        f"{loc} missing: {', '.join(keys)}" for loc, keys in missing.items()
    )
    return (
        f"WARNING: i18n key mismatch in {filename}. {details}. "
        "ACTION: Add missing keys to all 3 locales (FR/EN/ES)."
    )


def _is_test_file(ext, basename):
    if ext in ("ts", "tsx") and (".test." in basename or ".spec." in basename):
        return True
    return ext == "py" and basename.startswith("test_")


def _find_empty_ts_tests(content):
    empty = []
    test_blocks = re.finditer(
        r"(it|test)\s*\(\s*['\"]([^'\"]+)['\"]",
        content,
    )
    assertion_patterns = (
        r"expect\(", r"assert", r"toThrow", r"toEqual",
        r"toBe\(", r"toMatch", r"toContain", r"rejects",
    )
    for match in test_blocks:
        start = match.start()
        # Find the test body (rough heuristic: next 500 chars)
        body = content[start:start + 500]
        if not any(re.search(p, body) for p in assertion_patterns):
            empty.append(match.group(2))
    return empty


def _find_empty_py_tests(content):
    empty = []
    for match in re.finditer(r"def (test_\w+)\s*\(", content):
        start = match.start()
        # Find next def or end of file
        next_def = re.search(r"\ndef ", content[start + 1:])
        end = start + 1 + next_def.start() if next_def else len(content)
        body = content[start:end]
        if not re.search(r"assert |pytest\.raises|assertEqual|assertTrue", body):
            empty.append(match.group(1))
    return empty


def check_empty_tests(file_path):
    """Detect test functions with zero assertions — BLOCKING."""
    ext = os.path.splitext(file_path)[1].lstrip(".")
    basename = os.path.basename(file_path)

    if not _is_test_file(ext, basename):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return None

    if ext in ("ts", "tsx"):
        empty_tests = _find_empty_ts_tests(content)
    else:
        empty_tests = _find_empty_py_tests(content)

    if not empty_tests:
        return None

    names = ", ".join(empty_tests[:3])
    return (
        f"BLOCKED: Empty test(s) detected (zero assertions): {names}. "
        "RECOVERY: Add meaningful assertions to each test. "
        "A test without assertions gives false confidence."
    )


def check_ts_nocheck_header(file_path):
    """Detect @ts-nocheck at file header — WARNING."""
    ext = os.path.splitext(file_path)[1].lstrip(".")
    if ext not in ("ts", "tsx"):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            first_lines = "".join(f.readline() for _ in range(5))
        if "@ts-nocheck" in first_lines:
            return (
                f"WARNING: @ts-nocheck at top of {file_path}. "
                "This disables ALL type checking for the entire file. "
                "ACTION: Remove @ts-nocheck and fix type errors individually."
            )
    except OSError:
        pass
    return None


def check_vitest_config(file_path):
    """Verify vitest config has pool: 'forks' and maxForks — WARNING if absent."""
    basename = os.path.basename(file_path)
    if basename not in ("vitest.config.ts", "vite.config.ts"):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return None

    warnings = []
    if "pool:" not in content or "'forks'" not in content:
        warnings.append("pool: 'forks' missing")
    if "maxForks" not in content:
        warnings.append("maxForks missing")

    if warnings:
        return (
            f"WARNING: Vitest config ({basename}) missing OOM protections: "
            f"{', '.join(warnings)}. "
            "ACTION: Add pool: 'forks' and forks: {{ maxForks: 2 }} to prevent "
            "VPS memory saturation. See rules/Quality.md — Test Runtime Hygiene."
        )
    return None


def check_console_log(file_path):
    ext = os.path.splitext(file_path)[1].lstrip(".")
    if ext not in ("ts", "tsx", "js", "jsx"):
        return None

    skip_patterns = (".test.", ".spec.", ".stories.")
    if any(p in file_path for p in skip_patterns):
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        count = len(re.findall(r"console\.log", content))
        if count > 0:
            return (
                f"WARNING: {count} console.log found in {file_path}. "
                "ACTION: Remove all console.log statements "
                "(replace with proper logger if debug output is needed). "
                "Fix these before committing."
            )
    except OSError:
        pass
    return None


def _emit_blockers(file_path):
    """Print the first blocking finding and exit(2), else return."""
    blockers = [
        check_utf8_bom(file_path),
        check_utf8_validity(file_path),
        check_empty_tests(file_path),
    ]
    for msg in blockers:
        if msg:
            print(msg, file=sys.stderr)
            sys.exit(2)


def _emit_warnings(file_path, size_msg):
    """Print all non-blocking findings to stderr."""
    warnings = [
        size_msg,
        check_console_log(file_path),
        check_i18n_locales(file_path),
        check_ts_nocheck_header(file_path),
        check_vitest_config(file_path),
    ]
    for msg in warnings:
        if msg:
            print(msg, file=sys.stderr)


def main():
    data = read_input()
    file_path = get_file_path(data)
    if not file_path or not os.path.isfile(file_path):
        sys.exit(0)

    _emit_blockers(file_path)

    size_msg = check_file_size(file_path)
    if size_msg and size_msg.startswith("BLOCKED"):
        print(size_msg, file=sys.stderr)
        sys.exit(2)

    _emit_warnings(file_path, size_msg)
    sys.exit(0)


if __name__ == "__main__":
    main()
