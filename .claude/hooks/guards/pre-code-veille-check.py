#!/usr/bin/env python3
"""Veille / SKB Evidence guard — PreToolUse Write|Edit.

Enforces Workflows.md "Veille/SKB Evidence Protocol" with 3 hardening layers
(2026-05-19 — Option C):

  Layer A — Closed enum for SKIP motifs
    [VEILLE-SKIP] motif: <enum> where enum is one of:
      typo, internal-refactor-no-new-deps, hotfix-known-root-cause,
      test-only, methodology-edit, generated-artifact
    Any other motif text -> BLOCK.

  Layer B — Diff-aware: force REAL veille when content is sensitive
    Triggers (read the target file content / Edit diff):
      - Target is a dependency manifest (package.json, pyproject.toml,
        mix.exs, Cargo.toml, go.mod, requirements*.txt, Gemfile, ...)
      - New non-relative / non-stdlib import added vs old_string
      - Version pin pattern present in the diff (@X.Y.Z, ^X.Y, ~= X.Y)
    When triggered: ONLY [VEILLE] <techno>@<version> verifie <date> via <source>
    is accepted. SKB and VEILLE-SKIP are refused.

  Layer C — Session skip counter
    State file .claude/state/veille-skips-<session>.json tracks
    consecutive VEILLE-SKIP markers. The 3rd consecutive SKIP -> BLOCK
    even for trivial changes; a real [VEILLE] or [SKB] resets the counter.
    A given marker is counted ONCE (hashed) — repeated tool calls under
    the same marker do not re-increment.

Markers (case-sensitive, line-start or whitespace prefix):
  [VEILLE] <techno>@<version> verifie <date> via <source>
  [SKB] consulte: <paths>
  [VEILLE-SKIP] motif: <enum>

Hook exit codes:
  0 = pass
  2 = block (stderr message printed)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # noqa: E402
from session_state import read_state, write_state  # noqa: E402
from transcript_reader import iter_tool_calls  # noqa: E402


# --- Configuration -----------------------------------------------------------

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


# --- Input -------------------------------------------------------------------


def read_input() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return {}


def get_tool_input(data: dict) -> dict:
    return data.get("tool_input") or data


def get_file_info(data: dict) -> tuple[str, str, str]:
    ti = get_tool_input(data)
    file_path = (ti.get("file_path", "") or "").replace("\\", "/")
    filename = os.path.basename(file_path)
    _, ext = os.path.splitext(filename)
    return file_path, filename, ext.lstrip(".").lower()


def get_new_content(data: dict) -> str:
    ti = get_tool_input(data)
    return ti.get("content") or ti.get("new_string") or ""


def get_old_content(data: dict) -> str:
    ti = get_tool_input(data)
    return ti.get("old_string") or ""


# --- needs_evidence (path-based skip) ---------------------------------------


def needs_evidence(file_path: str, filename: str, ext: str) -> bool:
    """Source code in a non-skip path requires evidence."""
    if ext not in CODE_EXT:
        return False
    path_norm = file_path.lower()
    for part in SKIP_PATH_PARTS:
        if part in path_norm:
            return False
    for pat in SKIP_FILENAME_PATTERNS:
        if re.search(pat, filename, re.IGNORECASE):
            return False
    return True


# --- Layer B detection -------------------------------------------------------


def file_is_dep_manifest(filename: str) -> bool:
    return filename in DEPENDENCY_MANIFESTS


def new_lines(old: str, new: str) -> list[str]:
    """Return lines present in `new` but not in `old`. Naive but sufficient
    for our purpose (we don't need true line-level diff)."""
    old_set = set(old.splitlines())
    return [line for line in new.splitlines() if line not in old_set]


PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z_][\w.]*)|import\s+([a-zA-Z_][\w.]*))")
JS_IMPORT_RE = re.compile(r"""(?:^|;)\s*import\s+(?:[^;'"]+\s+from\s+)?['"]([^'"]+)['"]""")
JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")


def _py_line_has_external_import(line: str) -> bool:
    m = PY_IMPORT_RE.match(line)
    if not m:
        return False
    mod = (m.group(1) or m.group(2) or "").split(".")[0]
    if not mod or mod.startswith("_"):
        return False
    return not (PY_STDLIB and mod in PY_STDLIB)


def _js_line_has_external_import(line: str) -> bool:
    specs = [m.group(1) for m in JS_IMPORT_RE.finditer(line)]
    specs += [m.group(1) for m in JS_REQUIRE_RE.finditer(line)]
    return any(not s.startswith((".", "/", "~", "@/")) for s in specs)


