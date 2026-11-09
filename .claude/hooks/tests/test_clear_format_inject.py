"""lifecycle/clear-format-inject.py — UserPromptSubmit : un court rappel des principes de réponse de Jay.

Décision de Jay (2026-11-04) : plus de gabarit imposé. Le rappel redit ce que Jay attend (aller à l'essentiel,
court, pragmatique ; de quoi on parle, ce que ça implique, l'impact d'une décision ; « tout va bien » suffit ;
emojis modérés ; listes, check-lists et tableaux bienvenus) en 100 mots au plus, sans titres imposés.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "clear-format-inject.py"
LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))


def _run(repo: Path, payload: dict | bytes):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, cwd=repo)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def _first(tmp_path: Path) -> str:
    return _run(_repo(tmp_path), {"session_id": "s1", "prompt": "bonjour"}).stdout.decode("utf-8")


def test_should_exist():
    assert HOOK.is_file()


def test_should_inject_a_reminder_when_session_opens(tmp_path):
    assert _first(tmp_path).strip()


def test_should_stay_within_one_hundred_words(tmp_path):
    assert 0 < len(_first(tmp_path).split()) <= 100


def test_should_state_jays_principles(tmp_path):
    text = _first(tmp_path).lower()
    for key in ("essentiel", "court", "impact", "emoji", "liste", "tableau"):
        assert key in text, key


def test_should_impose_no_template(tmp_path):
    text = _first(tmp_path)
    assert "##" not in text and "Pour toi" not in text and "Gains et limites" not in text
    assert "150 mots" not in text


def test_should_stay_silent_when_session_already_told(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, {"session_id": "s1"})
    again = _run(repo, {"session_id": "s1"})
    assert again.returncode == 0 and again.stdout == b""


def test_should_inject_again_when_session_differs(tmp_path):
    repo = _repo(tmp_path)
    _run(repo, {"session_id": "s1"})
    assert _run(repo, {"session_id": "s2"}).stdout.strip()


def test_should_remind_every_sixth_prompt(tmp_path):
    """La consigne s'use vite (Jay 2026-11-09: les rapports de fin restent trop détaillés) : un rappel tous les 6 messages."""
    repo = _repo(tmp_path)
    outs = [_run(repo, {"session_id": "s1"}).stdout for _ in range(13)]
    told = [i for i, o in enumerate(outs) if o]
    assert told == [0, 6, 12]


def test_should_say_what_a_successful_end_of_work_looks_like(tmp_path):
    """Jay 2026-11-09: pas le récit de tout ce qui a été fait quand tout va bien."""
    text = _first(tmp_path).lower()
    assert "fait" in text and "vérifié" in text and "récit" in text and "détail" in text


def test_should_fail_open_when_input_is_broken(tmp_path):
    out = _run(_repo(tmp_path), b"not json")
    assert out.returncode == 0
