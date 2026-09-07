"""Le controle des faits arrive AVANT le commit, pas apres la derive.

Ne 2026-09-06. Trois controles existaient deja — le parc d'experts, le sommaire
de memoire, les chiffres du conseil — et AUCUN n'etait branche sur quoi que ce
soit. C'est pour ca que le sommaire de memoire avait derive : personne ne le
relancait.

Le partage choisi ici evite le debranchement : un fait faux dans un document
qu'on met en commit REFUSE, un fait faux ailleurs AVERTIT. Sinon une derive
lointaine bloquerait un commit sans rapport, et le garde-fou finirait desactive.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
HOOK = RACINE / ".claude/hooks/quality/doc-facts-check.py"
_spec = importlib.util.spec_from_file_location("doc_facts_check", HOOK)
hook = importlib.util.module_from_spec(_spec)
sys.modules["doc_facts_check"] = hook
_spec.loader.exec_module(hook)


class _Ecart:
    def __init__(self, fichier, ligne=1, fait="regles-auto", ecrit=1, reel=2):
        self.fichier = Path(fichier)
        self.ligne = ligne
        self.fait = fait
        self.ecrit = ecrit
        self.reel = reel
        self.texte = "extrait"


# --- ce qui declenche ------------------------------------------------------

def test_a_git_commit_triggers_the_check():
    assert hook.is_git_commit('git commit -m "feat: x"')


def test_reading_git_history_triggers_nothing():
    assert not hook.is_git_commit("git log --oneline -5")
    assert not hook.is_git_commit("git status")


def test_an_unrelated_command_triggers_nothing():
    assert not hook.is_git_commit("python -m pytest")


# --- le partage refuser / avertir ------------------------------------------

def test_a_false_fact_in_a_staged_document_is_refused():
    ecarts = [_Ecart(RACINE / ".claude/rules/Quality.md")]
    refuses, avertis = hook.partager(ecarts, [".claude/rules/Quality.md"], RACINE)
    assert len(refuses) == 1
    assert avertis == []


def test_a_false_fact_elsewhere_only_warns():
    # Sinon une derive lointaine bloque un commit sans rapport, et le
    # garde-fou finit debranche — il emporterait la vraie detection avec lui.
    ecarts = [_Ecart(RACINE / "docs/Migration-Brief-v6.md")]
    refuses, avertis = hook.partager(ecarts, [".claude/rules/Quality.md"], RACINE)
    assert refuses == []
    assert len(avertis) == 1


def test_no_drift_leaves_both_lists_empty():
    refuses, avertis = hook.partager([], [".claude/rules/Quality.md"], RACINE)
    assert (refuses, avertis) == ([], [])


def test_the_windows_separator_does_not_hide_a_staged_file():
    # git rend des chemins en barre oblique ; le disque Windows en rend d'autres.
    ecarts = [_Ecart(RACINE / "docs" / "Migration-Brief-v6.md")]
    refuses, _ = hook.partager(ecarts, ["docs/Migration-Brief-v6.md"], RACINE)
    assert len(refuses) == 1


# --- le message ------------------------------------------------------------

def test_the_message_names_the_file_the_line_and_both_numbers():
    message = hook.message([_Ecart(RACINE / "docs/x.md", ligne=42, ecrit=16, reel=17)], [])
    assert "docs/x.md" in message
    assert "42" in message
    assert "16" in message
    assert "17" in message
