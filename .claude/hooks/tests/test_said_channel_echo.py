"""transcript_reader — le canal « dit » par un echo, quand le journal perd le texte ET qu'ecrire un fichier est refuse.

Brief 2026-10-30: une mise en ligne relue trois fois a ete refusee quatre fois, parce que le texte des
messages portant un appel d'outil n'etait pas dans le journal. Le canal Write existait, mais le classeur
de permissions l'a refuse comme contournement. Un appel d'outil est toujours enregistre: un `echo` seul
(rien d'autre sur la ligne) qui imprime le marqueur est entendu au meme titre.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_transcript_reader_spoken_channel import _msg, _spoken, _split_thinking, _transcript  # noqa: E402

MARKER = "[REVIEW] par un contexte neuf sur abc1234 — verdict: PASS"


def _bash(tid: str, command: str) -> dict:
    return _msg("assistant", {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": command}})


def _heard(tmp_path, command):
    return _spoken(_transcript(tmp_path, *_split_thinking(), _bash("t1", command)))


def test_a_lone_echo_of_the_marker_is_heard(tmp_path):
    assert any(MARKER in t for t in _heard(tmp_path, f'echo "{MARKER}"'))


def test_a_lone_printf_of_the_marker_is_heard(tmp_path):
    assert any(MARKER in t for t in _heard(tmp_path, f"printf '%s\n' '{MARKER}'"))


def test_a_multiline_echo_keeps_its_lines(tmp_path):
    command = 'echo "[REVIEW-BRIEF]\nobjectif: x\nperimetre: y"'
    assert any(t.startswith("[REVIEW-BRIEF]\nobjectif: x") for t in _heard(tmp_path, command))


def test_an_echo_chained_to_another_command_is_not_heard(tmp_path):
    for command in (f'echo "{MARKER}" && ./deploy.sh', f'echo "{MARKER}"; rm -r x', f'echo "{MARKER}" | tee f',
                    f'echo "{MARKER}" > f.md', f'echo "{MARKER}" $(date)'):
        assert not any(MARKER in t for t in _heard(tmp_path, command)), command


def test_another_command_is_not_heard(tmp_path):
    assert not any(MARKER in t for t in _heard(tmp_path, f'cat "{MARKER}"'))


def test_an_unparseable_line_is_not_heard_and_does_not_crash(tmp_path):
    assert not any(MARKER in t for t in _heard(tmp_path, f'echo "{MARKER}'))
