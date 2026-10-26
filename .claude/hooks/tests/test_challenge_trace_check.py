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
        "## Reproches de livraison\naucun\n## Règles posées\naucune\n")
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
        "## Reproches de livraison\n\naucun\n\n## Règles posées\n\naucune\n")
    assert verdict is None


# --- « Toute règle créée est annoncée » (Jay, 2026-10-13) ----------------------------------------
# « Ce n'est pas la première fois que tu crées des règles sans réellement me consulter, sans
# réellement me notifier. » Un souvenir existait; rien ne le tenait. Le rapport nomme maintenant
# chaque règle, annexe, garde-fou ou compétence posé dans la séance — et « aucune » est refusé quand
# le dépôt montre le contraire.

BASE = "[NO-CHALLENGE] motif: chemin-unique-impose\n\n## Reproches de livraison\n\naucun\n\n"
RAPPORT = "docs/Sessions/Session-2026-10-26-001.md"


def test_a_report_without_the_posed_rules_section_fails():
    assert gate.rules_section(BASE) is False


def test_the_title_alone_is_not_an_answer():
    assert gate.rules_section(BASE + "## Règles posées\n\n## Autre\ntexte") is False


def test_declaring_no_rule_is_a_valid_answer_when_nothing_changed():
    assert gate.verdict(RAPPORT, BASE + "## Règles posées\n\naucune\n") is None


def test_a_listed_rule_is_a_valid_answer():
    texte = BASE + "## Règles posées\n\n- annexe `Socle-Minimal` : lue avant tout cahier des charges\n"
    assert gate.verdict(RAPPORT, texte) is None


def test_saying_none_while_rules_changed_is_warned_not_refused_and_names_the_files():
    # relecture du 2026-10-26 (constat 6): `git diff` voit aussi le travail d'une AUTRE séance en parallèle;
    # le dépôt ne prouve pas que CETTE séance a posé ces règles — avertir, jamais bloquer
    texte = BASE + "## Règles posées\n\naucune\n"
    touchees = [".claude/rules/02-Parcours.md", ".claude/hooks/guards/writer-lock.py"]
    assert gate.verdict(RAPPORT, texte) is None
    avis = gate.avertissement(RAPPORT, texte, touchees=touchees)
    assert avis is not None and "02-Parcours.md" in avis and "writer-lock.py" in avis
    assert "autre séance" in avis


def test_no_warning_when_the_report_lists_its_rules_or_nothing_changed():
    liste = BASE + "## Règles posées\n\n- garde-fou `writer-lock` : un seul écrivain\n"
    assert gate.avertissement(RAPPORT, liste, touchees=[".claude/hooks/guards/writer-lock.py"]) is None
    assert gate.avertissement(RAPPORT, BASE + "## Règles posées\n\naucune\n", touchees=[]) is None


def test_the_section_survives_accents_and_formatting():
    for titre in ("## Règles posées", "## Regles posees", "### **Règles posées**", "## Règle posée"):
        assert gate.rules_section(BASE + f"{titre}\n\naucune\n") is True, titre


def test_changed_rules_are_read_from_git_since_the_last_report(tmp_path):
    import subprocess

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / ".claude/rules").mkdir(parents=True)
    (tmp_path / "docs/Sessions").mkdir(parents=True)
    (tmp_path / ".claude/rules/old.md").write_text("a")
    git("add", ".")
    git("commit", "-qm", "avant")
    (tmp_path / "docs/Sessions/Session-2026-10-25-001.md").write_text("rapport")
    git("add", ".")
    git("commit", "-qm", "rapport precedent")
    (tmp_path / ".claude/rules/new.md").write_text("b")
    (tmp_path / "src.py").write_text("ignore")
    git("add", ".")
    git("commit", "-qm", "regle posee apres le dernier rapport")
    (tmp_path / ".claude/rules/old.md").write_text("modifie, non commite")
    touchees = gate.regles_touchees(tmp_path)
    assert ".claude/rules/new.md" in touchees and ".claude/rules/old.md" in touchees
    assert "src.py" not in touchees


# --- constat 6 (2026-10-26): un Edit partiel est jugé sur le rapport COMPLET, pas sur son new_string -------

COMPLET = BASE + "## Règles posées\n\naucune\n"


def _charge(outil: str, entree: dict) -> dict:
    return {"tool_name": outil, "tool_input": entree}


def _rapport(tmp_path, texte: str):
    dossier = tmp_path / "docs" / "Sessions"
    dossier.mkdir(parents=True)
    fichier = dossier / "Session-2026-10-26-009.md"
    fichier.write_text(texte, encoding="utf-8")
    return fichier


def test_an_edit_is_judged_on_the_whole_report_after_the_edit(tmp_path):
    f = _rapport(tmp_path, COMPLET + "Une fote de frappe.\n")
    data = _charge("Edit", {"file_path": str(f), "old_string": "fote", "new_string": "faute"})
    assert "faute de frappe" in gate.contenu_complet(data)
    assert gate.verdict(str(f), gate.contenu_complet(data)) is None


def test_an_edit_that_removes_the_trace_is_still_refused(tmp_path):
    f = _rapport(tmp_path, COMPLET)
    data = _charge("Edit", {"file_path": str(f), "old_string": "[NO-CHALLENGE] motif: chemin-unique-impose",
                            "new_string": "rien"})
    assert gate.verdict(str(f), gate.contenu_complet(data)) is not None


def test_a_multiedit_is_applied_in_order(tmp_path):
    f = _rapport(tmp_path, COMPLET + "alpha\n")
    edits = [{"old_string": "alpha", "new_string": "beta"}, {"old_string": "beta", "new_string": "gamma"}]
    data = _charge("MultiEdit", {"file_path": str(f), "edits": edits})
    assert gate.contenu_complet(data).endswith("gamma\n")


def test_an_edit_that_cannot_be_applied_is_not_judged(tmp_path):
    f = _rapport(tmp_path, COMPLET)
    data = _charge("Edit", {"file_path": str(f), "old_string": "introuvable", "new_string": "x"})
    assert gate.contenu_complet(data) is None
    absent = _charge("Edit", {"file_path": str(tmp_path / "absent.md"), "old_string": "a", "new_string": "b"})
    assert gate.contenu_complet(absent) is None


def test_a_write_is_judged_on_its_content():
    assert gate.contenu_complet(_charge("Write", {"file_path": "x.md", "content": "tout"})) == "tout"
