"""Tests for guards/write-guard.py — end to end, with the real payload shape.

Why this file exists (2026-08-07). The guard had no tests at all, and in
production it CRASHED on every single invocation with
`ValueError: not enough values to unpack (expected 5, got 4)` — before running
a single check. Two defects compounding:

  1. `get_file_info` read `data["file_path"]` at the top level, while the
     harness nests it under `tool_input`. So the path was always empty.
  2. The empty-path branch returned a 4-tuple where `main` unpacks 5, and the
     `info is None` guard never caught it because a 4-tuple is truthy.

Everything this guard is supposed to block had therefore never blocked
anything: JWT in localStorage, HS256, secrets in files, unpinned GitHub
Actions, Lego duplication, hardcoded i18n strings, the .env.example rule. All
of them documented as hook-enforced.

These tests run the hook as a subprocess. A unit test on a check function
cannot catch a guard that dies before calling it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "write-guard.py"


def _run(file_path: str, content: str, tool: str = "Write"):
    payload = json.dumps(
        {"tool_name": tool, "tool_input": {"file_path": file_path, "content": content}}
    )
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )


def test_the_guard_runs_at_all():
    # The regression that hid every other one: it used to exit 1 on any input.
    result = _run("src/lib/x.ts", "export const a = 1;")
    assert result.returncode == 0, result.stderr
    assert "ValueError" not in result.stderr


def test_jwt_in_localstorage_is_blocked():
    # Security.md: "httpOnly cookies ONLY — never localStorage (hook-enforced)".
    result = _run("src/lib/auth.ts", 'localStorage.setItem("jwt", token);')
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_hs256_is_blocked():
    # Security.md: RS256 or ES256, never HS256 in production.
    result = _run("src/lib/token.ts", 'const algorithm = "HS256";')
    assert result.returncode == 2, result.stderr
    assert "BLOCKED" in result.stderr


def test_an_ordinary_file_passes():
    result = _run("src/lib/format.ts", "export function pad(n: number) { return n; }")
    assert result.returncode == 0, result.stderr


def test_an_edit_payload_is_read_too():
    # Edit sends `new_string` rather than `content`; both shapes must reach the
    # checks, or half the writes in a session go unguarded.
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/lib/auth.ts",
                "new_string": 'localStorage.setItem("jwt", token);',
            },
        }
    )
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 2, result.stderr


def test_a_payload_without_a_path_exits_cleanly():
    payload = json.dumps({"tool_name": "Write", "tool_input": {}})
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "ValueError" not in result.stderr


# --- showing a forbidden pattern is not doing it ----------------------------
#
# Found by an independent review on 2026-08-11, the day this guard came back to
# life: a security test asserting on a fake key, and a doc showing the
# anti-pattern as a counter-example, were both blocked. Those are exactly the
# files that document the rule. The strings are built at runtime so this test
# file does not trip the guard it tests.

_JWT_IN_STORAGE = "localStorage.set" + "Item('jwt', token)"
_FAKE_KEY = "sk_live_" + "A" * 24


def test_a_test_file_may_show_the_forbidden_storage():
    assert _run("D:/p/src/auth.test.ts", _JWT_IN_STORAGE).returncode == 0


def test_a_doc_may_teach_the_counter_example():
    assert _run("D:/p/docs/Security-Examples.md", _JWT_IN_STORAGE).returncode == 0


def test_a_test_fixture_may_hold_a_fake_key():
    assert _run("D:/p/src/billing.test.ts", _FAKE_KEY).returncode == 0


def test_real_code_still_cannot_store_a_token_there():
    assert _run("D:/p/src/auth.ts", _JWT_IN_STORAGE).returncode == 2


def test_real_code_still_cannot_hold_a_key():
    assert _run("D:/p/src/config.ts", _FAKE_KEY).returncode == 2


def test_a_document_stays_watched_for_real_secrets():
    """A doc may quote an anti-pattern, but a pasted key is still a leak."""
    assert _run("D:/p/docs/Notes.md", _FAKE_KEY).returncode == 2
