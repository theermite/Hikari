"""lifecycle/clear-format-inject.py — UserPromptSubmit : le gabarit de réponse est posé AVANT l'écriture.

Reproche de Jay (2026-11-02) : la vérification de forme (quality/clear-recap-check.py) corrige Takumi après qu'il a
écrit ; la réponse est écrite deux fois, ce qui coûte des jetons et alourdit la lecture. Mesure corrigée du jour :
4 réécritures en 7 jours, 1 664 mots jetés (la première mesure, 8, comptait deux fois chaque refus).
Le remède : dire la forme au moment où la séance s'ouvre, une seule fois, avec le même gabarit que la vérification.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "clear-format-inject.py"
LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))
from clear_language import TEMPLATE  # noqa: E402


def _run(repo: Path, payload: dict | bytes):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, cwd=repo)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_should_exist():
    assert HOOK.is_file()


def test_should_inject_template_when_session_opens(tmp_path):
    out = _run(_repo(tmp_path), {"session_id": "s1", "prompt": "bonjour"})
    assert out.returncode == 0
    assert TEMPLATE in out.stdout.decode("utf-8")


def test_should_stay_short_when_injecting(tmp_path):
    text = _run(_repo(tmp_path), {"session_id": "s1"}).stdout.decode("utf-8")
    assert 0 < len(text.split()) <= 220


def test_should_name_the_trigger_so_short_answers_stay_free(tmp_path):
    text = _run(_repo(tmp_path), {"session_id": "s1"}).stdout.decode("utf-8")
    assert "150 mots" in text and "question" in text


def test_should_stay_silent_when_session_already_told(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, {"session_id": "s1"})
    again = _run(repo, {"session_id": "s1"})
    assert again.returncode == 0 and again.stdout == b""


def test_should_inject_again_when_session_differs(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, {"session_id": "s1"})
    assert TEMPLATE in _run(repo, {"session_id": "s2"}).stdout.decode("utf-8")


def test_should_remind_every_twenty_fifth_prompt(tmp_path):
    """Le contexte se compacte et la consigne s'use : un rappel espacé, pas un rappel à chaque message."""
    repo = _repo(tmp_path)
    outs = [_run(repo, {"session_id": "s1"}).stdout for _ in range(26)]
    told = [i for i, o in enumerate(outs) if o]
    assert told == [0, 25]


def test_should_fail_open_when_input_is_broken(tmp_path):
    out = _run(_repo(tmp_path), b"not json")
    assert out.returncode == 0
