"""Capacités vérifiées au démarrage: une règle ne promet jamais ce qu'elle n'a pas.

Constat du 2026-10-25: les règles citent la recherche web, la vision, le coffre de savoir, le navigateur
de test; dans un harnais sans ces outils, chaque marqueur `[VEILLE] … via <source>` devient une
déclaration fausse. Un garde-fou ne voit pas les outils réellement chargés (c'est le harnais qui le
sait); il vérifie ce qui est déclaré, ce qui est refusé, et force l'état à être dit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import capacites  # noqa: E402

SONDE = RACINE / ".claude/hooks/lifecycle/capacites-check.py"
REGISTRE = json.loads((RACINE / ".claude/rules-ondemand/capacites.json").read_text(encoding="utf-8"))["capacites"]


def _etat(registre_id: str, **kw):
    base = dict(serveurs_mcp=set(), outils_refuses=set(), commandes=set(), illisibles=set())
    base.update(kw)
    return {c["id"]: c for c in capacites.diagnostiquer(REGISTRE, **base)}[registre_id]["etat"]


def test_a_declared_mcp_server_is_declared_not_connected():
    assert _etat("coffre-de-savoir", serveurs_mcp={"obsidian-vault"}) == "declaree"


def test_a_missing_mcp_server_is_not_declared():
    assert _etat("coffre-de-savoir") == "non-declaree"


def test_a_denied_tool_is_certainly_refused():
    assert _etat("recherche-web", outils_refuses={"WebSearch"}) == "refusee"


def test_web_search_is_unverifiable_when_no_rule_denies_it():
    # relecture du 2026-10-26 (constat 7): c'est un outil INTÉGRÉ, l'absence d'un refus n'est pas une preuve
    assert _etat("recherche-web") == "non-verifiable"
    assert _etat("recherche-web", outils_refuses={"WebFetch"}) == "refusee"


def test_a_command_present_on_the_machine_counts():
    assert _etat("lecture-de-documents", commandes={"pdftotext"}) == "declaree"
    assert _etat("lecture-de-documents") == "non-declaree"


def test_an_unreadable_configuration_makes_a_server_unverifiable_not_absent():
    assert _etat("coffre-de-savoir", illisibles={".claude.json"}) == "non-verifiable"
    assert _etat("coffre-de-savoir", serveurs_mcp={"obsidian-vault"}, illisibles={".claude.json"}) == "declaree"


def test_vision_can_never_be_verified_by_a_guard():
    assert _etat("vision") == "non-verifiable"


def test_the_summary_says_what_is_missing_and_what_is_degraded():
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set()))
    assert "Coffre de savoir" in texte and "lecture directe" in texte
    assert "Vision" in texte and "non vérifiable" in texte
    assert "d'après les outils réellement chargés" in texte


def test_the_summary_is_short():
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set()))
    assert len(texte.splitlines()) <= 12


def test_the_register_is_complete_and_names_its_degradation():
    ids = {c["id"] for c in REGISTRE}
    assert {"recherche-web", "coffre-de-savoir", "navigateur-de-test", "vision"} <= ids
    for c in REGISTRE:
        assert c["degradation"].strip() and c["requise_par"].strip(), c["id"]


# --- la lecture de la configuration --------------------------------------------------------------

def test_mcp_servers_are_read_from_the_user_and_project_configuration(tmp_path):
    (tmp_path / ".claude.json").write_text(json.dumps({"mcpServers": {"obsidian-vault": {}},
                                                         "projects": {}}), encoding="utf-8")
    projet = tmp_path / "proj"
    projet.mkdir()
    (projet / ".mcp.json").write_text(json.dumps({"mcpServers": {"playwright": {}}}), encoding="utf-8")
    assert capacites.serveurs_mcp(tmp_path, projet) == {"obsidian-vault", "playwright"}


def test_denied_tools_are_read_from_the_settings(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/settings.json").write_text(
        json.dumps({"permissions": {"deny": ["WebSearch", "Bash(rm -rf:*)"]}}), encoding="utf-8")
    assert capacites.outils_refuses(tmp_path, tmp_path / "absent") == {"WebSearch"}


def test_an_unreadable_configuration_is_an_empty_one(tmp_path):
    (tmp_path / ".claude.json").write_text("{pas du json", encoding="utf-8")
    assert capacites.serveurs_mcp(tmp_path, tmp_path) == set()


def test_a_malformed_configuration_file_is_named_an_absent_one_is_not(tmp_path):
    (tmp_path / ".claude.json").write_text("{pas du json", encoding="utf-8")
    projet = tmp_path / "proj"
    projet.mkdir()
    assert capacites.configurations_illisibles(tmp_path, projet) == {".claude.json"}
    (tmp_path / ".claude.json").write_text("{}", encoding="utf-8")
    assert capacites.configurations_illisibles(tmp_path, projet) == set()


def test_the_summary_says_when_the_configuration_could_not_be_read():
    diag = capacites.diagnostiquer(REGISTRE, set(), set(), set(), illisibles={".claude.json"})
    texte = capacites.resume(diag, illisibles={".claude.json"})
    assert "illisible" in texte and ".claude.json" in texte
    assert "Coffre de savoir" in texte and "non déclarée" not in texte.split("Coffre de savoir")[1].splitlines()[0]


def test_the_probe_names_a_malformed_configuration(tmp_path):
    (tmp_path / ".claude.json").write_text("{pas du json", encoding="utf-8")
    env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PATH": ""}
    r = subprocess.run([sys.executable, str(SONDE)], capture_output=True, text=True, cwd=RACINE, env=env,
                       encoding="utf-8")
    assert "illisible" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


# --- la sonde de démarrage ---------------------------------------------------------------------

def test_the_probe_announces_without_ever_blocking(tmp_path):
    env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PATH": ""}
    r = subprocess.run([sys.executable, str(SONDE)], capture_output=True, text=True, cwd=RACINE, env=env,
                       encoding="utf-8")
    assert r.returncode == 0
    sortie = json.loads(r.stdout)
    assert "Capacités" in sortie["hookSpecificOutput"]["additionalContext"]
    assert sortie["hookSpecificOutput"]["hookEventName"] == "SessionStart"
