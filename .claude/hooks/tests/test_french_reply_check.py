"""quality/french-reply-check.py — Stop hook: Takumi answers Jay in French.

Reads `last_assistant_message` (the journal loses his text when his thinking is
split in two, 391/391 measured 2026-09-26). Refuses once per turn, never loops,
fails open on anything unreadable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "french-reply-check.py"

ENGLISH = (
    "I have read the three files and the tests that you asked me to check, and "
    "there is nothing in them that would explain why the build is failing on "
    "the server, so I will look at the logs next and then report what I find."
)
FRENCH = (
    "J'ai lu les trois fichiers et les tests que tu m'as demandé de vérifier, "
    "et rien ne explique pourquoi la construction échoue sur le serveur, donc "
    "je vais regarder les journaux ensuite et te dire ce que je trouve."
)


def _journal(tmp_path: Path, jay_text: str, assistant_text: str | None = None) -> Path:
    entries = [{"role": "user", "content": jay_text}]
    if assistant_text is not None:
        entries.append({"role": "assistant", "content": [{"type": "text", "text": assistant_text}]})
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def _run(payload: dict | str) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(HOOK)], input=raw.encode("utf-8"),
                          capture_output=True, timeout=10)


def test_english_reply_to_french_jay_is_refused_in_french(tmp_path):
    j = _journal(tmp_path, "peux-tu vérifier le build ?")
    r = _run({"last_assistant_message": ENGLISH, "transcript_path": str(j)})
    assert r.returncode == 2
    assert "français" in r.stderr.decode("utf-8").lower()


def test_french_reply_passes(tmp_path):
    j = _journal(tmp_path, "peux-tu vérifier le build ?")
    r = _run({"last_assistant_message": FRENCH, "transcript_path": str(j)})
    assert r.returncode == 0 and r.stderr == b""


def test_second_stop_in_the_same_turn_never_loops(tmp_path):
    j = _journal(tmp_path, "peux-tu vérifier le build ?")
    r = _run({"last_assistant_message": ENGLISH, "transcript_path": str(j), "stop_hook_active": True})
    assert r.returncode == 0


def test_jay_asking_for_english_is_respected(tmp_path):
    j = _journal(tmp_path, "réponds en anglais, c'est pour un client")
    r = _run({"last_assistant_message": ENGLISH, "transcript_path": str(j)})
    assert r.returncode == 0


def test_nothing_readable_fails_open(tmp_path):
    assert _run({}).returncode == 0
    assert _run("not json").returncode == 0
    assert _run({"last_assistant_message": 42, "transcript_path": 7}).returncode == 0


def test_english_in_a_code_block_is_not_refused(tmp_path):
    j = _journal(tmp_path, "montre l'exemple")
    r = _run({"last_assistant_message": f"Voici :\n\n```\n{ENGLISH}\n```", "transcript_path": str(j)})
    assert r.returncode == 0


def test_empty_message_never_falls_back_to_a_previous_turn(tmp_path):
    j = _journal(tmp_path, "lance les tests", ENGLISH)  # old English turn only in the journal
    assert _run({"last_assistant_message": "", "transcript_path": str(j)}).returncode == 0
    assert _run({"transcript_path": str(j)}).returncode == 0
