#!/usr/bin/env python3
"""A failed review must teach — PreToolUse Bash on `git commit`.

Why this hook exists
--------------------
On 2026-08-10, five independent reviews in a row rejected the same family of
defect. Each time the fix addressed the case that was reported, never the cause;
the family reopened one bypass later. Jay named the real failure: "le problème
n'est pas que tu aies fait une erreur, c'est que tu as persévéré dans cette
erreur. Dès que l'erreur est détectée, il faut prendre du recul pour savoir d'où
elle vient, la corriger, et mettre en place quelque chose qui fera qu'elle n'est
pas reproduite."

So a FAIL verdict is not a warning to note in passing. It opens an obligation
that the next commit has to discharge.

What is required
----------------
After a review came back FAIL, the next commit message carries:

  [CAUSE]
  - famille: <the CLASS of defect, not the single case>
  - cause: <where it comes from>
  - ce qui empeche la repetition: <test, shared component, gate — an artefact>
  - appelants reels: <oui — comment verifie (grep, callsites) | non-applicable>
  - garde a l'envers: <le test rougit-il si tu retires la garde ? oui | non-applicable>

At the SECOND consecutive FAIL ON THE SAME FAMILY, that is no longer enough:
patching the reported case is forbidden, and the message must also carry

  - approche changee: oui — <what is structurally different now>

because a family that survives one correction will survive the next one of the
same shape. Two failures say the approach is wrong, not the line.

The counter counts DEFECTS, not rounds (Jay 2026-08-30)
-------------------------------------------------------
The first version counted consecutive FAIL verdicts whatever they were about, so
two reviews finding two DIFFERENT problems escalated to "change your approach" --
backwards, since the review was doing its job. Jay: "si la relecture trouve une
nouvelle erreur ce n'est pas une deuxieme tentative [...] si tu essaies 2 ou 3
fois de corriger LA MEME erreur et n'y parviens pas, tu dois prendre du recul."

So a FAIL marker names the family it is about:

  [REVIEW] par <x> le <date> — verdict: FAIL, famille: <slug>, <ce qui en sort>

A different family resets the counter. An UNNAMED family counts with the previous
unnamed one -- omitting the slug must never be the cheap way past the gate.

Honest limits (independent review, 2026-08-10)
----------------------------------------------
- No transcript, or a verdict written inside a code block: the hook sees no FAIL
  and lets the commit through. Accepted, not hidden — the gate is an aid to
  stepping back, never a proof that stepping back happened.
- Three filled lines are not three TRUE lines: nothing checks that the family is
  named honestly. Jay stays the last verifier (Quality.md A9).
- A FAIL older than the last 40 assistant messages falls out of view.

Hook exit codes: 0 = pass · 2 = block (stderr message printed).

Source: Jay 2026-08-10. Pairs with rules/Independent-Review.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    get_command,
    pass_through,
    read_hook_input,
)
from marker_fields import field_filled, field_value  # noqa: E402
from shell_parse import simple_commands  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402

# These name a command, they never run it.
_PRINTERS = {"echo", "print", "printf"}

TRANSCRIPT_LOOKBACK = 40

# Commits worth excusing: the work has nothing to do with what the review found.
# Closed list — an open motif field becomes "pas envie" within a week.
SKIP_MOTIFS = (
    "sans-rapport",  # this commit touches another subject entirely
    "revert",  # going back to a state that was fine
    "wip-sauvegarde",  # checkpoint commit, the cause work is still in progress
)

_SKIP = re.compile(r"\[CAUSE-SKIP\][^\S\n]*motif[^\S\n]*:[^\S\n]*([a-z0-9-]+)", re.IGNORECASE)
_VERDICT = re.compile(r"\[REVIEW\][^\n]*?verdict\s*:\s*(PASS|FAIL)", re.IGNORECASE)
_CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)

# The family a FAIL is about, read from the marker itself:
#   [REVIEW] par <x> le <date> - verdict: FAIL, famille: <slug>, <ce qui en sort>
# It ends at a comma or a line break, so the free-text tail stays free.
_FAMILY = re.compile(r"famille[^\S\n]*:[^\S\n]*([^,\n]+)", re.IGNORECASE)
_UNNAMED = "<sans famille nommee>"

# A family gets reworded round to round (measured 2026-09-10, Shinkofa-Backend,
# service de paiement: "solde-disponible-vs-solde-brut" -> "solde-brut-au-lieu-
# de-disponible" -> "brut-vs-disponible", 3 textes pour 1 seul defaut). Exact-text
# comparison never saw 2 consecutive identical FAILs, so the 2nd-failure escalation
# (Autonomous-Session.md) never fired -- 17 rounds before a real stop. Compare the
# WORDS that make the slug distinctive, not the sentence.
#
# "sans" / "avec" removed 2026-09-11 (2e relecture) : ils portaient la negation
# francaise ("garde-sans-test" vs "garde-avec-test") et etaient pourtant traites
# comme du bruit -- meme defaut que "not" en anglais, jamais corrige cote FR.
_SLUG_STOPWORDS = frozenset({
    "vs", "au", "de", "du", "la", "le", "un", "une", "et", "ou", "sur", "dans",
    "pour", "par", "lieu", "meme", "en", "a",
    "the", "is", "on", "of", "to", "and", "or", "for", "with", "by", "in", "when",
})
# Un mot de polarite qui n'apparait que d'un cote disqualifie la fusion, quel
# que soit le score (2e relecture 2026-09-11) : au-dela de 3 mots distinctifs,
# un seul mot de difference peut deja franchir le plancher de similarite
# (ex. 3/5 = 0,6) -- garder "not"/"sans" hors des mots vides ne suffit plus
# a lui seul si les slugs s'allongent. Liste fermee, honnetement incomplete :
# une paraphrase sans aucun de ces mots reste hors de portee (embeddings
# differes, deja documente dans le commit qui a introduit Jaccard).
#
# LIMITE HONNETE (3e relecture independante, meme jour) : cette regle ferme
# la fusion abusive mais ouvre la SCISSION abusive dans l'autre sens -- une
# vraie reformulation qui laisse tomber un mot de polarite ("garde-non-cable"
# -> "garde-cable-a-moitie") reset desormais le compteur a 1 et desactive
# l'escalade au 2e echec. Le cas mesure qui a motive toute la fonction (le
# drift SANS negation) passe toujours ; seul le drift AVEC negation regresse.
# Non corrige : trancher entre les deux directions demande une comprehension
# semantique hors de portee d'une comparaison de mots (Jay stays the last
# verifier, Quality.md A9).
_POLARITY_WORDS = frozenset({
    "non", "pas", "sans", "faux", "fausse", "faussement", "absent", "absente",
    "manquant", "manquante", "jamais", "incorrect", "incorrecte", "errone",
    "erronee", "not", "no", "never", "wrong", "missing", "false", "without",
    "incorrectly",
})
# Le plancher reste sur l'union (Jaccard, pas le plus petit cote) -- un slug
# d'un seul mot ne doit jamais avaler tout slug qui le contient, et 2 mots de
# contexte partages sur 3 ne doivent jamais suffire a fusionner 2 vrais
# defauts (mesure 2e relecture 2026-09-11 : min() faisait les deux).
_SLUG_SIMILARITY_FLOOR = 0.6


def _slug_tokens(slug):
    words = re.split(r"[^a-z0-9]+", slug.casefold())
    return {w for w in words if len(w) > 1 and w not in _SLUG_STOPWORDS}


def _same_family(current, previous):
    """Same family if either text matches exactly, or their distinctive words
    overlap past the floor AND no polarity word appears on only one side.
    Never applies to the unnamed sentinel on one side only -- an unnamed FAIL
    must never inherit a named one's family for free."""
    if current == previous:
        return True
    if current == _UNNAMED or previous == _UNNAMED:
        return False
    a, b = _slug_tokens(current), _slug_tokens(previous)
    if not a or not b:
        return False
    if (a ^ b) & _POLARITY_WORDS:
        return False
    overlap = len(a & b) / len(a | b)
    return overlap >= _SLUG_SIMILARITY_FLOOR

