"""La reprise après compaction, de bout en bout (essai du 2026-11-22, « trois décisions posées avant le vidage »).

Mesuré avant correction : le résumé était écrit sous `handoff-<séance>.md`, le démarrage de session lisait
`handoff-latest.md` que rien n'écrivait, et l'avertissement de fin de compaction n'allait que dans le journal.
Le modèle n'était donc jamais prévenu, et seuls les trois derniers messages de Jay survivaient.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "lifecycle"


def _transcript(dossier: Path, messages: list[str]) -> Path:
    lignes = []
    for m in messages:
        lignes.append({"type": "user", "message": {"role": "user", "content": m}})
        lignes.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "noté"}]}})
    t = dossier / "t.jsonl"
    t.write_text("\n".join(json.dumps(x) for x in lignes) + "\n", encoding="utf-8")
    return t


def _lancer(depot: Path, hook: str, evenement: str, t: Path):
    charge = {"session_id": "e2e", "transcript_path": str(t), "hook_event_name": evenement, "source": "compact"}
    return subprocess.run([sys.executable, str(HOOKS / hook)], input=json.dumps(charge), capture_output=True,
                          text=True, cwd=depot, encoding="utf-8")


def test_decisions_posed_before_a_compaction_reach_the_model_at_session_start(tmp_path):
    (tmp_path / ".git").mkdir()
    decisions = [f"Décision {i} : choix numéro {i}." for i in range(1, 6)]
    t = _transcript(tmp_path, decisions + ["Reste ouvert : le nom du rouage du revenu."])
    assert _lancer(tmp_path, "pre-compact-handoff.py", "PreCompact", t).returncode == 0
    sortie = _lancer(tmp_path, "session-start-handoff.py", "SessionStart", t).stderr
    assert "[REPRISE]" in sortie, "le modèle n'est pas prévenu qu'un résumé l'attend"
    for i in (1, 2, 3, 4, 5):
        assert f"Décision {i}" in sortie, f"la décision {i} n'a pas survécu à la compaction"
    assert "rouage du revenu" in sortie
