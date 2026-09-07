"""Ce qui est en suspens survit a la reprise — il ne se perd pas au /clear.

Demande de Jay, 2026-09-06 : « s'il y a des choses importantes que le resume
peut perdre, integre-les dans l'ecriture du resume ». Et : « s'il y a une
objection en suspens a un fil d'intuition, il faut l'ecrire pour la reprise ».

POURQUOI un marqueur, et pas une redaction de memoire : un resume ecrit de
memoire vieillit et ment — mesure du 2026-08-30, ou trois chiffres d'un meme
inventaire se contredisaient le meme jour. Le resume de reprise est GENERE
depuis la session ; il ne peut donc pas oublier ce qui a ete marque, et il ne
peut pas inventer ce qui ne l'a pas ete.

Ce qui se perd sans ca, mesure sur cette session meme : une objection technique
laissee ouverte en attendant une reponse, et une piste de mesure notee sans
etre suivie. Les deux disparaissent au /clear, sans laisser de trace.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from brief_builder import collect_open_threads  # noqa: E402


def _transcript(tmp_path: Path, textes_assistant) -> Path:
    p = tmp_path / "t.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for t in textes_assistant:
            f.write(json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": t}]},
            }) + "\n")
    return p


def test_a_pending_objection_is_collected(tmp_path):
    t = _transcript(tmp_path, [
        "Bilan intermediaire.",
        "[EN-SUSPENS] l'approbation piece par piece peut devenir un goulot",
    ])
    assert collect_open_threads(t) == [
        "l'approbation piece par piece peut devenir un goulot"
    ]


def test_several_threads_keep_their_order(tmp_path):
    t = _transcript(tmp_path, [
        "[EN-SUSPENS] premier fil",
        "texte sans marqueur",
        "[EN-SUSPENS] second fil",
    ])
    assert collect_open_threads(t) == ["premier fil", "second fil"]


def test_a_thread_closed_later_is_dropped(tmp_path):
    # Une objection tranchee ne doit pas revenir hanter la reprise.
    t = _transcript(tmp_path, [
        "[EN-SUSPENS] le taux de conversion n'a pas de source",
        "[RESOLU] le taux de conversion n'a pas de source",
    ])
    assert collect_open_threads(t) == []


def test_formatting_does_not_break_the_marker(tmp_path):
    # Meme tolerance que les autres marqueurs : gras, accents graves, tableau.
    t = _transcript(tmp_path, ["**[EN-SUSPENS]** un fil en gras"])
    assert collect_open_threads(t) == ["un fil en gras"]


def test_a_transcript_without_markers_yields_nothing(tmp_path):
    t = _transcript(tmp_path, ["rien a signaler"])
    assert collect_open_threads(t) == []


def test_a_missing_transcript_is_not_an_error(tmp_path):
    assert collect_open_threads(tmp_path / "absent.jsonl") == []


def test_the_brief_carries_the_open_threads(tmp_path):
    from brief_builder import build_brief

    t = _transcript(tmp_path, ["[EN-SUSPENS] la porte serveur n'est pas verifiee"])
    brief = build_brief(str(t), "sess-1", trigger="manual")

    assert "la porte serveur n'est pas verifiee" in brief
    assert "suspens" in brief.lower()


def test_the_brief_says_so_when_nothing_is_pending(tmp_path):
    # Une section absente se lit comme un oubli ; « aucun » se lit comme une reponse.
    from brief_builder import build_brief

    t = _transcript(tmp_path, ["rien a signaler"])
    brief = build_brief(str(t), "sess-1", trigger="manual")

    assert "suspens" in brief.lower()
