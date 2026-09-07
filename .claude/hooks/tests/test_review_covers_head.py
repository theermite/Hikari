"""Un feu vert de relecture ne survit pas au code qu'il a valide.

NE D'UNE QUESTION DE JAY, le 2026-09-07 : « as-tu bien verifie tout ce que tu
vas propager ? ». La reponse etait non. Sept commits etaient partis apres le
dernier feu vert — la portee des reserves, une alerte, un garde-fou neuf, trois
corrections d'un compteur — et LE GARDE-FOU LES AURAIT LAISSES PASSER.

CE QU'IL FAISAIT. Il cherchait le dernier verdict de la conversation et lisait
son mot : PASS ou FAIL. Il ne demandait jamais sur QUOI ce verdict portait. Un
feu vert donne a 10 h couvrait donc encore, a 13 h, un code entierement
different.

MEME FAMILLE QUE LA JOURNEE ENTIERE : un controle qui mesure la mauvaise chose
rassure exactement comme un controle qui fonctionne. Ici il verifiait qu'une
phrase existe, jamais qu'elle correspond au code qui part.

CE QUI LE FERME. Le feu vert nomme l'empreinte du commit relu ; le garde-fou la
confronte a l'etat actuel du depot. Une phrase ne peut pas prouver ce qu'elle a
couvert ; une empreinte, si — c'est la regle « un artefact, jamais une
formulation », deja ecrite dans notre protocole de relais.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
GARDE = RACINE / ".claude/hooks/guards/pre-deploy-review-check.py"
_spec = importlib.util.spec_from_file_location("pre_deploy_review_check", GARDE)
gate = importlib.util.module_from_spec(_spec)
sys.modules["pre_deploy_review_check"] = gate
_spec.loader.exec_module(gate)

DEPLOY = "python scripts/propagate-methodology.py --apply --all-projects"
BRIEF = (
    "[REVIEW-BRIEF]\n"
    "- objectif: propager la methodologie\n"
    "- perimetre: le lot en cours\n"
    "- zones suspectes: la reserve, le compteur\n"
    "- consigne: refuter, jamais valider\n"
)


def _feu_vert(sur: str | None) -> str:
    empreinte = f" sur {sur}" if sur else ""
    return f"[REVIEW] par sonnet le 2026-09-07{empreinte} — verdict: PASS, rien trouve"


def test_a_pass_that_names_no_commit_is_refused():
    """Sans empreinte, le feu vert ne dit pas sur quoi il porte."""
    message = gate.verdict(DEPLOY, [_feu_vert(None), BRIEF], head="abc1234def")
    assert message is not None
    assert "empreinte" in message.lower()


def test_a_pass_on_the_current_commit_lets_it_through():
    assert gate.verdict(DEPLOY, [_feu_vert("abc1234"), BRIEF], head="abc1234def") is None


def test_a_pass_on_an_older_commit_is_refused():
    """Le cas exact du 2026-09-07 : sept commits apres le dernier feu vert."""
    message = gate.verdict(DEPLOY, [_feu_vert("19ae958"), BRIEF], head="5dfa6f1abc")
    assert message is not None
    assert "19ae958" in message and "5dfa6f1" in message


def test_the_check_stands_down_when_the_commit_is_unknown():
    """Hors depot git, le garde-fou ne se met pas a tout refuser.

    Un garde-fou qui refuse ce qu'il ne sait pas lire se fait debrancher, et
    emporte la detection reelle avec lui.
    """
    assert gate.verdict(DEPLOY, [_feu_vert("abc1234"), BRIEF], head=None) is None


def test_a_fail_still_blocks_whatever_the_commit():
    """Le verdict negatif garde la priorite — l'empreinte ne le rachete pas."""
    marque = "[REVIEW] par sonnet le 2026-09-07 sur abc1234 — verdict: FAIL, 2 defauts"
    assert gate.verdict(DEPLOY, [marque, BRIEF], head="abc1234def") is not None


def test_the_head_is_read_from_the_repository_by_default():
    """La valeur par defaut vient de git, jamais d'un appelant complaisant."""
    assert gate.head_courant() , "le garde-fou doit savoir lire l'empreinte courante"
