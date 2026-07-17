"""Tests for lib/drift.py — fingerprint-based drift detection (D1).

Pure-function level: import the module directly (no subprocess). drift.py is
stdlib-only and side-effect-free, so it is testable in isolation.

Drift vocabulary (source = Kata canonical, dst = a propagated project):
- identical : same relative path, same SHA-256 -> conformant
- drifted   : same relative path, different content -> the real signal
- missing   : in source, absent in project -> under-propagated
- extra     : in project, absent in source -> local enrichment (additive sync = allowed)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import drift  # noqa: E402


# --- Helpers ----------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- file_sha256 ------------------------------------------------------------


def test_sha256_same_content_same_digest(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    _write(a, "same content\n")
    _write(b, "same content\n")
    assert drift.file_sha256(a) == drift.file_sha256(b)


def test_sha256_different_content_different_digest(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    _write(a, "one\n")
    _write(b, "two\n")
    assert drift.file_sha256(a) != drift.file_sha256(b)


# --- is_transient -----------------------------------------------------------


def test_is_transient_pycache_and_pyc():
    assert drift.is_transient(Path("hooks/__pycache__/x.cpython-312.pyc"))
    assert drift.is_transient(Path("foo.pyc"))
    assert drift.is_transient(Path("foo.pyo"))
    assert not drift.is_transient(Path("rules/Quality.md"))
    assert not drift.is_transient(Path("hooks/guards/write-guard.py"))


# --- classify_dir -----------------------------------------------------------


def test_identical_files_counted(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "Quality.md", "rule body\n")
    _write(dst / "Quality.md", "rule body\n")
    result = drift.classify_dir(src, dst)
    assert result["identical"] == 1
    assert result["drifted"] == []
    assert result["missing"] == []
    assert result["extra"] == []


def test_drifted_file_detected(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "Quality.md", "canonical body\n")
    _write(dst / "Quality.md", "EDITED IN PROJECT\n")
    result = drift.classify_dir(src, dst)
    assert result["drifted"] == ["Quality.md"]
    assert result["identical"] == 0


def test_missing_file_detected(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "NewRule.md", "freshly added to source\n")
    (dst).mkdir(parents=True, exist_ok=True)
    result = drift.classify_dir(src, dst)
    assert result["missing"] == ["NewRule.md"]


def test_extra_file_is_enrichment_not_drift(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "Quality.md", "body\n")
    _write(dst / "Quality.md", "body\n")
    _write(dst / "Project-Specific.md", "local enrichment\n")
    result = drift.classify_dir(src, dst)
    assert result["extra"] == ["Project-Specific.md"]
    assert result["drifted"] == []
    assert result["identical"] == 1


def test_missing_dst_dir_makes_all_source_missing(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"  # never created
    _write(src / "a.md", "x\n")
    _write(src / "sub" / "b.md", "y\n")
    result = drift.classify_dir(src, dst)
    assert sorted(result["missing"]) == ["a.md", "sub/b.md"]


def test_transient_files_excluded_everywhere(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "real.py", "code\n")
    _write(src / "__pycache__" / "real.cpython-312.pyc", "bytecode-src\n")
    _write(dst / "real.py", "code\n")
    _write(dst / "__pycache__" / "real.cpython-312.pyc", "bytecode-dst-different\n")
    result = drift.classify_dir(src, dst)
    # the .pyc differs but must be ignored; only real.py counts (identical)
    assert result["identical"] == 1
    assert result["drifted"] == []
    assert result["extra"] == []


def test_nested_paths_use_forward_slashes(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write(src / "guards" / "x.py", "v1\n")
    _write(dst / "guards" / "x.py", "v2\n")
    result = drift.classify_dir(src, dst)
    assert result["drifted"] == ["guards/x.py"]


# --- classify_project -------------------------------------------------------


def test_classify_project_prefixes_with_dir(tmp_path):
    src_claude = tmp_path / "MNK" / ".claude"
    dst_claude = tmp_path / "Proj" / ".claude"
    _write(src_claude / "rules" / "Quality.md", "canonical\n")
    _write(dst_claude / "rules" / "Quality.md", "drifted in project\n")
    _write(src_claude / "hooks" / "guards" / "g.py", "code\n")
    _write(dst_claude / "hooks" / "guards" / "g.py", "code\n")
    result = drift.classify_project(src_claude, dst_claude, ("rules", "agents", "hooks", "skills"))
    assert result["drifted"] == ["rules/Quality.md"]
    assert result["identical"] == 1
    assert result["missing"] == []
    assert result["extra"] == []


def test_classify_project_aggregates_missing_and_extra(tmp_path):
    src_claude = tmp_path / "MNK" / ".claude"
    dst_claude = tmp_path / "Proj" / ".claude"
    _write(src_claude / "rules" / "OnlyInSource.md", "x\n")
    _write(dst_claude / "skills" / "only-in-project" / "SKILL.md", "y\n")
    result = drift.classify_project(src_claude, dst_claude, ("rules", "agents", "hooks", "skills"))
    assert result["missing"] == ["rules/OnlyInSource.md"]
    assert result["extra"] == ["skills/only-in-project/SKILL.md"]
    assert result["drifted"] == []


def test_classify_project_has_drift_flag(tmp_path):
    src_claude = tmp_path / "MNK" / ".claude"
    dst_claude = tmp_path / "Proj" / ".claude"
    _write(src_claude / "rules" / "Q.md", "a\n")
    _write(dst_claude / "rules" / "Q.md", "b\n")
    result = drift.classify_project(src_claude, dst_claude, ("rules",))
    assert result["has_drift"] is True
    # identical-only project -> has_drift False
    _write(dst_claude / "rules" / "Q.md", "a\n")
    result2 = drift.classify_project(src_claude, dst_claude, ("rules",))
    assert result2["has_drift"] is False
