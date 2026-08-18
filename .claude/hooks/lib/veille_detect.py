"""Detection layer of the veille / SKB evidence guard.

Answers two questions about a Write/Edit target, without deciding anything:

  needs_evidence()   — does this path require veille evidence at all?
  sensitive_change() — is the change SENSITIVE (Layer B), i.e. does it add a
                       dependency, a new external import, or a version pin?

Extracted from guards/pre-code-veille-check.py on 2026-08-18. Behaviour is
unchanged — the functions moved, the logic did not.

Stdlib only. Cross-platform (Windows + Linux).
"""

from __future__ import annotations

import json
import re

from veille_config import (
    CODE_EXT,
    DEPENDENCY_MANIFESTS,
    PY_STDLIB,
    SKIP_FILENAME_PATTERNS,
    SKIP_PATH_PARTS,
    VERSION_PIN_RE,
)

PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z_][\w.]*)|import\s+([a-zA-Z_][\w.]*))")
JS_IMPORT_RE = re.compile(r"""(?:^|;)\s*import\s+(?:[^;'"]+\s+from\s+)?['"]([^'"]+)['"]""")
JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")

NPM_DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


# --- Path-based skip ---------------------------------------------------------


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


def file_is_dep_manifest(filename: str) -> bool:
    return filename in DEPENDENCY_MANIFESTS


# --- Import / version-pin detection -----------------------------------------


def new_lines(old: str, new: str) -> list[str]:
    """Return lines present in `new` but not in `old`. Naive but sufficient
    for our purpose (we don't need true line-level diff)."""
    old_set = set(old.splitlines())
    return [line for line in new.splitlines() if line not in old_set]


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


# --- Manifest dependency comparison ------------------------------------------


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


# --- Layer B verdict ---------------------------------------------------------


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