# Last 2 added 2026-09-11: measured across 3 repos, 21 days, the defects a
# review kept finding were almost all detectable before writing -- "le
# correctif n'avait aucun appelant reel" (Shinkofa-Backend 09-09), "si je
# retire la garde, le test rougit-il ?" jamais pose (Shinkofa-Backend 09-08).
_FIELDS = (
    "famille", "cause", "ce qui empeche la repetition", "veille",
    "appelants reels", "garde a l'envers",
)

# La veille doit porter une DATE : « j'ai regardé » n'est pas une source, et un
# modele produit cette phrase aussi facilement que la verite (`Rule-Format.md`).
_DATE_OU_LIEN = re.compile(r"\d{4}-\d{2}-\d{2}|https?://")
# Validates the VALUE only (field_value() reads the line -- see _approche_changee).
_APPROACH_VALIDE = re.compile(r"^oui\s*[—-]\s*\S+", re.IGNORECASE)


def is_commit(command):
    """True when a real `git commit` runs — not a sentence naming one.

    Reads shell tokens (lib/shell_parse.py). Writing this detection by hand is
    the family of defect that cost five review rounds on 2026-08-10; the shared
    parser exists precisely so it is never written by hand again.
    """
    try:
        segments = simple_commands(command)
    except ValueError:
        segments = [[command or ""]]  # fail closed
    for segment in segments:
        if segment[0] in _PRINTERS:
            continue
        if "git" in _program_names(segment) and "commit" in segment:
            return True
    return False


