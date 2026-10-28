"""Deux travers du journal qui faisaient refuser une revue en règle (séance 2026-10-26/27).

1. Le journal contient, après chaque appel d'outil, une entrée `api-request-blob` qui RECOPIE le
   message précédent (thinking, text, tool_use). Mesuré le 2026-10-27 sur le journal de la séance :
   160 copies, 63 textes dedans, 0 absent des entrées `assistant`. La garde entendait donc chaque
   texte deux fois : un verdict de Takumi passait pour « un PASS plus ancien », la marche arrière
   s'arrêtait avant le brief, et la garde refusait « rien ne dit ce que le relecteur a reçu ».
   Un message qui porte aussi une écriture dans un fichier de parole donne T, S, T, S : une fusion
   des voisins identiques ne l'attrape pas (relecture du 2026-10-27) ; la copie doit être ignorée.
2. Le crochet lit le journal AVANT que le message qui porte la commande soit écrit : un marqueur
   placé dans ce même message n'est jamais vu. Le message de refus doit le dire, sinon la reprise
   conseillée (« émets le marqueur puis relance ») échoue de la même façon.
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


def _message(*blocks, kind="assistant") -> dict:
    return {"type": kind, "message": {"role": "assistant", "content": list(blocks)}}


def _text(t: str) -> dict:
    return {"type": "text", "text": t}


def _said_write(body: str, tool_id: str = "t1") -> dict:
    return {"type": "tool_use", "id": tool_id, "name": "Write",
            "input": {"file_path": "D:/x/.claude/state/said-review.md", "content": body}}


def _with_copy(*blocks) -> list[dict]:
    """Le message, puis sa copie `api-request-blob` : la forme du vrai journal."""
    return [_message(*blocks), _message(*blocks, kind="api-request-blob")]


def _heard(tmp_path: Path, *entries) -> list[str]:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return list(tr.iter_spoken_text(str(p), limit=40, include_reviewer=True))


BRIEF = "[REVIEW-BRIEF]\n- objectif: o\n- perimetre: p\n- zones suspectes: z\n- consigne: refuter"
PASS = "[REVIEW] par relecteur le 2026-10-27 sur abc1234 — verdict: PASS, rien"


def test_a_message_and_its_copy_are_heard_once(tmp_path):
    assert _heard(tmp_path, *_with_copy(_text("bonjour"))) == ["bonjour"]


def test_two_text_blocks_in_one_message_are_heard_once_each(tmp_path):
    assert _heard(tmp_path, *_with_copy(_text("a"), _text("b"))) == ["b", "a"]   # le plus recent d'abord


def test_a_text_and_a_said_file_in_one_message_are_heard_once_each(tmp_path):
    texts = _heard(tmp_path, *_with_copy(_text("Je pose le verdict."), _said_write(PASS)))
    assert texts == [PASS, "Je pose le verdict."]   # le plus recent d'abord


def test_two_identical_texts_in_two_real_messages_stay_two(tmp_path):
    texts = _heard(tmp_path, *_with_copy(_text("a")), *_with_copy(_text("a")))
    assert texts == ["a", "a"]


def test_the_assistant_text_reader_ignores_the_copy_too(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in _with_copy(_text("bonjour"))) + "\n", encoding="utf-8")
    assert list(tr.iter_assistant_text(str(p))) == ["bonjour"]


def test_a_verdict_with_its_copy_does_not_hide_the_brief(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, *_with_copy(_text(BRIEF)), *_with_copy(_text(PASS)))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_a_verdict_in_a_said_file_with_its_copy_does_not_hide_the_brief(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, *_with_copy(_text(BRIEF)),
                   *_with_copy(_text("Je pose le verdict."), _said_write(PASS)))
    assert gate.verdict("npm publish", texts, head="abc1234") is None


def test_a_verdict_with_its_copy_but_without_a_brief_still_blocks(tmp_path):
    gate = _load("guards/pre-deploy-review-check.py")
    texts = _heard(tmp_path, *_with_copy(_text(PASS)))
    assert "GIVEN" in gate.verdict("npm publish", texts, head="abc1234")


def test_the_refusal_says_the_marker_must_come_in_an_earlier_message():
    gate = _load("guards/pre-deploy-review-check.py")
    for message in (gate._block_message("npm publish"), gate._missing_brief_message()):
        assert "BEFORE the command" in message
