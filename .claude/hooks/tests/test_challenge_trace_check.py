"""Tests for quality/challenge-trace-check.py — le conseil arrive avant l'ecriture.

Point 5 du plan d'action, decide par Jay le 2026-09-06.

Mesure qui l'impose, prise le meme jour sur tout l'atelier : le gabarit
`TECHNICAL CHALLENGE` a ete emis pour de vrai **1 fois sur 1269 rapports de
session**. Sur les 20 dernieres sessions : 43 decisions structurantes, 3
contradictions emises — dont une fausse, fondee sur un chiffre jamais calcule —
et ~43 defauts rattrapes APRES ecriture. Le filet aval fonctionne ; la porte
amont est ouverte.

La regle existait depuis des mois et n'a jamais mordu. La lecon du jour
s'applique a elle-meme : ce qui est tenu par du texte ne tient pas. D'ou une
trace exigee dans l'artefact, avec une raison ecrite quand il n'y a pas eu de
contradiction — la raison etant elle-meme un signal a compter, pas une sortie
de secours.

Le hook est charge par chemin (le tiret dans le nom empeche l'import direct).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "challenge-trace-check.py"
_spec = importlib.util.spec_from_file_location("challenge_trace_check", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# --- ou la porte s'applique --------------------------------------------------


def test_a_session_report_is_gated():
    assert gate.is_session_report("docs/Sessions/Session-2026-09-06-001.md")
    assert gate.is_session_report(r"D:\x\docs\Sessions\Session-2026-09-06-001.md")


def test_anything_else_is_not_gated():
    # La porte vise le rapport de session, pas tout le depot.
    assert not gate.is_session_report("docs/Briefs/Un-Brief.md")
    assert not gate.is_session_report("scripts/propagate_lib/cli.py")
    assert not gate.is_session_report("docs/Sessions/README.md")


# --- ce qui compte comme une trace ------------------------------------------


def test_an_emitted_challenge_passes():
    assert gate.trace("Bilan.\n\n[CHALLENGE] la copie additive n'efface rien\n") is not None


def test_a_written_reason_passes():
    texte = "[NO-CHALLENGE] motif: contradiction-portee-par-jay"
    assert gate.trace(texte) is not None


def test_nothing_at_all_fails():
    assert gate.trace("Rapport de session sans rien.\n") is None


def test_a_reason_outside_the_closed_list_fails():
    # Sinon la raison devient une sortie de secours a rallonge.
    assert gate.trace("[NO-CHALLENGE] motif: pas-le-temps") is None


def test_a_reason_with_no_motif_fails():
    assert gate.trace("[NO-CHALLENGE]") is None


# --- le marqueur survit a la mise en forme ----------------------------------
#
# Un marqueur en gras a deja bloque silencieusement toute une serie de tentatives
# (souvenir « veille-marker-never-bold »). Le lecteur est tolerant, pour que la
# porte refuse un defaut de fond, jamais un defaut de mise en page.


def test_bold_does_not_break_the_marker():
    assert gate.trace("**[CHALLENGE]** un chemin plus simple existait") is not None


def test_backticks_do_not_break_the_marker():
    assert gate.trace("`[NO-CHALLENGE] motif: aucune-decision-structurante`") is not None


def test_a_table_cell_does_not_break_the_marker():
    assert gate.trace("| Trace | [CHALLENGE] le seuil n'etait tenu par personne |") is not None


# --- la porte elle-meme ------------------------------------------------------


def test_the_gate_blocks_a_report_without_a_trace():
    verdict = gate.verdict("docs/Sessions/Session-2026-09-06-001.md", "Bilan du jour.")
    assert verdict is not None
    assert "motif" in verdict


def test_the_gate_lets_a_traced_report_through():
    verdict = gate.verdict(
        "docs/Sessions/Session-2026-09-06-001.md",
        "Bilan.\n[NO-CHALLENGE] motif: chemin-unique-impose\n"
        "## Reproches de livraison\naucun\n",
    )
    assert verdict is None


def test_the_gate_ignores_a_file_it_does_not_own():
    assert gate.verdict("scripts/cli.py", "pas un rapport") is None


def test_an_empty_write_is_not_gated():
    # Creation d'un squelette : la porte se pose au contenu, pas au geste.
    assert gate.verdict("docs/Sessions/Session-2026-09-06-001.md", "") is None


# --- l'enumeration est fermee, et chaque motif est un signal ----------------


def test_the_closed_list_is_short_and_named():
    # Une liste longue est une liste a rallonger — donc plus une garde.
    assert len(gate.MOTIFS) <= 5
    assert "contradiction-portee-par-jay" in gate.MOTIFS


# --- le reproche de livraison a sa section, et elle dit quelque chose --------
#
# 5 reproches en 20 sessions, 3 APRES le correctif cense les fermer. Le signal
# etait documente a chaque fois et n'entrait dans aucun score — donc rien ne
# changeait. Une regle qu'aucun code ne tient ne tient pas : c'est la lecon du
# 2026-09-06, appliquee a la regle ecrite le meme jour.


def test_a_report_without_the_complaints_section_fails():
    texte = "[NO-CHALLENGE] motif: chemin-unique-impose\n\nBilan du jour."
    assert gate.complaints_section(texte) is False


def test_the_section_alone_is_not_enough():
    # Un titre vide est une case a cocher, pas une reponse.
    texte = "## Reproches de livraison\n\n## Suite\n"
    assert gate.complaints_section(texte) is False


def test_declaring_none_is_a_valid_answer():
    texte = "## Reproches de livraison\n\naucun\n"
    assert gate.complaints_section(texte) is True


def test_a_quoted_complaint_is_a_valid_answer():
    texte = '## Reproches de livraison\n\n« c\'est illisible » — cause: jargon\n'
    assert gate.complaints_section(texte) is True


def test_the_section_survives_formatting():
    texte = "**Reproches de livraison** : aucun\n"
    assert gate.complaints_section(texte) is True


def test_the_gate_blocks_a_traced_report_without_the_section():
    verdict = gate.verdict(
        "docs/Sessions/Session-2026-09-06-001.md",
        "[NO-CHALLENGE] motif: chemin-unique-impose\n\nBilan.",
    )
    assert verdict is not None
    assert "livraison" in verdict.lower()


def test_the_gate_lets_a_complete_report_through():
    verdict = gate.verdict(
        "docs/Sessions/Session-2026-09-06-001.md",
        "[NO-CHALLENGE] motif: chemin-unique-impose\n\n"
        "## Reproches de livraison\n\naucun\n",
    )
    assert verdict is None
