# KATA-ONLY
"""scripts/decisions.py — le registre se manipule par du code, jamais à la main (valider, ouvrir, trancher, vue)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "decisions.py"
BASE = {"id": "D-2026-11-20-un-sujet", "sujet": "Un sujet", "qui": "jay", "statut": "tranchee", "reponse": "Oui.",
        "date": "2026-11-20", "source": "Kata/docs/Reprise.md", "mots": ["un sujet"]}


def _monde(tmp_path: Path) -> dict:
    (tmp_path / "Shinzo" / "02-Projets").mkdir(parents=True)
    (tmp_path / "Kata" / "docs").mkdir(parents=True)
    (tmp_path / "Kata" / "docs" / "Reprise.md").write_text("x", encoding="utf-8")
    (tmp_path / "Shinzo" / "02-Projets" / "_Decisions.json").write_text(json.dumps({"version": 1, "decisions": [BASE]}), encoding="utf-8")
    return {**os.environ, "PROJETS_DIR": str(tmp_path), "SHINZO_DIR": str(tmp_path / "Shinzo")}


def _cli(env: dict, *args: str):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, encoding="utf-8", timeout=30)


def _registre(tmp_path: Path) -> list[dict]:
    return json.loads((tmp_path / "Shinzo" / "02-Projets" / "_Decisions.json").read_text(encoding="utf-8"))["decisions"]


def test_valider_dit_valide_ou_sort_un(tmp_path):
    env = _monde(tmp_path)
    assert _cli(env, "valider").returncode == 0
    f = tmp_path / "Shinzo" / "02-Projets" / "_Decisions.json"
    f.write_text(json.dumps({"decisions": [{**BASE, "source": "Kata/docs/Absente.md"}]}), encoding="utf-8")
    r = _cli(env, "valider")
    assert r.returncode == 1 and "source introuvable" in r.stdout


def test_ouvrir_ajoute_une_decision_ouverte_validee(tmp_path):
    env = _monde(tmp_path)
    r = _cli(env, "ouvrir", "D-2026-11-24-nouvelle", "--sujet", "Une nouvelle question", "--qui", "jay", "--source", "Kata/docs/Reprise.md", "--mots", "nouvelle", "question")
    assert r.returncode == 0, r.stderr
    nouvelle = [x for x in _registre(tmp_path) if x["id"] == "D-2026-11-24-nouvelle"][0]
    assert nouvelle["statut"] == "ouverte" and nouvelle["reponse"] == ""


def test_ouvrir_refuse_un_identifiant_deja_pris_ou_une_source_absente(tmp_path):
    env = _monde(tmp_path)
    assert _cli(env, "ouvrir", BASE["id"], "--sujet", "x", "--qui", "jay", "--source", "Kata/docs/Reprise.md").returncode == 1
    assert _cli(env, "ouvrir", "D-2026-11-24-b", "--sujet", "x", "--qui", "jay", "--source", "Kata/docs/Absente.md").returncode == 1
    assert len(_registre(tmp_path)) == 1, "un refus n'écrit rien"


def test_trancher_ferme_une_decision_ouverte(tmp_path):
    env = _monde(tmp_path)
    _cli(env, "ouvrir", "D-2026-11-24-q", "--sujet", "Q", "--qui", "jay", "--source", "Kata/docs/Reprise.md")
    r = _cli(env, "trancher", "D-2026-11-24-q", "--reponse", "Fait ainsi.", "--source", "Kata/docs/Reprise.md")
    assert r.returncode == 0, r.stderr
    x = [y for y in _registre(tmp_path) if y["id"] == "D-2026-11-24-q"][0]
    assert x["statut"] == "tranchee" and x["reponse"] == "Fait ainsi."
    assert _cli(env, "trancher", "D-2026-11-24-inconnue", "--reponse", "x", "--source", "Kata/docs/Reprise.md").returncode == 1


def test_la_vue_est_generee_et_deterministe(tmp_path):
    env = _monde(tmp_path)
    premiere, seconde = _cli(env, "vue").stdout, _cli(env, "vue").stdout
    assert premiere == seconde and BASE["id"] in premiere and "| Statut |" in premiere


def test_lister_filtre_par_statut(tmp_path):
    env = _monde(tmp_path)
    assert BASE["id"] in _cli(env, "lister", "--statut", "tranchee").stdout
    assert BASE["id"] not in _cli(env, "lister", "--statut", "ouverte").stdout
