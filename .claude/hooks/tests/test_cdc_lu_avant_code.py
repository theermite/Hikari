"""lifecycle/cdc-read-before-code.py — le cahier des charges se lit avant la première écriture de code.

Origine : Jay, 2026-11-01. Le code forçait la lecture de la fiche de projet au démarrage ; rien ne forçait
la lecture du CDC avant de coder. AVERTIT, ne bloque pas (un correctif d'une ligne n'a pas besoin du CDC entier).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "cdc-read-before-code.py"
_spec = importlib.util.spec_from_file_location("cdc_read_before_code", HOOK)
garde = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(garde)


def _projet(tmp_path: Path, *, cdc: str | None = "docs/CDC.md") -> Path:
    racine = tmp_path / "Projet"
    (racine / ".git").mkdir(parents=True)
    if cdc:
        (racine / cdc).parent.mkdir(parents=True, exist_ok=True)
        (racine / cdc).write_text("# CDC", encoding="utf-8")
    return racine


def _journal(tmp_path: Path, lectures: list[str], outil: str = "Read") -> Path:
    lignes = [json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": outil, "input": {"file_path": p}}]}}) for p in lectures]
    chemin = tmp_path / "t.jsonl"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin


# --- quel fichier appelle la lecture -----------------------------------------


def test_source_code_in_a_project_needs_the_cdc():
    assert garde.est_du_code("D:/p/Projet/src/app.ts")
    assert garde.est_du_code(r"D:\p\Projet\lib\mod.ex")


def test_tests_docs_methodology_and_prose_do_not():
    assert not garde.est_du_code("D:/p/Projet/docs/CDC.md")
    assert not garde.est_du_code("D:/p/Projet/.claude/hooks/x.py")
    assert not garde.est_du_code(r"D:\p\Projet\.claude\hooks\x.py")
    assert not garde.est_du_code("D:/p/Projet/src/app.test.ts")
    assert not garde.est_du_code("D:/p/Projet/README.md")


# --- le CDC du projet --------------------------------------------------------


def test_finds_a_single_file_cdc(tmp_path):
    racine = _projet(tmp_path)
    assert [p.name for p in garde.cdc_du_projet(racine)] == ["CDC.md"]


def test_finds_a_folder_cdc(tmp_path):
    racine = _projet(tmp_path, cdc="docs/CDC/01-But.md")
    assert [p.name for p in garde.cdc_du_projet(racine)] == ["01-But.md"]


def test_no_cdc_means_nothing_to_read(tmp_path):
    assert garde.cdc_du_projet(_projet(tmp_path, cdc=None)) == []


# --- lu ou non ---------------------------------------------------------------


def test_read_of_the_projects_cdc_counts(tmp_path):
    racine = _projet(tmp_path)
    journal = _journal(tmp_path, [str(racine / "docs" / "CDC.md")])
    assert garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_read_of_a_file_of_the_cdc_folder_counts(tmp_path):
    racine = _projet(tmp_path, cdc="docs/CDC/01-But.md")
    journal = _journal(tmp_path, [str(racine / "docs" / "CDC" / "01-But.md")])
    assert garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_another_projects_cdc_does_not_count(tmp_path):
    racine = _projet(tmp_path)
    journal = _journal(tmp_path, [str(tmp_path / "Autre" / "docs" / "CDC.md")])
    assert not garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_a_write_to_the_cdc_is_not_a_read(tmp_path):
    racine = _projet(tmp_path)
    journal = _journal(tmp_path, [str(racine / "docs" / "CDC.md")], outil="Write")
    assert not garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_missing_transcript_is_unread(tmp_path):
    racine = _projet(tmp_path)
    assert not garde.cdc_lu("", garde.cdc_du_projet(racine), [racine])


# --- le message --------------------------------------------------------------


def test_message_names_the_files_to_read(tmp_path):
    racine = _projet(tmp_path)
    msg = garde.message(garde.cdc_du_projet(racine))
    assert "CDC.md" in msg and "avant" in msg


def test_finds_named_cdc_files_beside_the_folder(tmp_path):
    racine = _projet(tmp_path, cdc="docs/CDC-P0.md")
    (racine / "docs" / "CDC-Hibiki-v6.md").write_text("# c", encoding="utf-8")
    assert [p.name for p in garde.cdc_du_projet(racine)] == ["CDC-Hibiki-v6.md", "CDC-P0.md"]


def test_reading_a_named_cdc_file_counts(tmp_path):
    racine = _projet(tmp_path, cdc="docs/CDC-P0.md")
    journal = _journal(tmp_path, [str(racine / "docs" / "CDC-P0.md")])
    assert garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_a_doc_that_only_looks_like_a_cdc_does_not_count(tmp_path):
    racine = _projet(tmp_path)
    journal = _journal(tmp_path, [str(racine / "docs" / "Briefs" / "CDC-notes.md"), str(racine / "docs" / "Cdcx.txt")])
    assert not garde.cdc_lu(str(journal), garde.cdc_du_projet(racine), [racine])


def test_roots_include_the_main_repo_from_a_worktree_anywhere(tmp_path):
    import os
    import subprocess
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    principal = _projet(tmp_path, cdc="docs/CDC.md")
    subprocess.run(["git", "init", "-q"], cwd=principal, check=True, env=env)
    (principal / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=principal, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=principal, check=True, env=env)
    autre = tmp_path / "_wt-ailleurs"  # hors de .claude/worktrees
    subprocess.run(["git", "worktree", "add", "-q", str(autre), "-b", "b"], cwd=principal, check=True, env=env)
    racines = [r.resolve() for r in garde._racines(autre)]
    assert autre.resolve() in racines and principal.resolve() in racines
    assert [r.resolve() for r in garde._racines(principal)] == [principal.resolve()]
