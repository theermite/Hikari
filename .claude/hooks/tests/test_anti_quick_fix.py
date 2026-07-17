"""anti-quick-fix.py — PreToolUse Bash gate on `fix:` / `hotfix:` commits.

Behavior under test:
- Trigger ONLY on `git commit -m "fix:..."` / `"hotfix:..."` (and `fix(scope):` etc.)
- Pass-through on feat:, refactor:, chore:, --amend, no -m, non-commit commands
- BLOCK when no [ROBUSTNESS] or [ROBUSTNESS-SKIP] marker in recent transcript
- BLOCK when [ROBUSTNESS] body lacks any of the 3 required labels
  (6 mois / cause racine / alternative durable)
- BLOCK when [ROBUSTNESS-SKIP] motif is outside the closed enum
- BLOCK when subject mentions regression and only a SKIP is present (Layer B)
- PASS when full marker is present and well-formed
- PASS when SKIP marker with valid motif is present (and under threshold)

Tests are isolated by giving each one a unique session_id (counter state file)
and a fresh transcript file under tmp_path.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "anti-quick-fix.py"


# --- Helpers ----------------------------------------------------------------


def _make_transcript(tmp_path: Path, *texts: str) -> Path:
    """Write a JSONL transcript whose entries contain the given text blocks."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    transcript = tmp_path / "transcript.jsonl"
    lines: list[str] = []
    for text in texts:
        lines.append(json.dumps({"role": "assistant", "content": text}))
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return transcript


def _run(cmd: str, *, transcript: Path | None = None,
         session_id: str | None = None) -> subprocess.CompletedProcess:
    payload: dict = {
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    }
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    if session_id is not None:
        payload["session_id"] = session_id
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=10,
    )


def _sid() -> str:
    """Fresh session id per test (isolates the counter state file)."""
    return f"test-{uuid.uuid4().hex[:12]}"


def _full_marker() -> str:
    return (
        "[ROBUSTNESS]\n"
        "- 6 mois: la cause racine est eliminee par validation au boundary\n"
        "- cause racine: oui -- input non valide a la frontiere\n"
        "- alternative durable: aucune valable, le fix est minimal\n"
    )


# --- Non-triggers (pass through silently) -----------------------------------


def test_silent_on_non_commit_command():
    r = _run("ls -la")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_git_status():
    r = _run("git status")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_amend():
    r = _run("git commit --amend --no-edit")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_feat_commit():
    r = _run("git commit -m 'feat(auth): add SSO'")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_refactor_commit():
    r = _run("git commit -m 'refactor(core): extract helper'")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_chore_commit():
    r = _run("git commit -m 'chore: bump deps'")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_commit_without_dash_m():
    # `git commit` without -m opens an editor; the hook cannot read it -> pass through.
    r = _run("git commit")
    assert r.returncode == 0
    assert r.stderr == b""


def test_silent_on_empty_stdin():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0


def test_silent_on_malformed_json():
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=b"not json at all",
        capture_output=True,
        timeout=10,
    )
    assert r.returncode == 0


# --- Blocks: missing / malformed marker -------------------------------------


