"""Un marqueur lu dans une sortie d'outil n'est pas un marqueur ecrit par Takumi.

Defaut trouve en session (2026-09-14) : `latest_marker` marchait le JSON entier
de chaque ligne du transcript, sortie d'outil comprise. Lire ce module (Read)
a fait remonter la phrase de son propre docstring — « a real [VEILLE] or [SKB]
resets the counter » — comme dernier marqueur, et le garde-fou a refuse un
[VEILLE-SKIP] pourtant valide, deux fois.

Le module marker_line contenant l'exemple ci-dessus le prouve deja : ce
fichier de test cite le meme genre de phrase dans un faux resultat d'outil et
verifie qu'elle reste invisible au garde-fou.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import veille_markers  # noqa: E402


def _transcript(tmp_path: Path, *entries: dict) -> Path:
    chemin = tmp_path / "transcript.jsonl"
    chemin.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(chemin)


def _assistant_text(texte: str) -> dict:
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": texte}]}}


def _tool_result(texte: str) -> dict:
    """Forme d'une ligne de transcript pour une sortie d'outil (Read, Grep, Bash)."""
    return {
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": [{"type": "text", "text": texte}]}],
        }
    }


def test_should_survive_a_non_object_entry_when_scanning_for_a_marker(tmp_path):
    # Regression, 2ᵉ relecture independante (2026-09-14) : le garde `isinstance`
    # de l'ancienne _assistant_text_blocks a disparu dans la factorisation vers
    # transcript_reader.assistant_text_blocks. Une ligne JSON valide mais non-
    # objet (`null`) faisait planter latest_marker (AttributeError sur .get)
    # au lieu de simplement la sauter.
    # L'entree `null` doit etre la PLUS RECENTE (derniere ecrite) pour etre
    # rencontree avant le marqueur par le scan en sens inverse.
    transcript = _transcript(tmp_path, _assistant_text("[VEILLE-SKIP] motif: typo"), None)
    marker_type, _, _ = veille_markers.latest_marker(transcript)
    assert marker_type == "VEILLE-SKIP"


def test_should_ignore_a_marker_quoted_inside_a_tool_result(tmp_path):
    transcript = _transcript(
        tmp_path,
        _tool_result("un fichier de doc dit : « a real [VEILLE] or [SKB] resets the counter »"),
    )
    assert veille_markers.latest_marker(transcript) is None


def test_should_still_find_a_marker_the_assistant_really_wrote(tmp_path):
    transcript = _transcript(tmp_path, _assistant_text("[VEILLE-SKIP] motif: typo"))
    marker_type, line, _ = veille_markers.latest_marker(transcript)
    assert marker_type == "VEILLE-SKIP"
    assert "typo" in line


def test_should_prefer_the_real_marker_over_a_more_recent_tool_result(tmp_path):
    # Le resultat d'outil arrive APRES le vrai marqueur (plus proche de la fin
    # du transcript) : sans le filtre par role, il gagnerait a tort.
    transcript = _transcript(
        tmp_path,
        _assistant_text("[VEILLE] pytest@8.4 verifie 2026-09-14 via pypi.org"),
        _tool_result("RECOVERY: emit [VEILLE-SKIP] motif: <one of [...]>"),
    )
    marker_type, line, _ = veille_markers.latest_marker(transcript)
    assert marker_type == "VEILLE"
    assert "pytest" in line


# --- F3, relecture independante 2026-09-14 --------------------------------
#
# BLOCKING : TRANSCRIPT_SCAN_LIMIT (200) comptait des LIGNES BRUTES, dominees
# par les sorties d'outils. Mesure reelle : mediane 274 lignes entre un vrai
# marqueur et l'ecriture qu'il couvre, 56% au-dela de 200 lignes. Le budget
# doit compter des tours de parole de l'assistant, pas des lignes brutes.

def test_should_find_a_marker_behind_250_tool_calls(tmp_path):
    entries = [_assistant_text("[VEILLE-SKIP] motif: typo")]
    entries += [_tool_result(f"resultat de l'outil numero {i}") for i in range(250)]
    transcript = _transcript(tmp_path, *entries)
    marker_type, _, _ = veille_markers.latest_marker(transcript)
    assert marker_type == "VEILLE-SKIP"


def test_should_ignore_a_marker_inside_a_tool_use_input(tmp_path):
    # Le contenu d'un fichier ecrit (parametre `content` d'un appel Write)
    # n'est pas non plus une parole de Takumi.
    entry = {
        "message": {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": "Write",
                 "input": {"file_path": "x.md", "content": "[VEILLE] faux@1.0 verifie 2026-01-01 via nulle-part"}},
            ],
        }
    }
    transcript = _transcript(tmp_path, entry)
    assert veille_markers.latest_marker(transcript) is None
