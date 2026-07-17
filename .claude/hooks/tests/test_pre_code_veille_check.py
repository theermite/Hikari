"""pre-code-veille-check.py — PreToolUse Write|Edit veille/SKB evidence guard.

Focus of this suite: Chantier D — a SENSITIVE change (dependency manifest,
new external import, version pin) backed by a [VEILLE] marker must ALSO be
backed by a REAL web tool call (WebSearch/WebFetch) somewhere in the session.
The marker alone (text) is no longer sufficient proof on the sensitive path.

Unchanged behaviors locked here as regressions:
- sensitive change + [SKB] marker -> BLOCK (Layer B: only [VEILLE] accepted)
- non-sensitive code + [SKB] marker -> pass (no web proof required off the
  sensitive path)
- missing marker -> BLOCK

Transcript shape mirrors Claude Code JSONL: top-level {role, content}.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "pre-code-veille-check.py"


# --- Transcript builders -----------------------------------------------------


def _veille_marker(text: str = "[VEILLE] phoenix@1.8.8 verifie 2026-06-12 via hex.pm") -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _skb_marker() -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": "[SKB] consulte: 11-Communication/Voice-Tone.md"}]}


def _web_call(name: str = "WebSearch") -> dict:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "name": name, "id": "s1", "input": {"query": "phoenix latest version"}}],
    }


def _write_transcript(tmp_path: Path, *entries: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return transcript


def _run(transcript: Path | None, *, file_path: str, content: str,
         old_string: str = "") -> subprocess.CompletedProcess:
    payload: dict = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "session_id": f"test-{uuid.uuid4().hex[:12]}",
    }
    if old_string:
        payload["tool_input"]["old_string"] = old_string
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


# --- Chantier D: sensitive + VEILLE needs a real web call --------------------


def test_sensitive_veille_passes_with_web_call(tmp_path):
    transcript = _write_transcript(tmp_path, _veille_marker(), _web_call("WebSearch"))
    r = _run(transcript, file_path="mix.exs", content='{:phoenix, "~> 1.8.8"}')
    assert r.returncode == 0, f"sensitive+VEILLE+web should pass: {r.stderr!r}"


def test_sensitive_veille_passes_with_webfetch(tmp_path):
    transcript = _write_transcript(tmp_path, _veille_marker(), _web_call("WebFetch"))
    r = _run(transcript, file_path="mix.exs", content='{:phoenix, "~> 1.8.8"}')
    assert r.returncode == 0, f"WebFetch should count: {r.stderr!r}"


def test_sensitive_veille_blocks_without_web_call(tmp_path):
    # Marker present but NO web tool call anywhere -> blocked (Chantier D).
    transcript = _write_transcript(tmp_path, _veille_marker())
    r = _run(transcript, file_path="mix.exs", content='{:phoenix, "~> 1.8.8"}')
    assert r.returncode == 2, "VEILLE text without a real web call must block"
    assert b"BLOCKED" in r.stderr


# --- Unchanged behaviors (regression locks) ----------------------------------


def test_sensitive_skb_still_blocks(tmp_path):
    # Layer B: [SKB] is insufficient for a sensitive change, regardless of web.
    transcript = _write_transcript(tmp_path, _skb_marker(), _web_call("WebSearch"))
    r = _run(transcript, file_path="mix.exs", content='{:phoenix, "~> 1.8.8"}')
    assert r.returncode == 2
    assert b"VEILLE" in r.stderr


def test_nonsensitive_skb_passes_without_web(tmp_path):
    # Plain source edit, no new import / version pin -> [SKB] is enough, no web proof.
    transcript = _write_transcript(tmp_path, _skb_marker())
    r = _run(
        transcript,
        file_path="lib/app/foo.ex",
        content="def hello, do: :world\n",
    )
    assert r.returncode == 0, f"non-sensitive [SKB] should pass: {r.stderr!r}"


def test_missing_marker_blocks(tmp_path):
    transcript = _write_transcript(tmp_path, {"role": "assistant", "content": [{"type": "text", "text": "no marker"}]})
    r = _run(transcript, file_path="lib/app/foo.ex", content="def hello, do: :world\n")
    assert r.returncode == 2
    assert b"BLOCKED" in r.stderr


# --- Manifest dependency-diff: rename without dep change is NOT sensitive -----
# (Jay 2026-06-13 — a package.json rename of name/bin, zero dependency change,
#  was hard-blocked as a false positive. Such an edit must pass like a refactor.)


def _run_edit(transcript: Path | None, *, file_path: str, old_string: str,
              new_string: str) -> subprocess.CompletedProcess:
    payload: dict = {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": old_string, "new_string": new_string},
        "session_id": f"test-{uuid.uuid4().hex[:12]}",
    }
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


def test_package_json_name_rename_passes_without_marker(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "name": "takumi-t",
        "bin": {"takumi-t": "./cli.js"},
        "dependencies": {"react": "^19.0.0"},
    }, indent=2), encoding="utf-8")
    # No transcript / no marker at all — a no-dep-change manifest edit must PASS.
    r = _run_edit(None, file_path=str(pkg),
                  old_string='"name": "takumi-t"',
                  new_string='"name": "mnk-terminal"')
    assert r.returncode == 0, f"name rename (no dep change) must pass: {r.stderr!r}"


def test_package_json_bin_rename_passes_without_marker(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "name": "takumi-t",
        "bin": {"takumi-t": "./cli.js"},
        "dependencies": {"react": "^19.0.0"},
    }, indent=2), encoding="utf-8")
    r = _run_edit(None, file_path=str(pkg),
                  old_string='"takumi-t": "./cli.js"',
                  new_string='"mnk-terminal": "./cli.js"')
    assert r.returncode == 0, f"bin-key rename (no dep change) must pass: {r.stderr!r}"


def test_package_json_dependency_add_still_sensitive(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "name": "app",
        "dependencies": {"react": "^19.0.0"},
    }, indent=2), encoding="utf-8")
    # Adding a real dependency stays sensitive: [SKB]+web is insufficient (Layer B).
    transcript = _write_transcript(tmp_path, _skb_marker(), _web_call("WebSearch"))
    r = _run_edit(transcript, file_path=str(pkg),
                  old_string='"react": "^19.0.0"',
                  new_string='"react": "^19.0.0",\n    "left-pad": "^1.3.0"')
    assert r.returncode == 2, f"adding a dependency must stay sensitive: {r.stderr!r}"
    assert b"VEILLE" in r.stderr


def test_pyproject_name_rename_passes_without_marker(tmp_path):
    pp = tmp_path / "pyproject.toml"
    pp.write_text(
        '[project]\n'
        'name = "takumi-t"\n'
        'version = "0.1.0"\n'
        'dependencies = ["httpx>=0.27"]\n',
        encoding="utf-8",
    )
    r = _run_edit(None, file_path=str(pp),
                  old_string='name = "takumi-t"',
                  new_string='name = "mnk-terminal"')
    assert r.returncode == 0, f"pyproject name rename must pass: {r.stderr!r}"


def test_requirements_comment_change_passes_without_marker(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("# old comment\nhttpx>=0.27\n", encoding="utf-8")
    r = _run_edit(None, file_path=str(req),
                  old_string="# old comment",
                  new_string="# renamed comment")
    assert r.returncode == 0, f"requirements comment-only change must pass: {r.stderr!r}"


# --- Backtick-wrapped marker must be detected (Jay 2026-06-13, session 004) ---


def test_veille_skip_in_backticks_is_detected(tmp_path):
    transcript = _write_transcript(tmp_path, {
        "role": "assistant",
        "content": [{"type": "text", "text": "Marker: `[VEILLE-SKIP] motif: typo`"}],
    })
    r = _run(transcript, file_path="lib/app/foo.ex", content="def hi, do: :ok\n")
    assert r.returncode == 0, f"backtick-wrapped VEILLE-SKIP must be detected: {r.stderr!r}"


def test_reindenting_existing_import_is_not_sensitive(tmp_path):
    # Moving an existing `import yaml` into a try/except adds NO new dependency.
    # The naive line-diff sees a "new" indented import line; the module-aware
    # check must see that `yaml` was already imported -> not sensitive.
    transcript = _write_transcript(tmp_path, {
        "role": "assistant",
        "content": [{"type": "text", "text": "[VEILLE-SKIP] motif: hotfix-known-root-cause"}],
    })
    r = _run_edit(
        transcript,
        file_path="scripts/tool.py",
        old_string="import yaml",
        new_string="try:\n    import yaml\nexcept ModuleNotFoundError:\n    yaml = None",
    )
    assert r.returncode == 0, f"re-indenting an existing import must not be sensitive: {r.stderr!r}"


def test_genuinely_new_import_stays_sensitive(tmp_path):
    # A real new external import (not present in old) stays sensitive: a SKIP
    # marker is refused, only a real [VEILLE] is accepted.
    transcript = _write_transcript(tmp_path, {
        "role": "assistant",
        "content": [{"type": "text", "text": "[VEILLE-SKIP] motif: hotfix-known-root-cause"}],
    })
    r = _run_edit(
        transcript,
        file_path="scripts/tool.py",
        old_string="import os",
        new_string="import os\nimport requests",
    )
    assert r.returncode == 2, f"a brand-new import must stay sensitive: {r.stderr!r}"
    assert b"VEILLE" in r.stderr


# --- Sticky marker: a real veille seen once covers later NON-sensitive writes
# even if it scrolled out of the scan window (Jay 2026-06-16 friction —
# long build salvo re-blocked because the [VEILLE] marker fell out of range).


def _run_sid(transcript: Path | None, *, file_path: str, content: str,
             session_id: str) -> subprocess.CompletedProcess:
    payload: dict = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "session_id": session_id,
    }
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


def test_sticky_veille_covers_nonsensitive_after_scrollout(tmp_path):
    sid = f"test-{uuid.uuid4().hex[:12]}"
    # 1) a real [VEILLE] on a non-sensitive write passes AND marks the session.
    t1 = _write_transcript(tmp_path, _veille_marker())
    r1 = _run_sid(t1, file_path="lib/app/foo.ex", content="def a, do: :ok\n", session_id=sid)
    assert r1.returncode == 0, f"setup veille should pass: {r1.stderr!r}"
    # 2) later non-sensitive write, marker scrolled out (none in transcript),
    #    SAME session -> sticky pass.
    t2 = _write_transcript(tmp_path / "later", {"role": "assistant", "content": [{"type": "text", "text": "building..."}]})
    r2 = _run_sid(t2, file_path="lib/app/bar.ex", content="def b, do: :ok\n", session_id=sid)
    assert r2.returncode == 0, f"sticky veille should cover non-sensitive: {r2.stderr!r}"


def test_sticky_does_not_cover_sensitive(tmp_path):
    sid = f"test-{uuid.uuid4().hex[:12]}"
    t1 = _write_transcript(tmp_path, _veille_marker())
    r1 = _run_sid(t1, file_path="lib/app/foo.ex", content="def a, do: :ok\n", session_id=sid)
    assert r1.returncode == 0
    # sensitive write (dep manifest) with NO fresh marker -> must still block.
    t2 = _write_transcript(tmp_path / "later", {"role": "assistant", "content": [{"type": "text", "text": "x"}]})
    r2 = _run_sid(t2, file_path="mix.exs", content='{:phoenix, "~> 1.8.8"}', session_id=sid)
    assert r2.returncode == 2, f"sticky must not cover a sensitive change: {r2.stderr!r}"


def test_sticky_survives_a_skip(tmp_path):
    sid = f"test-{uuid.uuid4().hex[:12]}"
    r1 = _run_sid(_write_transcript(tmp_path, _veille_marker()),
                  file_path="lib/app/foo.ex", content="def a, do: :ok\n", session_id=sid)
    assert r1.returncode == 0
    # a legitimate SKIP in between must NOT wipe the sticky veille flag.
    skip_t = _write_transcript(tmp_path / "skip", {"role": "assistant", "content": [{"type": "text", "text": "[VEILLE-SKIP] motif: typo"}]})
    r2 = _run_sid(skip_t, file_path="lib/app/bar.ex", content="def b, do: :ok\n", session_id=sid)
    assert r2.returncode == 0
    # now no marker at all -> still sticky.
    r3 = _run_sid(_write_transcript(tmp_path / "none", {"role": "assistant", "content": [{"type": "text", "text": "y"}]}),
                  file_path="lib/app/baz.ex", content="def c, do: :ok\n", session_id=sid)
    assert r3.returncode == 0, f"veille_seen must survive a skip: {r3.stderr!r}"


def test_no_marker_fresh_session_still_blocks(tmp_path):
    # Control: without a prior real veille this session, a missing marker blocks.
    sid = f"test-{uuid.uuid4().hex[:12]}"
    t = _write_transcript(tmp_path, {"role": "assistant", "content": [{"type": "text", "text": "no marker"}]})
    r = _run_sid(t, file_path="lib/app/foo.ex", content="def a, do: :ok\n", session_id=sid)
    assert r.returncode == 2, f"fresh session with no veille must block: {r.stderr!r}"


# --- pytest-convention test files are exempt from veille (Jay 2026-06-24) -----
# A test file legitimately imports pytest + the module under test (both may be
# external). It must NOT be flagged "sensitive: new external import". The
# existing exemptions covered `.test.`, `.spec.`, `conftest.py` but NOT the
# pytest naming `test_*.py` / `test-*.py` / `*_test.py`, nor a `__tests__/` dir
# at the PATH level. Sensitive (Layer B) must never fire on an exempt path.


def test_pytest_test_file_exempt_no_marker(tmp_path):
    # `test_*.py` importing an external lib (pytest) must pass with NO marker.
    r = _run(None, file_path="scripts/__tests__/test_portable_drift.py",
             content="import pytest\nimport requests\n\ndef test_it():\n    assert requests\n")
    assert r.returncode == 0, f"pytest test_*.py must be exempt: {r.stderr!r}"


def test_dash_test_file_exempt_no_marker(tmp_path):
    r = _run(None, file_path="scripts/test-drift.py",
             content="import pytest\n\ndef test_x():\n    assert True\n")
    assert r.returncode == 0, f"test-*.py must be exempt: {r.stderr!r}"


def test_underscore_test_suffix_exempt_no_marker(tmp_path):
    r = _run(None, file_path="pkg/foo_test.py",
             content="import pytest\n\ndef test_y():\n    assert True\n")
    assert r.returncode == 0, f"*_test.py must be exempt: {r.stderr!r}"


def test_dunder_tests_dir_path_exempt_no_marker(tmp_path):
    # A non-.test.* file living under a __tests__/ directory is exempt by PATH.
    r = _run(None, file_path="lib/__tests__/helper.ts",
             content="import { describe } from 'vitest'\nimport axios from 'axios'\n")
    assert r.returncode == 0, f"__tests__/ dir must be exempt by path: {r.stderr!r}"


def test_production_py_with_new_import_still_blocks(tmp_path):
    # Regression: a NON-test source file with a new external import still blocks
    # when no marker is present (the exemption is scoped to test files only).
    r = _run(None, file_path="src/app/service.py",
             content="import requests\n\ndef fetch():\n    return requests.get('x')\n")
    assert r.returncode == 2, f"production file must still require evidence: {r.stderr!r}"