def _program_names(segment):
    return {token.replace("\\", "/").rsplit("/", 1)[-1].lower() for token in segment}


def find_skip(message):
    """Return the skip match only when its motif is in the closed list."""
    match = _SKIP.search(message or "")
    if match and match.group(1).lower() in SKIP_MOTIFS:
        return match
    return None


def _spoken(text):
    return _CODE.sub(" ", text or "")


def last_verdict(recent_texts):
    """PASS, FAIL, or None — the most recent review verdict spoken in chat."""
    for text in recent_texts:
        match = _VERDICT.search(_spoken(text))
        if match:
            return match.group(1).upper()
    return None


def find_cause(message):
    """Return the message when it carries a complete [CAUSE] block, else None.

    Field reading via lib/marker_fields.py (2e relecture independante,
    2026-09-11) : le 1er correctif n'avait cable le lecteur partage QUE dans
    anti-quick-fix.py -- ce hook gardait sa propre regex exacte, refusant
    encore l'accent francais correct et l'apostrophe typographique sur son
    PROPRE champ. Meme famille reouverte, fermee pour de vrai cette fois.
    """
    if "[CAUSE]" not in (message or ""):
        return None
    if not all(field_filled(message, field) for field in _FIELDS):
        return None
    if not _veille_datee(message):
        return None
    return message


def _veille_datee(message):
    """La ligne de veille porte-t-elle une date ou un lien ?

    DEMANDE DE JAY, 2026-09-07 : « lorsqu'il y a des relectures qui sont faites
    et que les corrections sont tentees, il faut absolument faire des recherches
    Web pour s'assurer d'avoir les informations a jour, afin de corriger
    correctement les erreurs. »

    Mesure du jour qui lui donne raison : une journee entiere de correctifs
    ecrits depuis zero, sans une seule recherche. La premiere veille lancee a
    trouve que l'outil de reference REFUSE de demarrer sur un depot sale — la
    regle meme dont l'absence a coute toute la matinee. Corriger avec un jeu de
    connaissances perime, c'est corriger de travers, avec application.

    Une date ou un lien, jamais « j'ai regarde » : une phrase de verification
    n'est pas une verification.

    Valeur lue via field_value() (3e relecture independante 2026-09-11) : un
    2e lecteur a la main pour le meme champ 'veille' que field_filled() lisait
    deja -- exactement la famille que ce module a ete cree pour fermer.
    """
    valeur = field_value(message, "veille")
    return bool(valeur and _DATE_OU_LIEN.search(valeur))


def _missing_cause_message():
    return (
        "BLOCKED: the last independent review came back FAIL, and this commit does "
        "not say what it taught. "
        "RECOVERY: add to the commit message: '[CAUSE]' then SIX lines — "
        "'- famille: <la CLASSE du defaut, pas le cas signale>', "
        "'- cause: <d'ou il vient>', "
        "'- ce qui empeche la repetition: <test, composant partage, garde-fou>', "
        "'- veille: <source datee ou lien consulte AVANT de corriger>', "
        "'- appelants reels: <oui -- comment verifie | non-applicable -- pourquoi>', "
        "'- garde a l'envers: <le test rougit-il si tu retires la garde ? oui | non-applicable>'. "
        "Why: on 2026-08-10, five reviews in a row rejected the same family, "
        "because each fix addressed the reported case and never the cause. "
        "And on 2026-09-07, a full day of fixes was written from scratch with "
        "zero research: the first search found that the reference tool REFUSES "
        "to run on a dirty repo — the very rule whose absence cost the morning. "
        "Correcting from a stale dataset is correcting wrong, thoroughly."
    )