def _py_module(line: str) -> str:
    m = PY_IMPORT_RE.match(line)
    return (m.group(1) or m.group(2) or "").split(".")[0] if m else ""


def _js_specs(line: str) -> list[str]:
    specs = [m.group(1) for m in JS_IMPORT_RE.finditer(line)]
    specs += [m.group(1) for m in JS_REQUIRE_RE.finditer(line)]
    return [s for s in specs if not s.startswith((".", "/", "~", "@/"))]


def external_imports(text: str, ext: str) -> set[str]:
    """Set of external (non-stdlib, non-relative) imported modules/specs in text.

    Module-aware (not raw-line): re-indenting or moving an import that already
    exists yields the same set, so it is NOT seen as a new dependency.
    """
    mods: set[str] = set()
    for line in text.splitlines():
        if ext == "py" and _py_line_has_external_import(line):
            mods.add(_py_module(line))
        elif ext in {"ts", "tsx", "js", "jsx"} and _js_line_has_external_import(line):
            mods.update(_js_specs(line))
    mods.discard("")
    return mods


def has_version_pin(diff_lines: list[str]) -> bool:
    return any(VERSION_PIN_RE.search(line) for line in diff_lines)


NPM_DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


def _read_disk(file_path: str) -> str | None:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _full_old_new(file_path: str, old_string: str, new_content: str) -> tuple[str | None, str | None]:
    """Reconstruct full OLD + NEW file content.

    Edit: old_string/new_content are fragments; the file on disk still holds the
    OLD full content (PreToolUse runs before the edit applies). Write: new_content
    is already the full file. Returns new=None when reconstruction is impossible.
    """
    disk = _read_disk(file_path)
    if old_string:  # Edit
        if disk is None or old_string not in disk:
            return disk, None
        return disk, disk.replace(old_string, new_content, 1)
    return disk, new_content  # Write


def _npm_dep_sections(content: str) -> dict | None:
    try:
        obj = json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    return {k: obj.get(k) for k in NPM_DEP_KEYS}


