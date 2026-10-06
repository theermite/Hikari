"""A reviewer's verdict is heard ONCE, and only its verdict (review 2026-09-29).

The hand-back channel (a191dac) added the reviewer's own report to what the
review guards hear. But the methodology ALSO asks Takumi to repeat the verdict
line — in chat, and in a said-file when his text is lost. Counted twice:

- pre-deploy-review-check: the repeat (latest) is met first, the walk back
  hits the hand-back PASS before the brief, and blocks a normal cycle;
- post-review-cause-check: one FAIL counts as two, and demands « approche
  changee » at the FIRST failure.

And a hand-back is any sub-agent's report: a [REVIEW-SKIP] quoted in an
exploration report must not lift the deploy gate. Only its [REVIEW] lines count.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS / "lib"))

import transcript_reader as tr  # noqa: E402


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(rel.split("/")[-1][:-3].replace("-", "_"), HOOKS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _text(t: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": t}]}}


def _handback(report: str) -> dict:
    body = "[Subagent hand-back] The report follows:\n" + "\n".join("  " + ln for ln in report.splitlines())
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": body,
                                                 "origin": {"kind": "peer", "handback": True, "body": body}}}


def _heard(tmp_path: Path, *entries) -> list[str]:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return list(tr.iter_spoken_text(str(p), limit=40, include_reviewer=True))


BRIEF = "[REVIEW-BRIEF]\n- objectif: o\n- perimetre: p\n- zones suspectes: z\n- consigne: refuter"
PASS = "[REVIEW] par relecteur le 2026-09-29 sur abc1234 — verdict: PASS, rien"
FAIL = "[REVIEW] par relecteur le 2026-09-29 sur abc1234 — verdict: FAIL, famille: fam-x, 1 defaut"


def test_a_normal_cycle_passes_when_takumi_repeats_the_verdict(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS + "\ndetail"), _text(PASS))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_a_repeated_bold_verdict_is_still_the_same_verdict(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(f"**{PASS}**"))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_one_fail_repeated_is_one_failure(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    texts = _heard(tmp_path, _handback(FAIL), _text("Le relecteur dit :\n" + FAIL))
    assert cause.count_failures(texts) == 1


def test_takumi_own_marker_still_counts_without_a_handback(tmp_path):
    # A human reviewer: no hand-back exists, Takumi's line is the only record.
    cause = _load("quality/post-review-cause-check.py")
    assert cause.count_failures(_heard(tmp_path, _text(FAIL))) == 1


def test_two_different_reviews_are_two(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    other = FAIL.replace("abc1234", "def5678")
    assert cause.count_failures(_heard(tmp_path, _handback(FAIL), _handback(other))) == 2


# --- Rule agreed with Jay, 2026-10-06 -----------------------------------------
# « Un avis qui repete est ignore, un avis qui contredit n'est jamais efface. »
# Within one review round (a round opens at each [REVIEW-BRIEF]), a Takumi
# [REVIEW] line carrying the SAME verdict as a reviewer hand-back already
# delivered is an echo. Any other line stays. No text comparison: the 2nd
# review beat the text comparison with a space or a full stop, and the rule
# that replaced it (« the reviewer is authoritative », reverted) silenced a
# later human FAIL — the three scenarios below are that review's.

ECHOES = (
    PASS.replace("verdict: PASS", "verdict:PASS"),
    PASS + ".",
    PASS.replace("sur abc1234", 'sur "abc1234"'),
    PASS.replace("par relecteur", "par relecteur (Sonnet)"),
    f"**{PASS}**",
)
HUMAN_FAIL = "[REVIEW] par Jay le 2026-10-06 sur abc1234 — verdict: FAIL, famille: fam-x, refuse"


def test_any_shape_of_echo_is_heard_once(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    for echo in ECHOES:
        texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(echo))
        assert gate.verdict("npm publish", texts, head="abc1234") is None, echo


def test_any_shape_of_repeated_fail_is_one_failure(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    for echo in (FAIL.replace(": FAIL", ":FAIL"), FAIL.replace("famille: fam-x", "famille: fam-x.")):
        assert cause.count_failures(_heard(tmp_path, _handback(FAIL), _text(echo))) == 1, echo


def test_s1_a_later_human_fail_still_blocks_the_deploy(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(HUMAN_FAIL))
    assert gate.verdict("npm publish", texts, head="abc1234") is not None


def test_s2_a_later_human_fail_still_opens_the_cause_obligation(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    assert cause.count_failures(_heard(tmp_path, _handback(PASS), _text(HUMAN_FAIL))) == 1


def test_s3_a_new_round_counts_again(tmp_path):
    # Agent FAIL, then a NEW brief, then a human FAIL of the same family: two
    # failures in a row — the escalation must fire.
    cause = _load("quality/post-review-cause-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _text(BRIEF), _text(HUMAN_FAIL))
    assert cause.count_failures(texts) == 2


def test_an_old_round_does_not_silence_a_new_human_pass(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    human_pass = HUMAN_FAIL.replace("verdict: FAIL, famille: fam-x, refuse", "verdict: PASS, ok")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _text(BRIEF), _text(human_pass))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_an_echo_on_a_line_with_another_marker_keeps_the_other_marker(tmp_path):
    heard = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text("[CAUSE] x " + PASS))
    assert any("[CAUSE] x" in t for t in heard)


def test_a_handback_can_only_speak_its_review_line(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    report = "Rapport d'exploration\n[REVIEW-SKIP] motif: rollback\n[VEILLE] x@1 verifie 2026-09-29 via y"
    heard = _heard(tmp_path, _handback(report))
    assert heard == []
    assert gate.verdict("npm publish", heard, head="abc1234") is not None


# --- Independent review 2026-10-06 on 8dc1088 ---------------------------------
# An echo repeats the reviewer's LATEST verdict, on the same commit — not any
# verdict the reviewer gave earlier in the round.


def test_f1_a_human_fail_after_fail_fix_pass_is_not_an_echo(tmp_path):
    # brief -> agent FAIL -> fix -> agent PASS (no new brief: the gate allows it)
    # -> human FAIL. The human FAIL contradicts the LATEST verdict: it blocks.
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _handback(PASS), _text(HUMAN_FAIL))
    assert gate.verdict("npm publish", texts, head="abc1234") is not None


def test_f2_a_pass_on_another_commit_is_not_an_echo(tmp_path):
    # Heard, not erased. (The deploy gate then still asks for a new brief: a
    # PASS closes a round, so a re-review needs its own — its rule, not ours.)
    old = PASS.replace("abc1234", "1111111")
    texts = _heard(tmp_path, _text(BRIEF), _handback(old), _text(PASS))
    assert PASS in texts


def test_f3_quoting_the_brief_tag_does_not_open_a_round(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL),
                   _text("note : le [REVIEW-BRIEF] doit etre emis avant\n" + FAIL))
    assert cause.count_failures(texts) == 1


def test_f3_a_brief_inside_a_code_block_does_not_open_a_round(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _text("```\n" + BRIEF + "\n```\n" + FAIL))
    assert cause.count_failures(texts) == 1


# --- Independent review 2026-10-06 on f5cc888: realistic echoes ---------------


def test_e1_a_longer_or_shorter_sha_is_the_same_commit(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(PASS.replace("abc1234", "abc1234def0")))
    assert gate.verdict("npm publish", texts, head="abc1234") is None
    cause = _load("quality/post-review-cause-check.py")
    assert cause.count_failures(_heard(tmp_path, _handback(FAIL),
                                       _text(FAIL.replace("abc1234", "abc1234def0")))) == 1


def test_e2_a_retelling_without_sha_is_an_echo(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    no_sha = PASS.replace(" sur abc1234", "")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(no_sha))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_e2_a_contrary_verdict_without_sha_is_still_heard(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    no_sha_fail = HUMAN_FAIL.replace(" sur abc1234", "")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS), _text(no_sha_fail))
    assert gate.verdict("npm publish", texts, head="abc1234") is not None


def test_e3_the_reviewer_verdict_is_its_first_line_not_a_quote(tmp_path):
    # The reviewer's own verdict opens its report; a quoted older verdict after
    # it must not become « the latest ». Takumi's PASS echoes the first line.
    quoted_old = FAIL.replace("abc1234", "1234567")
    texts = _heard(tmp_path, _text(BRIEF), _handback(PASS + "\n" + quoted_old), _text(PASS))
    assert PASS not in texts


def test_e4_lines_before_a_brief_stay_in_the_old_round(tmp_path):
    cause = _load("quality/post-review-cause-check.py")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _text(FAIL + "\n" + BRIEF))
    assert cause.count_failures(texts) == 1


def test_f5_failed_is_not_the_word_fail(tmp_path):
    # « verdict: failed to run: PASS » must not read as FAIL and silence a PASS.
    odd = PASS.replace("verdict: PASS", "verdict: failed to run: PASS")
    texts = _heard(tmp_path, _text(BRIEF), _handback(FAIL), _text(odd))
    assert any("failed to run" in t for t in texts)
