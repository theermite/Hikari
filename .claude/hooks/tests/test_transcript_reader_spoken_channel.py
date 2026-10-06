"""transcript_reader — ce que Takumi a DIT, meme quand le journal perd son texte.

Mesure 2026-09-26 sur les 60 derniers journaux : 391 messages dont la
reflexion est enregistree en deux entrees, et AUCUN n'a garde son bloc de
texte ; 2203 messages a une seule entree de reflexion gardent le leur. Un
appel d'outil, lui, est toujours enregistre. D'ou le canal : un texte ecrit
(Write / Edit) dans <depot>/.claude/state/said-*.md compte comme dit.

Le verdict d'un relecteur arrive, lui, dans une entree a part (piece jointe
`queued_command`, origin.kind == "peer", handback) — ecrite par le relecteur,
jamais par Takumi : il ne peut ni se perdre avec son texte, ni etre invente.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import transcript_reader as tr  # noqa: E402

SAID = "D:/repo/.claude/state/said-1.md"


def _transcript(tmp_path: Path, *entries) -> Path:
    chemin = tmp_path / "transcript.jsonl"
    chemin.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return chemin


def _msg(role: str, *blocks: dict) -> dict:
    return {"type": role, "message": {"role": role, "content": list(blocks)}}


def _text(t: str) -> dict:
    return _msg("assistant", {"type": "text", "text": t})


def _split_thinking() -> list[dict]:
    """Deux entrees de reflexion : la forme ou le journal perd le texte."""
    return [_msg("assistant", {"type": "thinking", "thinking": ""}),
            _msg("assistant", {"type": "thinking", "thinking": "..."})]


def _write(tid: str, path: str, content: str) -> dict:
    return _msg("assistant", {"type": "tool_use", "id": tid, "name": "Write",
                              "input": {"file_path": path, "content": content}})


def _edit(tid: str, path: str, new: str) -> dict:
    return _msg("assistant", {"type": "tool_use", "id": tid, "name": "Edit",
                              "input": {"file_path": path, "old_string": "a", "new_string": new}})


def _result(tid: str, is_error: bool = False) -> dict:
    return _msg("user", {"type": "tool_result", "tool_use_id": tid, "is_error": is_error})


def _handback(body: str, kind: str = "peer", handback: bool = True) -> dict:
    framed = "[Subagent hand-back] The report follows:\n" + "\n".join(
        "  " + ln for ln in body.splitlines())
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": framed,
        "origin": {"kind": kind, "from": "a1", "body": framed, "handback": handback}}}


def _spoken(transcript, **kw) -> list[str]:
    return list(tr.iter_spoken_text(transcript, **kw))


# --- le canal ---------------------------------------------------------------


def test_a_said_file_is_heard_when_the_text_was_dropped(tmp_path):
    t = _transcript(tmp_path, *_split_thinking(),
                    _write("s1", SAID, "[VEILLE-SKIP] motif: test-only"), _result("s1"))
    assert _spoken(t) == ["[VEILLE-SKIP] motif: test-only"]


def test_the_old_reader_is_unchanged(tmp_path):
    # Les gardes de STYLE lisent le dernier message, toujours du texte seul :
    # elles gardent iter_assistant_text, qui ne lit pas le canal.
    t = _transcript(tmp_path, _write("s1", SAID, "dit"), _result("s1"))
    assert list(tr.iter_assistant_text(t)) == []


def test_an_edit_of_a_said_file_is_heard(tmp_path):
    t = _transcript(tmp_path, _edit("s1", SAID, "[REVIEW-BRIEF]"), _result("s1"))
    assert _spoken(t) == ["[REVIEW-BRIEF]"]


def test_the_reformulation_alias_is_heard(tmp_path):
    t = _transcript(tmp_path, _write("s1", r"C:\repo\.claude\state\reformulation.md", "REFORMULATION"),
                    _result("s1"))
    assert _spoken(t) == ["REFORMULATION"]


def test_a_failed_write_was_never_said(tmp_path):
    t = _transcript(tmp_path, _write("s1", SAID, "[VEILLE-SKIP] motif: test-only"),
                    _result("s1", is_error=True))
    assert _spoken(t) == []


def test_a_write_still_in_flight_is_heard(tmp_path):
    # Le journal ecrit les resultats apres tous les appels du message.
    t = _transcript(tmp_path, _write("s1", SAID, "dit"))
    assert _spoken(t) == ["dit"]


def test_order_is_the_journal_order_latest_first(tmp_path):
    t = _transcript(tmp_path, _text("ancien"), _write("s1", SAID, "milieu"), _result("s1"),
                    _text("recent"))
    assert _spoken(t) == ["recent", "milieu", "ancien"]


def test_limit_counts_said_files_too(tmp_path):
    t = _transcript(tmp_path, _text("a"), _write("s1", SAID, "b"), _result("s1"), _text("c"))
    assert _spoken(t, limit=2) == ["c", "b"]


def test_an_ordinary_file_is_never_speech(tmp_path):
    t = _transcript(tmp_path, _write("w1", "/repo/src/a.py", "# [VEILLE-SKIP] motif: test-only"),
                    _result("w1"))
    assert _spoken(t) == []


def test_look_alike_paths_are_not_the_channel(tmp_path):
    for path in ("/repo/.claude/state/said/x.md", "/repo/.claude/state/said.py",
                 "/repo/src/.claude/state-said.md", "/repo/.claude/state/../../src/said-1.md",
                 "/repo/.claude/state/counter.json"):
        t = _transcript(tmp_path, _write("s1", path, "dit"), _result("s1"))
        assert _spoken(t) == [], path


def test_is_said_file_is_canonical():
    assert tr.is_said_file("/r/.claude/state/said-x.md")
    assert tr.is_said_file(r"C:\R\.Claude\State\SAID.md")
    assert not tr.is_said_file("/r/.claude/state/x/../../../src/said-x.md")


# --- le verdict du relecteur ------------------------------------------------


VERDICT = "[REVIEW] par cross-model le 2026-09-28 sur abc1234 — verdict: FAIL, famille: x"


def test_a_reviewer_handback_is_heard_when_asked(tmp_path):
    t = _transcript(tmp_path, _handback(VERDICT + "\ndetail"))
    heard = _spoken(t, include_reviewer=True)
    assert len(heard) == 1
    assert VERDICT in heard[0]
    assert "\n  [REVIEW]" not in heard[0]  # le cadre d'indentation est retire


def test_a_reviewer_handback_is_not_takumi_speech_by_default(tmp_path):
    # Un [VEILLE] ecrit par un relecteur ne doit jamais ouvrir la porte de veille.
    t = _transcript(tmp_path, _handback(VERDICT))
    assert _spoken(t) == []


def test_only_a_peer_handback_counts(tmp_path):
    t = _transcript(tmp_path, _handback(VERDICT, kind="user"), _handback(VERDICT, handback=False))
    assert _spoken(t, include_reviewer=True) == []


def test_reviewer_and_speech_keep_journal_order(tmp_path):
    t = _transcript(tmp_path, _text("[REVIEW-BRIEF] avant"), _handback(VERDICT), _text("apres"))
    heard = _spoken(t, include_reviewer=True)
    assert heard[0] == "apres" and VERDICT in heard[1] and heard[2] == "[REVIEW-BRIEF] avant"


def test_a_non_object_line_does_not_break_the_channel(tmp_path):
    t = _transcript(tmp_path, None, _write("s1", SAID, "dit"), _result("s1"), 42)
    assert _spoken(t) == ["dit"]
