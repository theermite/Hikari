"""Meme defaut que veille_markers.py, trouve en meme temps (2026-09-14).

`scan_transcript_for_marker` marchait le JSON entier de chaque ligne — sortie
d'outil comprise. Un fichier lu (Read, Grep) qui cite un marqueur dans son
propre texte passait pour un marqueur ecrit par Takumi.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

HOOK = RACINE / ".claude/hooks/quality/veille-extended.py"
_spec = importlib.util.spec_from_file_location("veille_extended", HOOK)
veille_extended = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(veille_extended)


def _transcript(tmp_path: Path, *entries: dict) -> str:
    chemin = tmp_path / "transcript.jsonl"
    chemin.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(chemin)


def _assistant_text(texte: str) -> dict:
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": texte}]}}


def _tool_result(texte: str) -> dict:
    return {
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": [{"type": "text", "text": texte}]}],
        }
    }


def test_should_ignore_a_marker_quoted_inside_a_tool_result(tmp_path):
    transcript = _transcript(
        tmp_path, _tool_result("la doc dit : [VEILLE] faux@1.0 verifie 2026-01-01 via nulle-part")
    )
    assert veille_extended.scan_transcript_for_marker(transcript) is False


def test_should_still_find_a_marker_the_assistant_really_wrote(tmp_path):
    transcript = _transcript(tmp_path, _assistant_text("[SKB] consulte: docs/Audits/exemple.md"))
    assert veille_extended.scan_transcript_for_marker(transcript) is True


# --- F3, relecture independante 2026-09-14 --------------------------------
#
# BLOCKING : TRANSCRIPT_SCAN_LIMIT comptait des LIGNES BRUTES du transcript,
# une unite dominee par les sorties d'outils (souvent 1 ligne JSONL = un tour
# complet). Mesure reelle sur 157 transcripts : 83% des marqueurs authentiques
# se trouvent au-dela de 40 lignes brutes de leur point d'usage. Le budget doit
# compter des TOURS DE PAROLE de l'assistant, pas des lignes de transcript —
# un outil qui repond entre les deux ne doit rien couter au budget.

def test_should_find_a_marker_behind_40_tool_calls(tmp_path):
    entries = [_assistant_text("[VEILLE] pytest@8.4 verifie 2026-09-14 via pypi.org")]
    entries += [_tool_result(f"resultat de l'outil numero {i}") for i in range(40)]
    transcript = _transcript(tmp_path, *entries)
    assert veille_extended.scan_transcript_for_marker(transcript) is True
