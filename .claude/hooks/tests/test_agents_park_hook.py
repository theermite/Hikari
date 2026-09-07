"""Le parc d'experts se verifie AVANT le commit, pas apres la derive.

Ne 2026-09-06. `scripts/check-agents-park.py` existait, rendait vert, et n'etait
branche sur AUCUN evenement — comme le sommaire de memoire, comme le controle du
conseil. Un point du plan declare « livre » avec un controle que rien n'execute
n'est pas ferme : il est ferme jusqu'a la premiere modification.

Meme partage que le controle des faits : ce qu'on met en commit REFUSE, une
derive ailleurs AVERTIT. Bloquer sur une derive lointaine ferait echouer des
commits sans rapport, et le garde-fou finirait debranche.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
HOOK = RACINE / ".claude/hooks/quality/agents-park-check.py"
_spec = importlib.util.spec_from_file_location("agents_park_check", HOOK)
hook = importlib.util.module_from_spec(_spec)
sys.modules["agents_park_check"] = hook
_spec.loader.exec_module(hook)


# --- ce qui declenche ------------------------------------------------------

def test_a_git_commit_triggers_the_check():
    assert hook.is_git_commit('git commit -m "feat: x"')


def test_reading_git_history_triggers_nothing():
    assert not hook.is_git_commit("git log --oneline")


# --- ce qui est concerne ---------------------------------------------------

def test_an_expert_file_is_concerned():
    assert hook.experts_en_commit([".claude/agents/mobile-master.md"])


def test_an_archived_expert_is_concerned_too():
    # Ils sont destines a etre reveilles : leur derive compte des maintenant.
    assert hook.experts_en_commit([".claude/agents-archive/seo-master.md"])


def test_a_commit_without_any_expert_is_not_concerned():
    assert hook.experts_en_commit(["scripts/un-outil.py", "docs/note.md"]) == []


def test_the_windows_separator_does_not_hide_an_expert():
    assert hook.experts_en_commit([".claude\\agents\\mobile-master.md"])


# --- le message ------------------------------------------------------------

def test_the_message_names_each_problem_and_how_to_see_them():
    message = hook.message(["mobile-master.md : aucun appelant declare"])
    assert "mobile-master.md" in message
    assert "check-agents-park" in message


# --- le cablage ------------------------------------------------------------

def test_the_hook_is_wired_to_an_event():
    import json
    reglages = json.loads((RACINE / ".claude/settings.json").read_text(encoding="utf-8"))
    commandes = [
        h.get("command", "")
        for evenement in reglages["hooks"].values()
        for entree in evenement
        for h in entree.get("hooks", [])
    ]
    assert any("agents-park-check" in c for c in commandes)


# --- la verite du jour -----------------------------------------------------

# Ce test lit le parc REEL du depot ou il tourne. Il n'a de sens que dans Kata,
# domicile du parc : chez un receveur il decrit un monde qui n'existe pas et
# rougit sans rien apprendre — ce qui bloque toute la propagation, puisque la
# suite du receveur doit etre verte avant tout commit (mesure du 2026-09-07,
# 30 depots arretes). Kata se reconnait au script qui propage, lui ne voyage pas.
DANS_KATA = (RACINE / "scripts" / "propagate-methodology.py").is_file()


@pytest.mark.skipif(not DANS_KATA, reason="le parc reel ne vit que dans Kata")
def test_the_real_park_is_conform_today():
    """Si ce test rougit, le parc a derive — c'est le but."""
    assert hook.problemes_du_parc(RACINE) == []


# --- defaut trouve par la relecture independante du 2026-09-06 --------------
# Mon propre commentaire promettait « un probleme ailleurs AVERTIT ». Le code
# bloquait sur tout le parc. Un commit qui ajoute un expert parfaitement
# conforme etait refuse a cause d'un fichier qu'il ne touche pas.
#
# C'est exactement la famille fermee toute la soiree : un texte qui decrit un
# comportement que le code contredit.

def test_a_problem_on_a_staged_expert_refuses():
    refuses, avertis = hook.partager(["neuf : aucun appelant declare"],
                                     [".claude/agents/neuf.md"])
    assert refuses == ["neuf : aucun appelant declare"]
    assert avertis == []


def test_a_problem_on_an_untouched_expert_only_warns():
    refuses, avertis = hook.partager(["vieux : aucun appelant declare"],
                                     [".claude/agents/neuf.md"])
    assert refuses == []
    assert len(avertis) == 1


def test_a_commit_touching_a_clean_expert_is_not_refused_by_a_distant_drift():
    refuses, _ = hook.partager(
        ["vieux : aucun appelant declare", "autre : en-tete illisible"],
        [".claude/agents/neuf.md"])
    assert refuses == []


def test_a_problem_whose_expert_cannot_be_identified_only_warns():
    # Prudence dans le bon sens : on n'accuse pas un commit sur un doute.
    refuses, avertis = hook.partager(["message sans nom devant"],
                                     [".claude/agents/neuf.md"])
    assert refuses == []
    assert len(avertis) == 1
