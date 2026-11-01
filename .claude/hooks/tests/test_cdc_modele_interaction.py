"""lib/cdc_modele_interaction.py — le CDC d'un projet avec interface porte sa section « Modèle d'interaction ».

Origine : Jay, 2026-11-01. Le modèle d'interaction (ton, états vides et erreurs, adaptation, parcours principal)
n'est défini par son nom que dans un projet sur 32 ; ailleurs il est partiel. C'est le goût de Jay : le code
compte les manques, il ne les remplit jamais.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import cdc_modele_interaction as m  # noqa: E402


def _projet(tmp_path, nom="P"):
    racine = tmp_path / nom
    (racine / "docs").mkdir(parents=True)
    return racine


def test_a_react_app_has_an_interface(tmp_path):
    r = _projet(tmp_path)
    (r / "package.json").write_text(json.dumps({"dependencies": {"react": "19"}}), encoding="utf-8")
    assert m.a_une_interface(r)


def test_a_react_app_in_a_subfolder_has_an_interface(tmp_path):
    r = _projet(tmp_path)
    (r / "web").mkdir()
    (r / "web" / "package.json").write_text(json.dumps({"devDependencies": {"next": "16"}}), encoding="utf-8")
    assert m.a_une_interface(r)


def test_a_desktop_python_app_has_an_interface(tmp_path):
    r = _projet(tmp_path)
    (r / "pyproject.toml").write_text('dependencies = ["PySide6>=6"]', encoding="utf-8")
    assert m.a_une_interface(r)


def test_a_server_only_project_has_none(tmp_path):
    r = _projet(tmp_path)
    (r / "package.json").write_text(json.dumps({"dependencies": {"express": "5"}}), encoding="utf-8")
    assert not m.a_une_interface(r)


def test_a_word_in_a_description_is_not_a_dependency(tmp_path):
    r = _projet(tmp_path)
    (r / "package.json").write_text(json.dumps({"description": "works with react", "dependencies": {}}), encoding="utf-8")
    assert not m.a_une_interface(r)


def test_section_is_a_heading_not_a_word(tmp_path):
    r = _projet(tmp_path)
    (r / "docs" / "CDC.md").write_text("# CDC\n## 4. Modèle d'interaction\n- ton\n", encoding="utf-8")
    assert m.a_la_section(r)
    (r / "docs" / "CDC.md").write_text("# CDC\nNous n'avons pas de modèle d'interaction défini.\n", encoding="utf-8")
    assert not m.a_la_section(r)


def test_section_found_in_a_cdc_folder_or_named_file(tmp_path):
    r = _projet(tmp_path)
    (r / "docs" / "CDC").mkdir()
    (r / "docs" / "CDC" / "02.md").write_text("### Modele d'interaction (brouillon)\n", encoding="utf-8")
    assert m.a_la_section(r)


def test_typographic_apostrophe_is_accepted(tmp_path):
    r = _projet(tmp_path)
    (r / "docs" / "CDC-P0.md").write_text("## Modèle d’interaction\n", encoding="utf-8")
    assert m.a_la_section(r)


def test_manquants_lists_only_ui_projects_with_a_cdc_but_no_section(tmp_path):
    ui = {"dependencies": {"react": "19"}}
    for nom, section in (("A", True), ("B", False)):
        r = _projet(tmp_path, nom)
        (r / "package.json").write_text(json.dumps(ui), encoding="utf-8")
        (r / "docs" / "CDC.md").write_text("## Modèle d'interaction\n" if section else "# CDC\n", encoding="utf-8")
    c = _projet(tmp_path, "C")  # interface sans CDC: autre manque, pas celui-ci
    (c / "package.json").write_text(json.dumps(ui), encoding="utf-8")
    d = _projet(tmp_path, "D")  # CDC sans interface
    (d / "docs" / "CDC.md").write_text("# CDC\n", encoding="utf-8")
    assert m.manquants(["A", "B", "C", "D", "Absent"], tmp_path) == ["B"]


def test_a_monorepo_app_under_apps_has_an_interface(tmp_path):
    r = _projet(tmp_path)
    (r / "apps" / "web").mkdir(parents=True)
    (r / "apps" / "web" / "package.json").write_text(json.dumps({"dependencies": {"next": "16"}}), encoding="utf-8")
    assert m.a_une_interface(r)
