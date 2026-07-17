"""drift.py — fingerprint-based drift detection for propagated methodology files.

Problem (D1)
------------
`scripts/propagate-methodology.py` copies the canonical .claude/{rules,agents,
hooks,skills}/ from Kata into every project. The copy is ADDITIVE: it
overwrites and adds, but never deletes. So between propagations there is no way
to see whether a project edited a received file locally. The next propagation
would silently overwrite it — losing a legitimate local fix, or letting an
unauthorized divergence pass unnoticed.

This module is the shared, side-effect-free core that both the audit script
(`scripts/audit-drift.py`) and the pre-push guard
(`guards/pre-push-drift-check.py`) build on. stdlib only — no external deps.

Vocabulary (source = Kata canonical, dst = a propagated project)
---------------------------------------------------------------------
- identical : same relative path, same SHA-256 -> conformant
- drifted   : same relative path, different content -> the real signal to act on
- missing   : in source, absent in project -> under-propagated (run propagation)
- extra     : in project, absent in source -> local enrichment (additive sync = allowed)

Honest limit
------------
"drifted" means "differs from source right now". If the canonical source changed
without a propagation, those files also show as drifted — that case is
"pending propagation", not a local edit. Distinguishing the two would require
git history; out of scope for the fingerprint pass. The report says as much.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

# Match propagate-methodology.py `_is_sync_excluded`: bytecode caches are
# machine/version specific and are never propagated, so they must never count
# as drift either. Kept as a local copy (drift.py stays import-free and is
# itself propagated to all projects, where scripts/ is not available).
_TRANSIENT_SUFFIXES = (".pyc", ".pyo")


def is_transient(rel: Path) -> bool:
    """True for compiled/transient artifacts excluded from drift comparison."""
    if "__pycache__" in rel.parts:
        return True
    return rel.suffix in _TRANSIENT_SUFFIXES


def file_sha256(path: Path) -> str:
    """Hex SHA-256 of a file's bytes, read in chunks (large-file safe)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_files(root: Path, exclude: Callable[[Path], bool]) -> set[Path]:
    """Relative paths of all non-excluded files under root (empty if absent)."""
    if not root.exists():
        return set()
    out: set[Path] = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if exclude(rel):
            continue
        out.add(rel)
    return out


def _compare_present(
    src_dir: Path, dst_dir: Path, src_files: set[Path], dst_files: set[Path]
) -> tuple[int, list[str], list[str]]:
    """For files present in source: split into identical / drifted / missing."""
    identical = 0
    drifted: list[str] = []
    missing: list[str] = []
    for rel in src_files:
        if rel not in dst_files:
            missing.append(rel.as_posix())
        elif file_sha256(src_dir / rel) == file_sha256(dst_dir / rel):
            identical += 1
        else:
            drifted.append(rel.as_posix())
    return identical, drifted, missing


def classify_dir(
    src_dir: Path,
    dst_dir: Path,
    exclude: Callable[[Path], bool] = is_transient,
) -> dict:
    """Compare one directory tree (source vs project copy).

    Returns {"identical": int, "drifted": [str], "missing": [str], "extra": [str]}
    where the lists hold forward-slash relative paths, sorted.
    """
    src_files = _rel_files(src_dir, exclude)
    dst_files = _rel_files(dst_dir, exclude)
    identical, drifted, missing = _compare_present(src_dir, dst_dir, src_files, dst_files)
    extra = [rel.as_posix() for rel in (dst_files - src_files)]
    return {
        "identical": identical,
        "drifted": sorted(drifted),
        "missing": sorted(missing),
        "extra": sorted(extra),
    }


def _aggregate_dirs(
    src_claude: Path,
    dst_claude: Path,
    sync_dirs: tuple[str, ...],
    exclude: Callable[[Path], bool],
) -> tuple[int, list[str], list[str], list[str]]:
    """Sum drift across the propagated dirs; prefix each path with its dir."""
    identical = 0
    drifted: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    for d in sync_dirs:
        sub = classify_dir(src_claude / d, dst_claude / d, exclude)
        identical += sub["identical"]
        drifted += [f"{d}/{p}" for p in sub["drifted"]]
        missing += [f"{d}/{p}" for p in sub["missing"]]
        extra += [f"{d}/{p}" for p in sub["extra"]]
    return identical, drifted, missing, extra


def classify_project(
    src_claude: Path,
    dst_claude: Path,
    sync_dirs: tuple[str, ...],
    exclude: Callable[[Path], bool] = is_transient,
) -> dict:
    """Aggregate drift across the propagated dirs of one project.

    Paths are prefixed with their dir, e.g. "rules/Quality.md".
    """
    identical, drifted, missing, extra = _aggregate_dirs(
        src_claude, dst_claude, sync_dirs, exclude
    )
    return {
        "identical": identical,
        "drifted": sorted(drifted),
        "missing": sorted(missing),
        "extra": sorted(extra),
        "has_drift": bool(drifted),
    }
