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


def test_web_search_is_a_builtin_presumed_present_when_no_rule_denies_it():
    # 2026-10-28 : deux seances ont declare [VEILLE-IMPOSSIBLE] alors que WebSearch et WebFetch existent
    # (outils differes a charger par ToolSearch). Un outil fourni par l'application est presume present.
    assert _etat("recherche-web") == "integree"
    assert _etat("recherche-web", outils_refuses={"WebFetch"}) == "refusee"


def test_a_command_present_on_the_machine_counts():
    assert _etat("lecture-de-documents", commandes={"pdftotext"}) == "declaree"
    assert _etat("lecture-de-documents") == "non-declaree"


def test_an_unreadable_configuration_makes_a_server_unverifiable_not_absent():
    assert _etat("coffre-de-savoir", illisibles={".claude.json"}) == "non-verifiable"
    assert _etat("coffre-de-savoir", serveurs_mcp={"obsidian-vault"}, illisibles={".claude.json"}) == "declaree"


def test_vision_is_a_builtin_read_by_the_read_tool_and_refused_if_read_is_denied():
    assert _etat("vision") == "integree"
    assert _etat("vision", outils_refuses={"Read"}) == "refusee"


def test_the_summary_says_what_is_missing_and_what_is_degraded():
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set()))
    assert "Coffre de savoir" in texte and "lecture directe" in texte
    assert "Vision" in texte and "Read" in texte
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


# --- les capacites INTEGREES a l'application (2026-10-28) ------------------------------------------
# Cause : « Recherche web — non vérifiable (…) → [VEILLE-IMPOSSIBLE] motif: pas-d-acces-web ». La fleche se
# lisait comme une consigne : deux seances ont declare l'impossibilite sans chercher l'outil, qui etait
# seulement DIFFERE (a charger par ToolSearch). La vision, elle, passe par l'outil Read.

def _resume_par_defaut() -> str:
    return capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set()))


def test_the_summary_never_ties_the_impossibility_marker_to_an_unverified_builtin():
    texte = _resume_par_defaut()
    ligne = next(l for l in texte.splitlines() if "Recherche web" in l)
    assert "présumée présente" in ligne
    assert "ToolSearch" in ligne
    # l'impossibilite n'est dite que sous condition : apres un essai de chargement qui echoue
    assert "VEILLE-IMPOSSIBLE" not in ligne.split("ToolSearch")[0]
    assert "seulement" in ligne.split("VEILLE-IMPOSSIBLE")[0]


def test_the_summary_tells_how_to_load_the_deferred_web_tools():
    assert "select:WebSearch,WebFetch" in _resume_par_defaut()


def test_the_summary_tells_vision_to_be_tried_with_read_before_giving_up():
    ligne = next(l for l in _resume_par_defaut().splitlines() if "Vision" in l)
    assert "Read" in ligne and "avant" in ligne


def test_a_builtin_that_is_refused_keeps_its_degradation_without_the_loading_advice():
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), {"WebSearch"}, set()))
    ligne = next(l for l in texte.splitlines() if "Recherche web" in l)
    assert "refusée" in ligne and "VEILLE-IMPOSSIBLE" in ligne and "ToolSearch" not in ligne


def test_every_builtin_of_the_register_says_how_to_confirm_it():
    integrees = [c for c in REGISTRE if c.get("integree")]
    assert {c["id"] for c in integrees} == {"recherche-web", "vision"}
    for c in integrees:
        assert c["confirmation"].strip(), c["id"]


def test_a_non_builtin_without_proof_stays_unverifiable():
    assert _etat("suivi-d-erreurs") == "non-verifiable"


def test_the_probe_text_given_at_startup_carries_the_builtin_advice(tmp_path):
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set()))
    assert texte.count("select:WebSearch,WebFetch") == 1


# --- sonde du navigateur de test (2026-10-29) ---------------------------------------------------
# L'application de bureau fournit un navigateur integre (outils mcp__Claude_Browser__*) ; le terminal non.
# Le point d'entree de la seance (CLAUDE_CODE_ENTRYPOINT) dit lequel des deux on est.

def test_the_desktop_app_provides_a_builtin_test_browser():
    assert _etat("navigateur-de-test", entrypoint="claude-desktop") == "integree"


def test_outside_the_desktop_app_the_test_browser_needs_a_declared_server():
    assert _etat("navigateur-de-test", entrypoint="cli") == "non-declaree"
    assert _etat("navigateur-de-test") == "non-declaree"
    assert _etat("navigateur-de-test", entrypoint="cli", serveurs_mcp={"playwright"}) == "declaree"
    # notre propre serveur web (shinkofa-web, 2026-10-29) est la preuve attendue ; il remplace le serveur Playwright
    assert _etat("navigateur-de-test", entrypoint="cli", serveurs_mcp={"shinkofa-web"}) == "declaree"


def test_the_builtin_browser_says_how_to_confirm_it():
    texte = capacites.resume(capacites.diagnostiquer(REGISTRE, set(), set(), set(), entrypoint="claude-desktop"))
    ligne = next(l for l in texte.splitlines() if "Navigateur de test" in l)
    assert "mcp__Claude_Browser__" in ligne and "intégrée" in ligne


def test_the_probe_reads_the_entrypoint_from_the_environment(tmp_path):
    import os
    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "claude-desktop", "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    sortie = subprocess.run([sys.executable, str(SONDE)], input=b"{}", capture_output=True, timeout=20, env=env, cwd=str(RACINE))
    assert b"mcp__Claude_Browser__" in sortie.stdout


def test_our_web_server_is_named_as_the_first_proof_and_says_what_it_is_good_for():
    nav = next(c for c in REGISTRE if c["id"] == "navigateur-de-test")
    assert nav["preuve"]["mcp"][0] == "shinkofa-web"
    assert "web_check" in nav["confirmation"] and "browser_open" in nav["confirmation"]