def _pyproject_dep_sections(content: str) -> dict | None:
    try:
        import tomllib
    except ImportError:
        return None
    try:
        obj = tomllib.loads(content)
    except (ValueError, TypeError):
        return None
    project = obj.get("project") if isinstance(obj.get("project"), dict) else {}
    tool = obj.get("tool") if isinstance(obj.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    return {
        "dependencies": project.get("dependencies"),
        "optional-dependencies": project.get("optional-dependencies"),
        "poetry.dependencies": poetry.get("dependencies"),
        "poetry.dev-dependencies": poetry.get("dev-dependencies"),
        "poetry.group": poetry.get("group"),
    }


def _requirements_dep_lines(content: str) -> list[str]:
    return [s for s in (ln.strip() for ln in content.splitlines()) if s and not s.startswith("#")]


def _sections_changed(old_sec: dict | None, new_sec: dict | None) -> bool | None:
    if old_sec is None or new_sec is None:
        return None
    return old_sec != new_sec


def manifest_dependencies_changed(file_path: str, filename: str, old_string: str, new_content: str) -> bool | None:
    """True if a dependency key changed, False if not, None if undetermined.

    Only npm (package.json), pyproject.toml and requirements*.txt are parsed.
    Other manifests / lockfiles return None (conservative — caller keeps the
    'sensitive' default so a real add/bump still requires veille).
    """
    old_full, new_full = _full_old_new(file_path, old_string, new_content)
    if old_full is None or new_full is None:
        return None
    if filename == "package.json":
        return _sections_changed(_npm_dep_sections(old_full), _npm_dep_sections(new_full))
    if filename == "pyproject.toml":
        return _sections_changed(_pyproject_dep_sections(old_full), _pyproject_dep_sections(new_full))
    if filename.startswith("requirements") and filename.endswith(".txt"):
        return _requirements_dep_lines(old_full) != _requirements_dep_lines(new_full)
    return None


def sensitive_change(file_path: str, filename: str, ext: str, old: str, new: str) -> str | None:
    """Return a short reason string if Layer B is triggered, else None."""
    if file_is_dep_manifest(filename):
        changed = manifest_dependencies_changed(file_path, filename, old, new)
        if changed is False:
            return None  # manifest edited but no dependency changed -> not sensitive
        if changed is True:
            return f"dependency change in manifest ({filename})"
        return f"target is dependency manifest ({filename})"  # undetermined -> conservative
    diff = new_lines(old, new) if old else new.splitlines()
    if has_version_pin(diff):
        return "version pin pattern in diff"
    if ext in {"py", "ts", "tsx", "js", "jsx"}:
        added = external_imports(new, ext) - external_imports(old, ext)
        if added:
            return f"new external import detected ({ext}: {', '.join(sorted(added))})"
    return None


# --- Transcript scan ---------------------------------------------------------


def extract_text(entry) -> str:
    chunks: list[str] = []

    def walk(node):
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for _, v in node.items():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(entry)
    return "\n".join(chunks)


def _entry_text(raw: str) -> str:
    """Plain text of a transcript line, with our own recovery/block lines removed
    (they contain literal marker templates that would otherwise be re-matched)."""
    try:
        text = extract_text(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        text = raw
    kept = [ln for ln in text.splitlines()
            if not any(h in ln for h in RECOVERY_LINE_HINTS)]
    return "\n".join(kept)


def _concrete_markers(text: str) -> list:
    """MARKER_RE matches that are real, not angle-bracket / set-repr templates
    (e.g. the literal "[VEILLE] <techno>@<version> ..." in a recovery message)."""
    return [m for m in MARKER_RE.finditer(text)
            if "<" not in m.group(0) and "{" not in m.group(0)]


def latest_marker(transcript_path: str) -> tuple[str, str, str] | None:
    """Return (marker_type, marker_line, hash) of the most recent marker, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    for raw in reversed(lines[-TRANSCRIPT_SCAN_LIMIT:]):
        raw = raw.strip()
        if not raw:
            continue
        matches = _concrete_markers(_entry_text(raw))
        if matches:
            line = matches[-1].group(0).strip()
            digest = hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]
            return matches[-1].group(1), line, digest
    return None


# --- Counter state -----------------------------------------------------------


STATE_NAME = "veille-skips"


def load_counter(session_id: str | None, repo_root: Path) -> dict:
    data = read_state(STATE_NAME, session_id, repo_root)
    return {
        "skip_count": int(data.get("skip_count", 0)),
        "last_marker_hash": str(data.get("last_marker_hash", "")),
        "veille_seen": bool(data.get("veille_seen", False)),
    }


def _persist(session_id: str | None, repo_root: Path, *, skip_count: int,
             marker_hash: str, veille_seen: bool) -> None:
    write_state(
        STATE_NAME,
        {"skip_count": skip_count, "last_marker_hash": marker_hash, "veille_seen": veille_seen},
        session_id,
        repo_root,
    )


# --- Main --------------------------------------------------------------------


def has_web_veille_call(transcript_path: str) -> bool:
    """True if a real web tool call (WebSearch/WebFetch/MCP web) happened.

    Scope is session-wide on purpose: under plan mode (Chantier B) the veille
    is performed in the plan phase and the code is written in a later turn, so
    a per-turn scan would false-block legitimate plan execution. A real tool
    call cannot be fabricated by writing marker text — that is the proof.
    """
    if not transcript_path:
        return False
    try:
        for call in iter_tool_calls(transcript_path):
            name = call.get("name") or ""
            if name in WEB_TOOL_NAMES_EXACT:
                return True
            low = name.lower()
            if any(sub in low for sub in WEB_TOOL_SUBSTRINGS):
                return True
    except Exception:
        return False
    return False


def block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def _block_missing_marker(file_path: str) -> None:
    block(
        "BLOCKED: Veille / SKB evidence missing before writing source code.\n"
        f"Target: {file_path}\n"
        "RECOVERY: Output one of the strict markers BEFORE retrying:\n"
        "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>\n"
        "  [SKB] consulte: <chemin1>, <chemin2>\n"
        f"  [VEILLE-SKIP] motif: <one of {sorted(ALLOWED_SKIP_MOTIFS)}>\n"
        "See rules/Workflows.md -> 'Veille/SKB Evidence Protocol'."
    )


def _enforce_sensitive(file_path: str, reason: str, marker_type: str, transcript_path: str) -> None:
    """A sensitive change requires a real [VEILLE] backed by a real web call."""
    if marker_type != "VEILLE":
        block(
            "BLOCKED: Sensitive change detected — real [VEILLE] required.\n"
            f"Target: {file_path}\n"
            f"Trigger: {reason}\n"
            f"Latest marker: [{marker_type}] (insufficient for sensitive change)\n"
            "RECOVERY: Output a real veille marker BEFORE retrying:\n"
            "  [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>\n"
            "Layer B refuses [SKB] and [VEILLE-SKIP] on sensitive content."
        )
    if not has_web_veille_call(transcript_path):
        block(
            "BLOCKED: [VEILLE] marker present but no web veille was actually performed.\n"
            f"Target: {file_path}\n"
            f"Trigger: {reason}\n"
            "No WebSearch / WebFetch (or MCP web) tool call found in this session.\n"
            "RECOVERY: actually run the veille — WebSearch/WebFetch the registry "
            "(hex.pm, npmjs, pypi, crates.io...) to confirm the current version, "
            "THEN re-emit [VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>.\n"
            "The marker text alone is not proof; the tool call is."
        )


def _enforce_skip(file_path: str, marker_line: str, marker_hash: str,
                  counter: dict, session_id: str | None, repo_root: Path) -> None:
    """Layer A (motif enum) + Layer C (session skip counter). Preserves the
    sticky veille_seen flag across SKIPs (Jay 2026-06-16)."""
    m = SKIP_MOTIF_RE.search(marker_line)
    motif = m.group(1).lower() if m else ""
    if motif not in ALLOWED_SKIP_MOTIFS:
        block(
            "BLOCKED: VEILLE-SKIP motif is not in the closed enum.\n"
            f"Target: {file_path}\n"
            f"Motif found: '{motif or '(empty)'}'\n"
            f"RECOVERY: use one of {sorted(ALLOWED_SKIP_MOTIFS)}\n"
            "Or emit a real [VEILLE] / [SKB] marker instead."
        )
    if counter["last_marker_hash"] != marker_hash:
        counter["skip_count"] += 1
    seen = counter.get("veille_seen", False)
    if counter["skip_count"] >= SKIP_COUNT_THRESHOLD:
        _persist(session_id, repo_root, skip_count=counter["skip_count"], marker_hash=marker_hash, veille_seen=seen)
        block(
            "BLOCKED: VEILLE-SKIP threshold reached.\n"
            f"Consecutive SKIPs this session: {counter['skip_count']} "
            f"(threshold {SKIP_COUNT_THRESHOLD}).\n"
            f"Target: {file_path}\n"
            "RECOVERY: Emit a real [VEILLE] or [SKB] marker — the counter "
            "resets only with verified evidence, not with another SKIP."
        )
    _persist(session_id, repo_root, skip_count=counter["skip_count"], marker_hash=marker_hash, veille_seen=seen)


def _session_ctx(data: dict) -> tuple[str, str, Path]:
    transcript = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    return transcript, session_id, find_repo_root()


def _handle_no_marker(file_path: str, sensitive_reason: str | None, counter: dict) -> None:
    """No marker in scan range. Sticky: a real [VEILLE]/[SKB] seen earlier this
    session covers a NON-sensitive write even if the marker scrolled out of the
    200-line scan window (Jay 2026-06-16). Sensitive changes always need a fresh
    real [VEILLE] + web call, so the sticky bypass never applies to them."""
    if not sensitive_reason and counter.get("veille_seen"):
        sys.exit(0)
    _block_missing_marker(file_path)


def _record_real_marker(session_id: str | None, repo_root: Path, counter: dict, marker_hash: str) -> None:
    """A real [VEILLE]/[SKB]: reset the skip counter and remember (sticky) that
    veille was performed this session."""
    if counter["last_marker_hash"] != marker_hash or not counter.get("veille_seen"):
        _persist(session_id, repo_root, skip_count=0, marker_hash=marker_hash, veille_seen=True)


def main() -> None:
    data = read_input()
    file_path, filename, ext = get_file_info(data)
    if not file_path:
        sys.exit(0)
    is_dep = file_is_dep_manifest(filename)
    if not is_dep and not needs_evidence(file_path, filename, ext):
        sys.exit(0)
    old_content = get_old_content(data)
    new_content = get_new_content(data)
    sensitive_reason = sensitive_change(file_path, filename, ext, old_content, new_content)
    # Dep manifest with no dependency change = internal edit -> no evidence (Jay 2026-06-13).
    if is_dep and sensitive_reason is None:
        sys.exit(0)
    transcript_path, session_id, repo_root = _session_ctx(data)
    counter = load_counter(session_id, repo_root)
    latest = latest_marker(transcript_path)
    if latest is None:
        _handle_no_marker(file_path, sensitive_reason, counter)
    marker_type, marker_line, marker_hash = latest
    if sensitive_reason:
        _enforce_sensitive(file_path, sensitive_reason, marker_type, transcript_path)
    if marker_type == "VEILLE-SKIP":
        _enforce_skip(file_path, marker_line, marker_hash, counter, session_id, repo_root)
        sys.exit(0)
    _record_real_marker(session_id, repo_root, counter, marker_hash)
    sys.exit(0)


if __name__ == "__main__":
    main()
