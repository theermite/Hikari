"""Tests for quality/post-review-cause-check.py — a failed review must teach.

Jay 2026-08-10, after a session where five independent reviews in a row rejected
the same family of defect: "le problème n'est pas que tu aies fait une erreur,
c'est que tu as persévéré dans cette erreur. Dès que l'erreur est détectée, il
faut prendre du recul pour savoir d'où elle vient, la corriger, et mettre en
place quelque chose qui fera qu'elle n'est pas reproduite."

So a FAIL verdict is not a warning to note — it opens an obligation. The next
commit must name the FAMILY of the defect, its cause, and what stops it coming
back. And a family that shows up twice forbids patching: the approach changes.

The hook is loaded by file path (hyphen in name -> not importable as a module).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "post-review-cause-check.py"
_spec = importlib.util.spec_from_file_location("post_review_cause_check", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


FULL_CAUSE = (
    "[CAUSE]\n"
    "- famille: analyse du shell faite a la main dans chaque garde-fou\n"
    "- cause: deux analyseurs prives qui divergent\n"
    "- ce qui empeche la repetition: un analyseur partage, avec ses tests\n"
)


# --- reading the verdicts ----------------------------------------------------


def test_a_failed_verdict_is_seen():
    text = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: FAIL, 3 defauts"
    assert gate.last_verdict([text]) == "FAIL"


def test_a_passing_verdict_is_seen():
    text = "[REVIEW] par contexte-neuf le 2026-08-10 — verdict: PASS, 0 defaut"
    assert gate.last_verdict([text]) == "PASS"


def test_the_most_recent_verdict_wins():
    texts = [
        "[REVIEW] par x le 2026-08-10 — verdict: PASS, corrige",
        "[REVIEW] par x le 2026-08-10 — verdict: FAIL, 2 defauts",
    ]  # most recent first
    assert gate.last_verdict(texts) == "PASS"


def test_no_review_at_all_is_not_a_verdict():
    assert gate.last_verdict(["on a bien avance ce soir"]) is None


# --- the cause marker --------------------------------------------------------


def test_a_complete_cause_marker_is_accepted():
    assert gate.find_cause(FULL_CAUSE) is not None


def test_a_cause_marker_missing_the_family_is_refused():
    text = "[CAUSE]\n- cause: x\n- ce qui empeche la repetition: y\n"
    assert gate.find_cause(text) is None


def test_a_cause_marker_missing_the_prevention_is_refused():
    text = "[CAUSE]\n- famille: x\n- cause: y\n"
    assert gate.find_cause(text) is None


def test_an_empty_field_is_refused():
    text = "[CAUSE]\n- famille:\n- cause: y\n- ce qui empeche la repetition: z\n"
    assert gate.find_cause(text) is None


# --- the gate ----------------------------------------------------------------


def test_a_commit_after_a_failed_review_needs_the_cause():
    message = "fix(hooks): corrige le cas signale"
    assert gate.verdict(message, ["[REVIEW] par x le 2026-08-10 — verdict: FAIL, 3 defauts"], failures=1) is not None


def test_a_commit_carrying_the_cause_passes():
    message = f"fix(hooks): corrige la famille\n\n{FULL_CAUSE}"
    assert gate.verdict(message, ["[REVIEW] par x le 2026-08-10 — verdict: FAIL, 3 defauts"], failures=1) is None


def test_a_commit_after_a_passing_review_is_free():
    texts = ["[REVIEW] par x le 2026-08-10 — verdict: PASS, rien a signaler"]
    assert gate.verdict("fix(hooks): un detail", texts, failures=0) is None


def test_a_commit_with_no_review_at_all_is_free():
    assert gate.verdict("feat: un ajout", ["rien"], failures=0) is None


# --- the second time is not a patch ------------------------------------------


def test_a_second_failure_says_stop_patching():
    message = "fix(hooks): corrige le nouveau cas signale"
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, encore un contournement"
    blocked = gate.verdict(message, [text], failures=2)
    assert blocked is not None
    assert "approche" in blocked.lower()


def test_a_second_failure_still_needs_more_than_a_marker():
    """Two failures in a row: the marker alone is no longer enough to proceed."""
    message = f"fix(hooks): rustine\n\n{FULL_CAUSE}"
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, meme famille"
    blocked = gate.verdict(message, [text], failures=2)
    assert blocked is not None
    assert "famille" in blocked.lower()


def test_mentioning_a_commit_in_a_message_is_not_a_commit():
    """Same family as the whole evening: read tokens, never raw substrings."""
    assert not gate.is_commit('echo "pense a git commit plus tard"')


def test_a_real_commit_is_seen():
    assert gate.is_commit('git commit -m "un vrai commit"')


def test_a_commit_in_another_repo_is_seen():
    assert gate.is_commit('git -C ~/Shinzo commit -m "x"')


def test_an_unrelated_commit_can_be_excused_with_a_closed_motif():
    message = "docs: corrige une coquille\n\n[CAUSE-SKIP] motif: sans-rapport"
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, 2 defauts"
    assert gate.verdict(message, [text], failures=1) is None


def test_every_documented_skip_motif_is_accepted():
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, 2 defauts"
    for motif in gate.SKIP_MOTIFS:
        message = f"docs: x\n\n[CAUSE-SKIP] motif: {motif}"
        assert gate.verdict(message, [text], failures=1) is None, motif


def test_an_invented_skip_motif_is_refused():
    message = "fix: rustine\n\n[CAUSE-SKIP] motif: pas envie"
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, 2 defauts"
    assert gate.verdict(message, [text], failures=1) is not None


def test_the_skip_does_not_excuse_a_second_failure():
    """Twice in a row, no excuse: the approach has to move."""
    message = "fix: rustine\n\n[CAUSE-SKIP] motif: sans-rapport"
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, meme famille"
    assert gate.verdict(message, [text], failures=2) is not None


def test_a_second_failure_passes_once_the_approach_changed():
    message = (
        "refactor(hooks): un seul analyseur partage\n\n"
        f"{FULL_CAUSE}"
        "- approche changee: oui — l'analyse maison est remplacee par un module commun\n"
    )
    text = "[REVIEW] par x le 2026-08-10 — verdict: FAIL, meme famille"
    assert gate.verdict(message, [text], failures=2) is None
