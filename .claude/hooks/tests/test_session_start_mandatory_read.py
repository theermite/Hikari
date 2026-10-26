"""session-start-mandatory-read — le fichier compte comme lu s'il a ete livre
par le harnais, pas seulement par un appel Read explicite.

Garde a l'envers : avant ce correctif, `_was_delivered` n'existait pas et le
hook appelait `has_read_file` seul -- un transcript ne portant QUE
l'attachment d'instructions (le cas reel a chaque session) aurait ete
signale comme manquant, alors que Takumi a deja le contenu sous les yeux.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lifecycle"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import importlib
mandatory_read = importlib.import_module("session-start-mandatory-read")


def _transcript_with_attachment(tmp_path: Path, paths: list[str]) -> Path:
    p = tmp_path / "t.jsonl"
    entry = {"attachment": {"type": "instructions",
                             "files": [{"path": fp, "type": "Project"} for fp in paths]}}
    p.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return p


def test_should_count_a_file_delivered_only_via_attachment_as_read(tmp_path):
    t = _transcript_with_attachment(
        tmp_path, ["D:\\30-Dev-Projects\\Kata\\.claude\\rules\\Monozukuri.md"])
    assert mandatory_read._was_delivered(str(t), ".claude/rules/Monozukuri.md")


def test_should_still_count_an_explicit_read_tool_call(tmp_path):
    p = tmp_path / "t.jsonl"
    entry = {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Read",
         "input": {"file_path": "D:\\...\\Monozukuri.md"}},
    ]}}
    p.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    assert mandatory_read._was_delivered(str(p), "Monozukuri.md")


def test_should_report_a_file_missing_from_both_sources(tmp_path):
    t = _transcript_with_attachment(tmp_path, ["D:\\...\\Quality.md"])
    assert not mandatory_read._was_delivered(str(t), ".claude/rules/Monozukuri.md")


def test_all_three_mandatory_files_pass_when_all_are_in_the_attachment(tmp_path):
    t = _transcript_with_attachment(tmp_path, [
        "D:\\30-Dev-Projects\\Kata\\.claude\\rules\\Interpretation-Protocol.md",
        "D:\\30-Dev-Projects\\Kata\\.claude\\rules\\Confidentiality.md",
        "D:\\30-Dev-Projects\\Kata\\.claude\\rules\\Monozukuri.md",
    ])
    missing = [mf for mf in mandatory_read.MANDATORY_FILES
               if not mandatory_read._was_delivered(str(t), mf)]
    assert missing == []


# --- la bascule des regles v2 : la porte exige les fichiers qui EXISTENT ---------------------
# Sans cela, archiver les seize anciennes regles bloquerait chaque session au demarrage : la porte
# reclamerait la lecture de fichiers absents, et la session qui voudrait la corriger serait bloquee
# par la porte elle-meme.

def _regles(tmp_path: Path, noms: list[str]) -> Path:
    dossier = tmp_path / ".claude" / "rules"
    dossier.mkdir(parents=True)
    for nom in noms:
        (dossier / nom).write_text("x", encoding="utf-8")
    return tmp_path


ANCIENNES = ["Interpretation-Protocol.md", "Confidentiality.md", "Monozukuri.md"]
V2 = ["01-Lecture.md", "07-Securite.md", "03-Qualite.md"]


def test_should_require_the_legacy_files_before_the_switch(tmp_path):
    racine = _regles(tmp_path, ANCIENNES)
    assert mandatory_read.mandatory_files(racine) == [f".claude/rules/{n}" for n in ANCIENNES]


def test_should_require_the_v2_files_once_all_three_are_there(tmp_path):
    racine = _regles(tmp_path, V2)
    assert mandatory_read.mandatory_files(racine) == [f".claude/rules/{n}" for n in V2]


def test_should_not_require_absent_legacy_files_after_archiving(tmp_path):
    # Apres la bascule : v2 presentes, anciennes archivees. Aucune ancienne n'est reclamee.
    racine = _regles(tmp_path, V2 + ["Quality.md"])
    exigees = mandatory_read.mandatory_files(racine)
    assert not any("Monozukuri" in f or "Interpretation" in f for f in exigees)


def test_should_keep_the_legacy_set_while_the_v2_copy_is_incomplete(tmp_path):
    # Copie en cours : deux v2 sur trois. On n'exige pas un jeu inacheve.
    racine = _regles(tmp_path, ANCIENNES + V2[:2])
    assert mandatory_read.mandatory_files(racine) == [f".claude/rules/{n}" for n in ANCIENNES]


def test_should_let_a_v2_file_be_edited_without_the_gate(tmp_path):
    data = {"tool_name": "Edit", "tool_input": {"file_path": r"D:\Kata\.claude\rules\03-Qualite.md"}}
    assert mandatory_read._targets_a_mandatory_file(data)
