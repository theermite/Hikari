"""quality/handoff-nudge.py — Stop hook: Takumi must not hand Jay a command to type.

Jay 2026-10-18 (methodology review): "trop de fois j'ai du rentrer moi-meme des commandes".
The hook reads `last_assistant_message`. A fenced shell block plus a request to run it, with
none of the closed-list reasons (secret value, consent click, admin rights, third-party
dashboard), keeps the turn open once with a reminder. It never loops, never fires when Jay
himself asked for the command, and fails open.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "handoff-nudge.py"

FENCE = "```"
ASK_RUN = f"Peux-tu relancer cette commande :\n\n{FENCE}bash\ndocker compose restart api\n{FENCE}\n"
ASK_TYPE = f"Tu peux lancer ceci dans ton terminal :\n\n{FENCE}powershell\nGet-Service Kobo\n{FENCE}\n"


def _journal(tmp_path: Path, jay_text: str) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"role": "user", "content": jay_text}) + "\n", encoding="utf-8")
    return p


def _run(payload) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    raw = raw.encode("utf-8") if isinstance(raw, str) else raw
    return subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, timeout=10)


def _msg(text, tmp_path, jay="lance le deploiement"):
    return {"last_assistant_message": text, "transcript_path": str(_journal(tmp_path, jay))}


def test_asking_jay_to_run_a_command_is_flagged(tmp_path):
    for text in (ASK_RUN, ASK_TYPE):
        r = _run(_msg(text, tmp_path))
        assert r.returncode == 2, text
        err = r.stderr.decode("utf-8").lower()
        assert "terminal" in err and "secret" in err


def test_a_closed_list_reason_allows_the_hand_off(tmp_path):
    for reason in ("Il faut ton mot de passe administrateur pour ça.", "Cloudflare demande ton consentement.",
                   "La valeur du secret doit être saisie par toi.", "Il faut des droits administrateur (UAC).",
                   "C'est dans le tableau de bord du fournisseur."):
        r = _run(_msg(f"{reason}\n\n{ASK_RUN}", tmp_path))
        assert r.returncode == 0, reason


def test_jay_asking_for_the_command_is_respected(tmp_path):
    for jay in ("donne-moi la commande", "écris-moi la commande à lancer", "quelle commande dois-je taper ?"):
        assert _run(_msg(ASK_RUN, tmp_path, jay=jay)).returncode == 0, jay


def test_a_command_block_without_a_request_passes(tmp_path):
    text = f"Voici ce que j'ai lancé :\n\n{FENCE}bash\ndocker ps\n{FENCE}\nRésultat : 3 conteneurs."
    assert _run(_msg(text, tmp_path)).returncode == 0


def test_a_request_without_a_command_block_passes(tmp_path):
    assert _run(_msg("Peux-tu me dire où se trouve le fichier ?", tmp_path)).returncode == 0


def test_second_stop_in_the_same_turn_never_loops(tmp_path):
    payload = dict(_msg(ASK_RUN, tmp_path), stop_hook_active=True)
    assert _run(payload).returncode == 0


def test_unreadable_input_fails_open():
    for raw in (b"", b"not json", b'{"last_assistant_message": 5}', b'{"transcript_path": 7}'):
        assert _run(raw).returncode == 0


def test_first_person_does_not_count_as_a_request(tmp_path):
    text = f"Si c'est propre, on relance. Confirme et je lance le dry-run :\n\n{FENCE}bash\nmake dry\n{FENCE}\n"
    assert _run(_msg(text, tmp_path)).returncode == 0
