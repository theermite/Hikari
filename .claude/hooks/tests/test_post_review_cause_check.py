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


# --- the counter counts DEFECTS, never rounds ---------------------------------
#
# Jay 2026-08-30: "si la relecture trouve une nouvelle erreur ce n'est pas une
# deuxieme tentative. Mon point de vue est que si tu essaies 2 ou 3 fois de
# corriger LA MEME erreur et n'y parviens pas, tu dois prendre du recul."
#
# The first version counted consecutive FAIL verdicts whatever they were about.
# Two reviews finding two DIFFERENT defects escalated to "change your approach",
# which is backwards: the review was working. The escalation belongs to a family
# that survives its own correction, never to a review that keeps finding things.
#
# Signal used: the `famille:` slug carried by a FAIL marker. An unnamed family
# counts with the previous unnamed one -- omitting it must never be the cheap way
# out of the gate.


def _fail(famille=None, tail="des defauts"):
    part = f"famille: {famille}, " if famille else ""
    return f"[REVIEW] par contexte-neuf le 2026-08-30 — verdict: FAIL, {part}{tail}"


def test_should_count_one_when_two_failures_name_different_families():
    """Two new defects found is the review doing its job, not persistence."""
    texts = [_fail("bouton decoratif"), _fail("chemin d-appel redouble")]
    assert gate.count_failures(texts) == 1


def test_should_count_two_when_the_same_family_fails_twice():
    texts = [_fail("analyse du shell a la main"), _fail("analyse du shell a la main")]
    assert gate.count_failures(texts) == 2


def test_should_count_three_when_the_same_family_survives_twice():
    same = _fail("analyse du shell a la main")
    assert gate.count_failures([same, same, same]) == 3


def test_should_match_a_family_regardless_of_case_and_spacing():
    """The slug is written by hand every time; casing must not split a family."""
    texts = [_fail("Analyse Du Shell"), _fail("analyse du shell")]
    assert gate.count_failures(texts) == 2


def test_should_stop_counting_at_a_passing_verdict():
    same = _fail("analyse du shell a la main")
    passed = "[REVIEW] par x le 2026-08-30 — verdict: PASS, rien"
    assert gate.count_failures([same, passed, same]) == 1


def test_should_treat_consecutive_unnamed_families_as_the_same_one():
    """Leaving the family out must not be the cheap way past the escalation."""
    texts = [_fail(None), _fail(None)]
    assert gate.count_failures(texts) == 2


def test_should_reset_when_a_named_family_follows_an_unnamed_one():
    texts = [_fail("bouton decoratif"), _fail(None)]
    assert gate.count_failures(texts) == 1


def test_should_return_zero_without_any_verdict():
    assert gate.count_failures(["rien a signaler", "autre texte"]) == 0


def test_should_ignore_a_verdict_written_inside_a_code_block():
    """A marker shown as an example is not a marker that happened."""
    quoted = "voici le gabarit : `" + _fail("exemple") + "`"
    assert gate.count_failures([quoted]) == 0


def test_should_not_escalate_after_two_failures_on_different_families():
    """End to end: the commit only owes the [CAUSE] block, never the approach."""
    texts = [_fail("bouton decoratif"), _fail("chemin redouble")]
    message = f"fix(ui): le bouton appelle le vrai module\n\n{FULL_CAUSE}"
    assert gate.verdict(message, texts, gate.count_failures(texts)) is None


def test_should_escalate_after_two_failures_on_the_same_family():
    texts = [_fail("analyse du shell"), _fail("analyse du shell")]
    message = f"fix(hooks): encore une rustine\n\n{FULL_CAUSE}"
    blocked = gate.verdict(message, texts, gate.count_failures(texts))
    assert blocked is not None
    assert "approche" in blocked.lower()


def test_should_tell_the_reader_how_to_declare_a_new_family():
    """A block that does not say how to prove progress traps the reader."""
    texts = [_fail(None), _fail(None)]
    message = f"fix: rustine\n\n{FULL_CAUSE}"
    blocked = gate.verdict(message, texts, gate.count_failures(texts))
    assert blocked is not None
    assert "famille:" in blocked


# --- the family belongs to the marker, not to the prose around it -------------
#
# Independent review 2026-08-30, family: a regex reading the whole text instead
# of the span it belongs to. `_family_of` searched the entire message, so a
# sentence mentioning "famille:" BEFORE the real marker hijacked the capture --
# two FAILs on the same family then counted as one, and the escalation this hook
# was rewritten to fix never fired.

_PROSE = "je l'avais note comme famille: shell-parsing-old dans le rapport precedent. "


def test_should_read_the_family_from_the_marker_not_from_the_prose_before_it():
    a = _PROSE + _fail("shell-parsing-bypass", "nouveau bypass")
    b = _fail("shell-parsing-bypass", "meme bypass")
    assert gate.count_failures([a, b]) == 2


def test_should_not_invent_a_family_from_prose_when_the_marker_has_none():
    """Prose before an unnamed FAIL must not become that FAIL's family."""
    a = _PROSE + _fail(None)
    b = _fail(None)
    assert gate.count_failures([a, b]) == 2


def test_should_ignore_prose_written_after_the_marker():
    a = _fail("bouton-decoratif") + " ensuite j'ai relu la famille: autre-chose"
    b = _fail("bouton-decoratif")
    assert gate.count_failures([a, b]) == 2


# --- what the review agents are told to emit must be readable here too ---------

_AGENTS = (
    Path(__file__).resolve().parents[2] / "agents" / "code-review-master.md",
    Path(__file__).resolve().parents[2] / "agents" / "cross-model-reviewer-master.md",
)


def _prescribed(agent_file):
    text = agent_file.read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("[REVIEW]")]


def test_should_read_the_family_out_of_the_marker_the_agents_prescribe():
    """Closes the drift for good: the template lives on disk, the test reads it."""
    for agent in _AGENTS:
        for line in _prescribed(agent):
            if "FAIL" not in line:
                continue
            concrete = (
                line.replace("<relecteur>", "cross-model-sonnet")
                .replace("<YYYY-MM-DD>", "2026-08-30")
                .replace("<slug>", "bouton-decoratif")
                .replace("<ce qui en est sorti>", "1 defaut reel")
            )
            assert gate.count_failures([concrete]) == 1, f"{agent.name}: {line}"
            assert gate.count_failures([concrete, concrete]) == 2, f"{agent.name}: {line}"
