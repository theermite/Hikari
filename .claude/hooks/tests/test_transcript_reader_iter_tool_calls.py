"""iter_tool_calls survit a une entree de transcript non-objet.

Trouve par la 3e relecture independante avant propagation (2026-09-14) :
assistant_text_blocks avait recu son garde `isinstance(entry, dict)` apres une
regression, mais iter_tool_calls (meme fichier, meme forme d'entree JSON
"message ou entry") ne l'a jamais eu. Une ligne JSON valide mais non-objet
(`null`) le fait planter au lieu de le sauter.

Mesure de la relecture : 0 occurrence sur 382 531 lignes de transcripts reels
-- risque de terrain faible, mais meme famille de defaut deja fermee ailleurs
dans ce fichier, laissee ouverte ici.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import transcript_reader  # noqa: E402


def _transcript(tmp_path: Path, *entries) -> Path:
    chemin = tmp_path / "transcript.jsonl"
    chemin.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return chemin


def _tool_use(name: str) -> dict:
    return {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": {}}]}}


def test_should_survive_a_non_object_entry_when_iterating_tool_calls(tmp_path):
    transcript = _transcript(tmp_path, _tool_use("Read"), None)
    appels = list(transcript_reader.iter_tool_calls(transcript))
    assert [a["name"] for a in appels] == ["Read"]


def test_should_still_find_a_real_tool_call(tmp_path):
    transcript = _transcript(tmp_path, _tool_use("Bash"))
    appels = list(transcript_reader.iter_tool_calls(transcript))
    assert len(appels) == 1
    assert appels[0]["name"] == "Bash"


# --- 2e relecture independante (2026-09-15) : la famille n'etait fermee qu'a
# moitie. Meme forme d'entree, 6 autres appelants du meme motif -- count_turns
# vit dans ce module, les 5 autres dans brief_builder/friction/logs-first/
# reformulate-gate. Un test par site, comme demande.


def _assistant_text(texte: str) -> dict:
    return {"message": {"role": "assistant", "content": [{"type": "text", "text": texte}]}}


def test_should_survive_a_non_object_entry_when_counting_turns(tmp_path):
    transcript = _transcript(tmp_path, _assistant_text("bonjour"), None)
    user, assistant = transcript_reader.count_turns(transcript)
    assert (user, assistant) == (0, 1)