def _second_failure_message():
    return (
        "BLOCKED: second review failure in a row — patching the reported case is no "
        "longer the answer. "
        "RECOVERY: step back and change the APPROACH, then write the [CAUSE] block "
        "('- famille:', '- cause:', '- ce qui empeche la repetition:') plus "
        "'- approche changee: oui — <ce qui est structurellement different>'. "
        "Why: a famille that survived one correction survives the next one of the "
        "same shape (Jay 2026-08-10). Two failures say the design is wrong, not the "
        "line. If you believe the approach is right, say so to Jay and let him "
        "decide — do not spend a third round. "
        "If this review actually found a DIFFERENT problem, that is progress, not "
        "persistence — name it in the marker as "
        "'verdict: FAIL, famille: <slug>, ...' and the counter starts over "
        "(Jay 2026-08-30: a new defect found is not a second attempt)."
    )


def _approche_changee(message):
    """The 'approche changee' field, read via field_value() (3e relecture
    independante 2026-09-11) -- the hand-rolled regex it replaces matched on
    plain `\\s`, which crosses line breaks: an EMPTY field borrowed the next
    line's text as its own value, on the escalation gate itself."""
    valeur = field_value(message, "approche changee")
    return bool(valeur and _APPROACH_VALIDE.match(valeur))


def verdict(commit_message, recent_texts, failures):
    """Return a block message, or None when the commit may proceed."""
    if last_verdict(recent_texts) != "FAIL":
        return None
    # Twice in a row, the demand is higher: the approach has to move, not the line.
    # No excuse holds here — a second failure is about the design, not this commit.
    if failures >= 2:
        return None if _approche_changee(commit_message or "") else _second_failure_message()
    if find_skip(commit_message):
        return None
    if not find_cause(commit_message):
        return _missing_cause_message()
    return None


def _family_of(spoken_text, verdict_match):
    """The family slug a verdict is about, folded for comparison.

    Anchored on the marker, never on the whole message (independent review
    2026-08-30). Searching the full text let a sentence mentioning "famille:"
    BEFORE the marker hijack the capture: two FAILs on the same family then
    counted as one, and the escalation this hook exists for never fired.
    The slug lives on the marker's own line, so the search stops at its end.
    """
    line_end = spoken_text.find("\n", verdict_match.end())
    tail = spoken_text[verdict_match.end() : line_end if line_end != -1 else None]
    match = _FAMILY.search(tail)
    if not match:
        return _UNNAMED
    return " ".join(match.group(1).split()).casefold()


def count_failures(recent_texts):
    """How many times the SAME family failed in a row, most recent first.

    Counting rounds instead of defects was the defect (Jay 2026-08-30): two
    reviews finding two DIFFERENT problems escalated to "change your approach",
    when in fact the review was doing its job. The escalation belongs to a family
    that survives its own correction, never to a review that keeps finding things.

    An unnamed family counts with the previous unnamed one: leaving the slug out
    must never be the cheap way past the gate.

    The comparison is against the IMMEDIATELY PRECEDING round, not the first one
    seen (2026-09-10): a family drifts in wording one round at a time, and a
    fixed anchor loses a slow drift that a chain of neighbours still catches.
    """
    failures = 0
    family = None
    for text in recent_texts:
        spoken = _spoken(text)
        match = _VERDICT.search(spoken)
        if not match:
            continue
        if match.group(1).upper() != "FAIL":
            break
        current = _family_of(spoken, match)
        if family is not None and not _same_family(current, family):
            break
        family = current
        failures += 1
    return failures


def main():
    raw, data = read_hook_input()
    command = get_command(data)
    if not is_commit(command):
        pass_through()

    transcript = data.get("transcript_path", "")
    texts = list(iter_assistant_text(transcript, limit=TRANSCRIPT_LOOKBACK)) if transcript else []
    failures = count_failures(texts)

    message = verdict(raw, texts, failures)
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    main()