def test_blocks_fix_commit_without_marker(tmp_path):
    transcript = _make_transcript(tmp_path, "some unrelated assistant text")
    r = _run("git commit -m 'fix(auth): handle null token'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 2
    assert b"BLOCKED" in r.stderr
    assert b"ROBUSTNESS" in r.stderr


def test_blocks_hotfix_commit_without_marker(tmp_path):
    transcript = _make_transcript(tmp_path, "no marker here")
    r = _run("git commit -m 'hotfix: deploy rollback'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 2
    assert b"BLOCKED" in r.stderr


def test_blocks_when_robustness_body_incomplete(tmp_path):
    bad_marker = "[ROBUSTNESS]\n- 6 mois: yes\n- cause racine: yes\n"  # missing alternative
    transcript = _make_transcript(tmp_path, bad_marker)
    r = _run("git commit -m 'fix: nullable user id'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 2
    assert b"missing required label" in r.stderr
    assert b"alternative durable" in r.stderr


def test_blocks_when_skip_motif_not_in_enum(tmp_path):
    transcript = _make_transcript(tmp_path, "[ROBUSTNESS-SKIP] motif: because-i-said-so")
    r = _run("git commit -m 'fix: trivial'", transcript=transcript, session_id=_sid())
    assert r.returncode == 2
    assert b"not in closed enum" in r.stderr


# --- Layer B: regression / revert demands full marker -----------------------


def test_blocks_skip_when_subject_mentions_regression(tmp_path):
    transcript = _make_transcript(tmp_path, "[ROBUSTNESS-SKIP] motif: typo")
    r = _run("git commit -m 'fix(auth): regression on logout'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 2
    assert b"regression" in r.stderr.lower()


def test_allows_revert_skip_on_revert_subject(tmp_path):
    transcript = _make_transcript(tmp_path, "[ROBUSTNESS-SKIP] motif: revert")
    # Layer B exception: motif=revert IS allowed when subject contains 'Revert'.
    r = _run("git commit -m 'fix: Revert previous change'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 0


# --- Passes: full marker accepted -------------------------------------------


def test_passes_with_full_robustness_marker(tmp_path):
    transcript = _make_transcript(tmp_path, _full_marker())
    r = _run("git commit -m 'fix(api): clamp pagination size'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 0
    assert r.stderr == b""


def test_passes_with_skip_typo(tmp_path):
    transcript = _make_transcript(tmp_path, "[ROBUSTNESS-SKIP] motif: typo")
    r = _run("git commit -m 'fix: typo in error message'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 0


def test_passes_with_skip_lint_fix(tmp_path):
    transcript = _make_transcript(tmp_path, "[ROBUSTNESS-SKIP] motif: lint-fix")
    r = _run("git commit -m 'fix(style): apply ruff format'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 0


def test_passes_with_fix_scope_syntax(tmp_path):
    # `fix(scope):` form should be detected as gated.
    transcript = _make_transcript(tmp_path, _full_marker())
    r = _run("git commit -m 'fix(payment): handle 3DS challenge timeout'",
             transcript=transcript, session_id=_sid())
    assert r.returncode == 0


# --- Layer C: SKIP counter --------------------------------------------------


def test_blocks_after_three_consecutive_skips(tmp_path):
    """Three distinct skip markers in a row -> 3rd one is blocked."""
    sid = _sid()

    t1 = _make_transcript(tmp_path / "t1", "[ROBUSTNESS-SKIP] motif: typo")
    r1 = _run("git commit -m 'fix: typo a'", transcript=t1, session_id=sid)
    assert r1.returncode == 0, f"skip 1 should pass: {r1.stderr!r}"

    t2 = _make_transcript(tmp_path / "t2", "[ROBUSTNESS-SKIP] motif: formatting")
    r2 = _run("git commit -m 'fix: format b'", transcript=t2, session_id=sid)
    assert r2.returncode == 0, f"skip 2 should pass: {r2.stderr!r}"

    t3 = _make_transcript(tmp_path / "t3", "[ROBUSTNESS-SKIP] motif: comment-only")
    r3 = _run("git commit -m 'fix: comment c'", transcript=t3, session_id=sid)
    assert r3.returncode == 2
    assert b"threshold reached" in r3.stderr


def test_silent_on_fix_string_inside_node_e(tmp_path):
    # `node -e "...git commit -m \"fix:\"..."` is a JS test of a regex, NOT a real
    # commit. `git commit` lives inside a quoted -e argument -> must pass through.
    transcript = _make_transcript(tmp_path, "no marker")
    cmd = 'node -e "const m = \'git commit -m \\"fix: x\\"\'; console.log(/fix:/.test(m))"'
    r = _run(cmd, transcript=transcript, session_id=_sid())
    assert r.returncode == 0, f"git commit inside node -e must not gate: {r.stderr!r}"
    assert r.stderr == b""


def test_silent_on_fix_string_inside_echo(tmp_path):
    transcript = _make_transcript(tmp_path, "no marker")
    r = _run("""echo 'git commit -m "fix: y"'""", transcript=transcript, session_id=_sid())
    assert r.returncode == 0, f"git commit inside echo must not gate: {r.stderr!r}"
    assert r.stderr == b""


def test_real_fix_commit_in_compound_still_gates(tmp_path):
    # Regression: a REAL `git commit -m "fix:"` as a command (even chained after
    # &&) must still gate when no marker is present.
    transcript = _make_transcript(tmp_path, "no marker")
    r = _run('cd repo && git commit -m "fix(api): clamp size"',
             transcript=transcript, session_id=_sid())
    assert r.returncode == 2, f"a real chained fix commit must still gate: {r.stderr!r}"
    assert b"ROBUSTNESS" in r.stderr


def test_full_marker_resets_skip_counter(tmp_path):
    """A real [ROBUSTNESS] marker resets the SKIP counter to 0."""
    sid = _sid()

    t1 = _make_transcript(tmp_path / "s1", "[ROBUSTNESS-SKIP] motif: typo")
    assert _run("git commit -m 'fix: a'", transcript=t1, session_id=sid).returncode == 0

    t2 = _make_transcript(tmp_path / "s2", "[ROBUSTNESS-SKIP] motif: formatting")
    assert _run("git commit -m 'fix: b'", transcript=t2, session_id=sid).returncode == 0

    # Full marker -> resets counter
    treal = _make_transcript(tmp_path / "real", _full_marker())
    assert _run("git commit -m 'fix: real'", transcript=treal, session_id=sid).returncode == 0

    # Another SKIP after reset should now pass (counter back to 1).
    t3 = _make_transcript(tmp_path / "s3", "[ROBUSTNESS-SKIP] motif: comment-only")
    r3 = _run("git commit -m 'fix: c'", transcript=t3, session_id=sid)
    assert r3.returncode == 0, f"skip after reset should pass: {r3.stderr!r}"
