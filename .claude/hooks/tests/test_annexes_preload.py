"""Demande de lecture des annexes au démarrage — lues d'entrée, en un tour, plutôt que refusées en plein geste.

Pourquoi (Jay, 2026-11-09) : 54 refus d'annexe en 18 séances, chacun coûtant un aller-retour. Le démarrage
nomme les annexes du moment et demande de les lire tout de suite. Il n'inscrit RIEN comme lu (relecture
indépendante : un hook ne livre que 10 000 caractères, le reste est réduit à un aperçu) : le garde, qui voit les
vraies lectures, reste seul juge.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import annexes  # noqa: E402
from session_state import read_state  # noqa: E402

HOOK = RACINE / ".claude/hooks/lifecycle/annexes-preload.py"
_spec = importlib.util.spec_from_file_location("annexes_preload", HOOK)
preload = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preload)


def _depot(tmp_path: Path, code: bool) -> Path:
    onde = tmp_path / ".claude" / "rules-ondemand"
    onde.mkdir(parents=True)
    ids = ["conduite", "identite-et-strategie", "veille-et-savoir", "tests-et-mesures", "interface"]
    for i in ids:
        (onde / f"{i}.md").write_text(f"CONTENU-{i}\n", encoding="utf-8")
    registre = {"annexes": [{"id": i, "fichier": f".claude/rules-ondemand/{i}.md", "declencheurs": []} for i in ids],
                "au_demarrage": {"toujours": ["conduite", "identite-et-strategie"],
                                 "projet_code": ["veille-et-savoir", "tests-et-mesures"]}}
    (onde / "annexes.json").write_text(json.dumps(registre), encoding="utf-8")
    if code:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_projet_sans_code_ne_precharge_que_le_socle(tmp_path):
    racine = _depot(tmp_path, code=False)
    ids = [a["id"] for a in annexes.a_precharger(annexes.charger(racine), racine)]
    assert ids == ["conduite", "identite-et-strategie"]


def test_projet_de_code_ajoute_veille_et_tests(tmp_path):
    racine = _depot(tmp_path, code=True)
    ids = [a["id"] for a in annexes.a_precharger(annexes.charger(racine), racine)]
    assert ids == ["conduite", "identite-et-strategie", "veille-et-savoir", "tests-et-mesures"]


def test_le_demarrage_demande_la_lecture_sans_rien_inscrire(tmp_path):
    """Relecture 2026-11-09: un hook ne livre que 10 000 caractères (au-delà, le modèle reçoit un aperçu de 2 000).
    Livrer 40 Ko et inscrire « lu » laissait passer sans que la règle soit lue. Le hook DEMANDE la lecture; seul le
    garde, qui voit les vraies lectures, inscrit."""
    racine = _depot(tmp_path, code=True)
    texte = preload.build_decision(racine, "sess-1")["hookSpecificOutput"]["additionalContext"]
    for i in ("conduite", "identite-et-strategie", "veille-et-savoir", "tests-et-mesures"):
        assert f"{i}.md" in texte
    assert "CONTENU-" not in texte and "interface.md" not in texte  # le chemin, jamais le texte
    assert len(texte) < preload.PLAFOND_HOOK // 2
    assert read_state(annexes.ETAT_LUES, session_id="sess-1", repo_root=racine).get("ids", []) == []


def test_la_sortie_reelle_tient_sous_le_plafond_des_hooks():
    texte = preload.build_decision(RACINE, "sess-reel")["hookSpecificOutput"]["additionalContext"]
    assert len(texte) < preload.PLAFOND_HOOK // 2


def test_registre_sans_cle_au_demarrage_ne_livre_rien(tmp_path):
    racine = _depot(tmp_path, code=True)
    chemin = racine / ".claude" / "rules-ondemand" / "annexes.json"
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    doc.pop("au_demarrage")
    chemin.write_text(json.dumps(doc), encoding="utf-8")
    assert preload.build_decision(racine, "sess-3") == {}


def test_le_registre_reel_ne_nomme_que_des_annexes_existantes():
    registre = annexes.charger(RACINE)
    ids = {a["id"] for a in registre}
    groupes = registre.au_demarrage
    assert groupes, "le registre réel doit déclarer au_demarrage"
    for groupe in groupes.values():
        assert set(groupe) <= ids
    assert {"conduite", "identite-et-strategie"} <= set(groupes["toujours"])


def test_le_registre_reel_ajoute_veille_conventions_tests_a_un_projet_de_code(tmp_path):
    """Le dossier d'exécution varie selon le dépôt qui porte la copie: le marqueur de code vient donc d'un dossier neuf."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    ids = {a["id"] for a in annexes.a_precharger(annexes.charger(RACINE), tmp_path)}
    assert {"veille-et-savoir", "conventions-et-pile", "tests-et-mesures"} <= ids


def test_le_garde_et_le_demarrage_partagent_le_meme_nom_d_etat():
    source = (RACINE / ".claude/hooks/guards/annexes-gate.py").read_text(encoding="utf-8")
    assert "annexes.ETAT_LUES" in source
