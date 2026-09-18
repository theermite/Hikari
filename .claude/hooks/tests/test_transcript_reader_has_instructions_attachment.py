"""has_instructions_attachment — detecte un fichier deja livre par le harnais.

Le harnais Claude Code injecte le contenu entier de CLAUDE.md et de
.claude/rules/*.md au tout debut de la session, comme une entree
{"attachment": {"type": "instructions", "files": [{"path": ..., ...}]}} dans
le transcript -- confirme sur un transcript reel le 2026-09-18 (19 fichiers,
dont les 3 fichiers de lecture obligatoire). session-start-mandatory-read.py
exigeait ensuite un second appel Read sur ces memes fichiers : le contenu
etait paye deux fois, a chaque session, sur les 32 depots.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import transcript_reader  # noqa: E402


def _write(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def test_should_find_a_file_delivered_via_instructions_attachment(tmp_path):
    p = _write(tmp_path, [{
        "attachment": {
            "type": "instructions",
            "files": [
                {"path": "D:\\30-Dev-Projects\\Kata\\.claude\\rules\\Confidentiality.md",
                 "type": "Project", "content": "..."},
            ],
        },
    }])
    assert transcript_reader.has_instructions_attachment(
        p, ".claude/rules/Confidentiality.md")


def test_should_not_find_a_file_absent_from_the_attachment(tmp_path):
    p = _write(tmp_path, [{
        "attachment": {
            "type": "instructions",
            "files": [{"path": "D:\\...\\Quality.md", "type": "Project", "content": "..."}],
        },
    }])
    assert not transcript_reader.has_instructions_attachment(
        p, ".claude/rules/Confidentiality.md")


def test_should_ignore_an_attachment_of_a_different_type(tmp_path):
    # Une piece jointe utilisateur (image, PDF) n'est pas une livraison de regle.
    p = _write(tmp_path, [{
        "attachment": {
            "type": "upload",
            "files": [{"path": ".claude/rules/Confidentiality.md"}],
        },
    }])
    assert not transcript_reader.has_instructions_attachment(
        p, ".claude/rules/Confidentiality.md")


def test_should_survive_entries_with_no_attachment_field(tmp_path):
    p = _write(tmp_path, [{"message": {"role": "user", "content": "hello"}}])
    assert not transcript_reader.has_instructions_attachment(p, "Confidentiality.md")


def test_should_survive_a_missing_transcript(tmp_path):
    assert not transcript_reader.has_instructions_attachment(
        tmp_path / "absent.jsonl", "Confidentiality.md")


def test_match_is_forward_slash_normalized_both_sides(tmp_path):
    p = _write(tmp_path, [{
        "attachment": {
            "type": "instructions",
            "files": [{"path": "D:/30-Dev-Projects/Kata/.claude/rules/Monozukuri.md"}],
        },
    }])
    assert transcript_reader.has_instructions_attachment(
        p, ".claude\\rules\\Monozukuri.md")
