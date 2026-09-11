"""quality/post-review-cause-check.py -- the family-matching half: how many
consecutive FAILs on the SAME family (count_failures, _same_family).

Split from test_post_review_cause_check.py on 2026-09-11 (500-line limit) --
one concept per file: the marker/[CAUSE] fields live there, the family
comparison lives here.

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
    "- veille: shlex, doc officielle consultee le 2026-09-07\n"
    "- appelants reels: oui -- grep sur 3 callsites, tous exerces\n"
    "- garde a l'envers: oui -- le test rougit si je retire la verification\n"
)


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


# --- the family survives being reworded (2026-09-10 measure) ------------------
#
# Shinkofa-Backend, service de paiement, 2026-09-08/09 : la meme famille a ete
# ecrite 3 fois differemment d'un tour a l'autre -- "solde-disponible-vs-solde-
# brut", puis "solde-brut-au-lieu-de-disponible", puis "brut-vs-disponible". La
# comparaison exacte de texte ne voyait jamais 2 echecs consecutifs IDENTIQUES,
# donc l'escalade au 2e echec (Autonomous-Session.md) ne s'est jamais declenchee
# -- 17 tours avant un arret reel. Les mots distinctifs comptent, pas la phrase.


def test_should_count_two_when_the_same_family_is_reworded():
    texts = [
        _fail("solde-disponible-vs-solde-brut"),
        _fail("solde-brut-au-lieu-de-disponible"),
    ]
    assert gate.count_failures(texts) == 2


def test_should_survive_three_rewordings_of_the_same_family():
    texts = [
        _fail("brut-vs-disponible"),
        _fail("solde-brut-au-lieu-de-disponible"),
        _fail("solde-disponible-vs-solde-brut"),
    ]
    assert gate.count_failures(texts) == 3


def test_a_shared_word_alone_must_not_merge_two_real_families():
    """Un mot de contexte commun (le module, le service) ne suffit pas -- il
    faut que la MAJORITE des mots distinctifs se retrouvent des deux cotes."""
    texts = [_fail("paiement-montant-arrondi"), _fail("paiement-webhook-signature")]
    assert gate.count_failures(texts) == 1


# --- the denominator must be the UNION, never the smaller side (2026-09-11) --
#
# Relecture independante : le denominateur min(len(a), len(b)) fait qu'un slug
# d'UN SEUL mot (ex. "hook") fusionne avec N'IMPORTE QUEL slug qui le contient
# ("verdict-marker-format-mismatch"), et que deux mots de contexte partages sur
# trois suffisent a fusionner deux VRAIS defauts differents. Le Jaccard (sur
# l'union) corrige les deux sans perdre le cas mesure qui a motive la fonction.


def test_a_single_word_slug_must_not_swallow_everything_containing_it():
    texts = [_fail("marker"), _fail("verdict-marker-format-mismatch")]
    assert gate.count_failures(texts) == 1


def test_two_shared_context_words_on_three_must_not_merge_distinct_bugs():
    """Relecture : 'hook-bloquant-manquant' et 'hook-bloquant-faux' sont 2
    defauts reels differents (garde absente vs garde fausse), pas 1 reformule."""
    texts = [_fail("hook-bloquant-manquant"), _fail("hook-bloquant-faux")]
    assert gate.count_failures(texts) == 1


def test_the_original_reworded_family_still_survives_jaccard():
    """Non-regression : le cas qui a motive toute la fonction doit encore
    fusionner avec un denominateur Jaccard."""
    texts = [
        _fail("brut-vs-disponible"),
        _fail("solde-brut-au-lieu-de-disponible"),
        _fail("solde-disponible-vs-solde-brut"),
    ]
    assert gate.count_failures(texts) == 3


# --- stopwords must cover English too, without erasing negation (2026-09-11) -
#
# Relecture : les slugs ecrits en anglais (gabarit [REVIEW] en anglais) n'avaient
# aucun mot vide filtre, donc "the", "is", "on" comptaient comme mots distinctifs
# et gonflaient artificiellement le score. Mais "not" / "no" / "never" ne sont PAS
# des mots vides : ils inversent le sens, et les retirer fusionnerait une garde
# absente avec une garde presente-mais-fausse.


def test_english_filler_words_do_not_inflate_the_score():
    texts = [_fail("the-guard-is-not-wired"), _fail("the-guard-is-wired-wrong")]
    assert gate.count_failures(texts) == 1, "garde absente et garde mal cablee sont 2 defauts"


def test_negation_words_are_kept_as_distinctive():
    texts = [_fail("guard-not-wired"), _fail("guard-wired-wrong")]
    assert gate.count_failures(texts) == 1, "'not' change le sens, ce n'est pas un mot vide"


# --- 2e relecture 2026-09-11 : l'invariant ne survit pas a un mot de contexte
# de plus, et "sans"/"avec" (negation francaise) restaient des mots vides -----
#
# Mesure : deux slugs qui ne different que par UN mot fusionnent des qu'ils
# portent 4 mots distinctifs (3/5 = 0,600 >= le plancher). Un mot de polarite
# (non/pas/sans/faux/absent/manquant/jamais, et leurs equivalents anglais) qui
# n'apparait que d'un cote doit disqualifier la fusion, quel que soit le score.


def test_negation_disqualifies_even_with_one_more_context_word():
    texts = [_fail("the-guard-is-not-wired-on-write"), _fail("the-guard-is-wired-wrong-on-write")]
    assert gate.count_failures(texts) == 1


def test_french_negation_disqualifies_the_merge():
    texts = [_fail("marqueur-non-emis-dans-le-rapport"), _fail("marqueur-emis-faux-dans-le-rapport")]
    assert gate.count_failures(texts) == 1


def test_sans_avec_are_no_longer_filler_words():
    texts = [_fail("garde-sans-test"), _fail("garde-avec-test")]
    assert gate.count_failures(texts) == 1


def test_marqueur_sans_date_is_distinct_from_marqueur_avec_fausse_date():
    texts = [_fail("marqueur-sans-date"), _fail("marqueur-avec-date-fausse")]
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

# Meme correction que dans `test_pre_deploy_review_check.py` : la liste se LIT
# dans le parc actif. Une liste figee a casse ce test le 2026-09-05 quand un
# expert de relecture est parti en sommeil.
_PARC = Path(__file__).resolve().parents[2] / "agents"
_AGENTS = tuple(
    chemin for chemin in sorted(_PARC.glob("*.md"))
    if "review" in chemin.stem or "reviewer" in chemin.stem
)


def test_the_park_still_holds_at_least_one_review_agent():
    assert _AGENTS, "aucun expert de relecture dans le parc actif"


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
