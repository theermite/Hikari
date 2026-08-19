"""post-write-guard.py — the empty-test detector must read the real test body.

Why this file exists (brief `Couche-Etat-Hooks-Defauts-2026-08-18.md`, défaut 4).
`_find_empty_ts_tests` searched for an assertion pattern in a FIXED 500-char
window after `it(`/`test(`. A real test with a long comment before its first
assertion pushes that assertion past the window — the check reports a false
"empty test" on code that has a real assertion. Reproduced 2026-08-19 in
Hikari: a legitimate unsubscribe test, assertion at char 557, blocked. Worked
around on the spot by shortening the comment — a real test, misdetected,
patched around instead of a real defect.

The fix bounds the search on the real test call (balanced parentheses, quote-
aware) instead of a character count, so an assertion is found wherever it
actually sits, and a genuinely empty test is still caught however long its
body is.

DOWNGRADE (2026-08-19, same evening, 3rd independent-review round): three
heuristic-scanning defects surfaced in a row on this exact check — the
500-char window, then an apostrophe-in-comment false negative, then a regex-
literal false negative AND (once patched with a second independent bound) a
`.test(`-as-member-access false POSITIVE that blocked ordinary
`SOME_REGEX.test(value)` code. Jay's call: this check moves from BLOCKING to
WARNING. It still runs and still names suspects — it just can no longer
refuse a legitimate write over its own heuristic's blind spot. Every test
below that used to assert `returncode == 2` / `"BLOCKED"` now asserts
`returncode == 0` / `"WARNING"`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "post-write-guard.py"


def _run(tmp_path: Path, filename: str, content: str):
    target = tmp_path / filename
    target.write_text(content, encoding="utf-8")
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
    )
    return subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )


def test_assertion_past_500_chars_is_not_a_false_positive(tmp_path):
    # The Hikari case: a long explanatory comment pushes the real assertion
    # well past the old fixed window, but it IS there.
    long_comment = "// " + ("this test exercises the unsubscribe cleanup path. " * 12)
    content = (
        "describe('cleanup', () => {\n"
        "  it('unsubscribes on unmount', () => {\n"
        f"    {long_comment}\n"
        "    const unsub = subscribe();\n"
        "    unsub();\n"
        "    expect(handler).not.toHaveBeenCalled();\n"
        "  });\n"
        "});\n"
    )
    assert content.index("expect(") > 500, "fixture must reproduce >500 chars before the assertion"
    result = _run(tmp_path, "cleanup.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr


def test_genuinely_empty_test_with_long_body_is_still_flagged(tmp_path):
    long_comment = "// " + ("this comment explains the setup in great detail. " * 20)
    content = (
        "describe('cleanup', () => {\n"
        "  it('does nothing useful', () => {\n"
        f"    {long_comment}\n"
        "    const unsub = subscribe();\n"
        "    unsub();\n"
        "  });\n"
        "});\n"
    )
    assert len(content) > 500, "fixture must reproduce a body longer than the old window"
    result = _run(tmp_path, "cleanup.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "does nothing useful" in result.stderr


# --- independent review 2026-08-19: the paren-balance fix above introduced ---
# a fresh false negative, comment-apostrophe contamination. `_find_matching_paren`
# treated a single quote inside a `//` comment as opening a string, so an
# unterminated "string" swallowed everything up to and including a LATER
# test's real assertion — an empty test read the neighbor's `expect(...)` as
# its own and passed silently. Reproduced by the reviewer, verified here.


def test_apostrophe_in_line_comment_does_not_hide_an_empty_test(tmp_path):
    content = (
        "it('should do nothing yet', () => {\n"
        "  // it's not implemented\n"
        "  const x = 1;\n"
        "});\n"
        "\n"
        "it('a real one', () => {\n"
        "  expect(1).toBe(1);\n"
        "});\n"
    )
    result = _run(tmp_path, "apostrophe.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "should do nothing yet" in result.stderr
    assert "a real one" not in result.stderr


def test_apostrophe_in_block_comment_does_not_hide_an_empty_test(tmp_path):
    content = (
        "it('should do nothing yet', () => {\n"
        "  /* doesn't do anything yet, don't rely on it */\n"
        "  const x = 1;\n"
        "});\n"
        "\n"
        "it('a real one', () => {\n"
        "  expect(1).toBe(1);\n"
        "});\n"
    )
    result = _run(tmp_path, "block-comment.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "should do nothing yet" in result.stderr


def test_comment_with_apostrophe_does_not_block_a_real_assertion(tmp_path):
    # Symmetric case: the comment sits BEFORE a real assertion in the SAME test.
    content = (
        "it('handles it', () => {\n"
        "  // it's tricky here, don't skip this\n"
        "  expect(1).toBe(1);\n"
        "});\n"
    )
    result = _run(tmp_path, "same-test.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr


def test_short_empty_test_is_still_flagged(tmp_path):
    content = (
        "it('a real gap', () => {\n"
        "  const x = 1;\n"
        "});\n"
    )
    result = _run(tmp_path, "gap.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "a real gap" in result.stderr


def test_short_test_with_assertion_passes(tmp_path):
    content = (
        "it('adds', () => {\n"
        "  expect(1 + 1).toBe(2);\n"
        "});\n"
    )
    result = _run(tmp_path, "add.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr


# --- independent review 2026-08-19, round 2: 2nd FAIL on the same family ----
# (comment/quote/paren scanning in _find_matching_paren). A regex literal
# ending in a doubled slash (`/\/\//`) reads as `//` to the comment-skipper,
# which then treats the rest of the file as commented-out and never returns
# to depth 0 — the scan runs to EOF and the raw-text assertion search finds a
# NEIGHBORING test's `expect(...)`, masking a genuinely empty test. Per
# Independent-Review.md, a second failure on the same family means patching
# the reported case again is not enough — Jay approved option B: an
# independent second bound (the next `it(`/`test(`/`describe(` occurrence,
# found by a plain textual search with NO comment/quote/regex awareness at
# all) caps the search window regardless of what the paren scanner computed.
# The two techniques must fail in the SAME way to both miss an empty test —
# a regex literal fools the char-by-char scanner but not the plain keyword
# search, and vice versa for a stray unmatched paren inside a string.


def test_regex_literal_does_not_hide_an_empty_test(tmp_path):
    content = (
        "it('match slashes, no assertion', () => {\n"
        "  const x = content.match(/\\/\\//);\n"
        "});\n"
        "\n"
        "it('victim2', () => {\n"
        "  expect(1).toBe(1);\n"
        "});\n"
    )
    result = _run(tmp_path, "regex-literal.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "match slashes, no assertion" in result.stderr
    assert "victim2" not in result.stderr


def test_regex_literal_does_not_block_a_real_assertion_in_same_test(tmp_path):
    content = (
        "it('splits on slashes', () => {\n"
        "  const parts = content.split(/\\/\\//);\n"
        "  expect(parts.length).toBe(2);\n"
        "});\n"
    )
    result = _run(tmp_path, "regex-literal-ok.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" not in result.stderr


def test_last_test_in_file_with_regex_literal_and_no_assertion_is_caught(tmp_path):
    # No "next test" boundary exists here — EOF must still bound the search.
    content = (
        "it('match slashes, no assertion', () => {\n"
        "  const x = content.match(/\\/\\//);\n"
        "});\n"
    )
    result = _run(tmp_path, "regex-literal-last.test.ts", content)
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "match slashes, no assertion" in result.stderr


# --- independent review 2026-08-19, round 3: 3rd FAIL on the same family ----
# (the min-of-two-bounds fix above). `_next_test_boundary`'s dumb textual
# search for `it(`/`test(`/`describe(` does not distinguish a real Jest
# declaration from a MEMBER-ACCESS call — `EMAIL_REGEX.test(candidate)`, one
# of the most common JS/TS idioms there is, matches `test(` and truncates the
# search window before the real assertion that follows. This is what tipped
# the decision to WARNING: a false BLOCK on ordinary regex-validation test
# code was judged worse than a false negative the check would otherwise miss.


def test_member_access_test_call_does_not_block_a_real_assertion(tmp_path):
    content = (
        "it('validates email format', () => {\n"
        "  const isValid = EMAIL_REGEX.test(candidate);\n"
        "  expect(isValid).toBe(true);\n"
        "});\n"
    )
    result = _run(tmp_path, "email-validation.test.ts", content)
    assert result.returncode == 0, result.stderr
    # The heuristic may still WARN here (known blind spot) — what matters,
    # now that this check is non-blocking, is that it never refuses the write.
