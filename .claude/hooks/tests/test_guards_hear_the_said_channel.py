"""Every guard that looks for something Takumi wrote hears the said channel.

2026-09-28. The journal drops Takumi's text whenever his thinking is saved as
two entries (391/391 such messages, measured 2026-09-26); a tool call is always
recorded. Each test below builds exactly that shape — split thinking, no text —
with the marker carried ONLY by a said-file write (or, for the review guards,
by the reviewer's own hand-back). Each has a control without the marker, so a
pass proves the channel, not a guard that lets everything through.

Reverse test: point transcript_reader.iter_spoken_text back at text blocks only
and every "hears" test below goes red (run 2026-09-28, recorded in the commit).

Style guards (simple-language, clock-not-fatigue) are deliberately absent: they
read the last message, always text-only, always recorded.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))

SAID = "D:/repo/.claude/state/said-1.md"


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(rel.replace("/", "_").replace("-", "_")[:-3],
                                                  HOOKS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _msg(role: str, *blocks: dict) -> dict:
    return {"type": role, "message": {"role": role, "content": list(blocks)}}


def _said(text: str, tid: str = "s1") -> list[dict]:
    """The real dropped-text shape: two thinking entries, then the said-file write."""
    return [
        _msg("assistant", {"type": "thinking", "thinking": ""}),
        _msg("assistant", {"type": "thinking", "thinking": "..."}),
        _msg("assistant", {"type": "tool_use", "id": tid, "name": "Write",
                           "input": {"file_path": SAID, "content": text}}),
        _msg("user", {"type": "tool_result", "tool_use_id": tid, "is_error": False}),
    ]


def _reviewer(report: str) -> dict:
    body = "[Subagent hand-back] The report follows:\n" + "\n".join("  " + ln for ln in report.splitlines())
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": body,
        "origin": {"kind": "peer", "from": "r1", "body": body, "handback": True}}}


def _transcript(tmp_path: Path, entries: list) -> str:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(p)


def _run(rel: str, tmp_path: Path, transcript: str, tool: str, tool_input: dict):
    """Fire the hook from an empty folder: its state files land there, never in Kata."""
    payload = {"tool_name": tool, "tool_input": tool_input, "transcript_path": transcript,
               "session_id": f"test-{tmp_path.name}"}
    return subprocess.run([sys.executable, str(HOOKS / rel)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=20, cwd=str(tmp_path))


BRIEF = ("[REVIEW-BRIEF]\n- objectif: o\n- perimetre: p\n- zones suspectes: z\n"
         "- consigne: refuter")
PASS = "[REVIEW] par relecteur le 2026-09-28 sur abcdef1 — verdict: PASS, rien"
FAIL = "[REVIEW] par relecteur le 2026-09-28 sur abcdef1 — verdict: FAIL, famille: fam-x, 1 defaut"


# --- veille ------------------------------------------------------------------


def test_pre_code_veille_check_hears_the_said_channel(tmp_path):
    # Control first: the guard remembers a marker for the session once seen.
    tool_input = {"file_path": "lib/app/foo.ex", "content": "def hello, do: :world\n"}
    silent = _transcript(tmp_path, _said("rien"))
    assert _run("guards/pre-code-veille-check.py", tmp_path, silent, "Write", tool_input).returncode == 2
    heard = _transcript(tmp_path, _said("[SKB] consulte: 11-Communication/Voice-Tone.md"))
    assert _run("guards/pre-code-veille-check.py", tmp_path, heard, "Write", tool_input).returncode == 0


def test_veille_markers_latest_marker_hears_the_said_channel(tmp_path):
    vm = _load("lib/veille_markers.py")
    assert vm.latest_marker(_transcript(tmp_path, _said("[VEILLE-SKIP] motif: test-only")))
    assert vm.latest_marker(_transcript(tmp_path, _said("rien"))) is None


def test_veille_extended_hears_the_said_channel(tmp_path):
    ve = _load("quality/veille-extended.py")
    assert ve.scan_transcript_for_marker(_transcript(tmp_path, _said("[VEILLE-SKIP] motif: test-only")))
    assert not ve.scan_transcript_for_marker(_transcript(tmp_path, _said("rien")))


def test_a_reviewer_fail_counts_for_the_veille_skip_guard(tmp_path):
    vm = _load("lib/veille_markers.py")
    t = _transcript(tmp_path, [_reviewer(FAIL)])
    assert vm.latest_review_verdict(t) == "FAIL"
    assert vm.latest_review_family(t) == "fam-x"


def test_a_reviewer_veille_is_not_takumi_veille(tmp_path):
    vm = _load("lib/veille_markers.py")
    assert vm.latest_marker(_transcript(tmp_path, [_reviewer("[VEILLE-SKIP] motif: test-only")])) is None


# --- reviews -----------------------------------------------------------------


def test_pre_deploy_review_check_hears_brief_and_reviewer(tmp_path):
    cmd = {"command": "python scripts/propagate-methodology.py Kobo"}
    heard = _transcript(tmp_path, _said(BRIEF) + [_reviewer(PASS)])
    r = _run("guards/pre-deploy-review-check.py", tmp_path, heard, "Bash", cmd)
    assert r.returncode == 0, r.stderr
    brief_only = _transcript(tmp_path, _said(BRIEF))
    assert _run("guards/pre-deploy-review-check.py", tmp_path, brief_only, "Bash", cmd).returncode == 2


def test_post_review_cause_check_hears_a_reviewer_fail(tmp_path):
    # A FAIL lost with Takumi's text used to erase the obligation it opens.
    cmd = {"command": 'git commit -m "feat: x"'}
    failed = _transcript(tmp_path, [_reviewer(FAIL)])
    assert _run("quality/post-review-cause-check.py", tmp_path, failed, "Bash", cmd).returncode == 2
    clean = _transcript(tmp_path, _said("rien"))
    assert _run("quality/post-review-cause-check.py", tmp_path, clean, "Bash", cmd).returncode == 0


def test_post_review_cause_check_hears_a_said_fail(tmp_path):
    cmd = {"command": 'git commit -m "feat: x"'}
    failed = _transcript(tmp_path, _said(FAIL))
    assert _run("quality/post-review-cause-check.py", tmp_path, failed, "Bash", cmd).returncode == 2


# --- commits and deploys -----------------------------------------------------


ROBUSTNESS = ("[ROBUSTNESS]\n- 6 mois: tient\n- cause racine: yes — x\n- alternative durable: none valid\n"
              "- appelants reels: yes — grep\n- garde a l'envers: yes")


def test_anti_quick_fix_hears_the_said_channel(tmp_path):
    aq = _load("quality/anti-quick-fix.py")
    assert aq.latest_marker(_transcript(tmp_path, _said(ROBUSTNESS)))
    assert aq.latest_marker(_transcript(tmp_path, _said("rien"))) is None


def test_axe_violations_hears_the_said_channel(tmp_path):
    axe = _load("deploy/axe-violations.py")
    assert axe._scan_markers(_transcript(tmp_path, _said("[AXE-OK] 0 violations on /"))) == (True, False)
    assert axe._scan_markers(_transcript(tmp_path, _said("rien"))) == (False, False)


def test_safari_test_required_hears_the_said_channel(tmp_path):
    saf = _load("deploy/safari-test-required.py")
    assert saf._has_safari_marker(_transcript(tmp_path, _said("[SAFARI-OK] iOS 18"))) == (True, False)
    assert saf._has_safari_marker(_transcript(tmp_path, _said("rien"))) == (False, False)


# --- advisory and metrics ----------------------------------------------------


def test_rules_vs_memory_hears_the_said_channel(tmp_path):
    tool_input = {"file_path": "x.md", "content": "x"}
    heard = _transcript(tmp_path, _said("d'apres ma memoire la veille se fait comme ca"))
    r = _run("memory/rules-vs-memory.py", tmp_path, heard, "Write", tool_input)
    assert b"Memory-claim" in r.stdout + r.stderr
    silent = _transcript(tmp_path, _said("rien"))
    r = _run("memory/rules-vs-memory.py", tmp_path, silent, "Write", tool_input)
    assert b"Memory-claim" not in r.stdout + r.stderr


def test_estimation_capture_hears_the_said_channel(tmp_path):
    heard = _transcript(tmp_path, _said("ca prendra environ 20 minutes"))
    _run("time-tracker/estimation-capture.py", tmp_path, heard, "Write", {"file_path": "x.md"})
    assert list(tmp_path.rglob("estimations.jsonl")), "the estimate was not captured"


def test_the_resume_brief_keeps_a_said_open_thread(tmp_path):
    # A 12th reader, outside transcript_reader: an [EN-SUSPENS] lost with the
    # text was lost at the next warm resume too.
    import brief_builder
    t = _transcript(tmp_path, _said("[EN-SUSPENS] le compteur est a verifier"))
    assert brief_builder.collect_open_threads(t) == ["le compteur est a verifier"]
    assert brief_builder.collect_open_threads(_transcript(tmp_path, _said("rien"))) == []


def test_session_end_metrics_counts_said_markers(tmp_path):
    sem = _load("lifecycle/session-end-metrics.py")
    counts = sem._veille_markers(_transcript(tmp_path, _said("[VEILLE] next@16.1 verifie 2026-09-28 via npm")))
    assert counts["VEILLE"] == 1
