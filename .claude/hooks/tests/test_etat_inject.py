"""lifecycle/etat-inject.py — les faits arrivent dans mon contexte AVANT que je parle (UserPromptSubmit).

Jay 2026-11-24: la prévention doit être anticipative et déterministe. Un garde de fin de message arrive après coup. Ici, le code
calcule l'état (registre des décisions; état du chantier là où `scripts/etat.py` existe) et le dépose dans le contexte au premier
message de la séance, puis chaque fois que Jay demande un point, un état, un reste à faire, une propagation ou une décision.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "etat-inject.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
_spec = importlib.util.spec_from_file_location("etat_inject", HOOK)
ei = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ei)


def _dec(ident: str, statut: str, qui: str = "jay", date: str = "2026-11-20", reponse: str = "") -> dict:
    return {"id": ident, "sujet": f"Sujet {ident}", "qui": qui, "statut": statut, "date": date, "reponse": reponse}


def test_le_premier_message_declenche_toujours():
    assert ei.declencheur("Bonjour", premiere=True)


def test_un_message_ordinaire_ne_declenche_pas_apres_le_premier():
    assert not ei.declencheur("Corrige la fonction de tri", premiere=False)


def test_un_point_un_etat_un_reste_a_faire_une_propagation_une_decision_declenchent():
    for texte in ("fais-moi un point", "quel est l'état d'avancement ?", "ce qu'il reste à faire", "on propage le lot",
                  "as-tu fusionné la branche ?", "c'est quoi la décision sur Q1 ?", "Dis-moi où on en est"):
        assert ei.declencheur(texte, premiere=False), texte


def test_le_resume_des_decisions_met_les_ouvertes_d_abord_et_n_expose_pas_celles_de_takumi():
    registre = [_dec("D-2026-11-10-t", "tranchee", reponse="Oui."), _dec("D-2026-11-24-o", "ouverte"),
                _dec("D-2026-11-24-r", "a_recouper"), _dec("D-2026-11-24-k", "ouverte", qui="takumi")]
    texte = ei.resume_decisions(registre)
    assert texte.index("D-2026-11-24-o") < texte.index("D-2026-11-10-t")
    pour_jay = texte.split("Tranchées récemment")[0]
    assert "D-2026-11-24-k" not in pour_jay, "une décision de Takumi n'est pas une question pour Jay"


def test_le_resume_est_borne_et_deterministe():
    registre = [_dec(f"D-2026-11-{i:02d}-t", "tranchee", reponse="x", date=f"2026-11-{i:02d}") for i in range(1, 28)]
    texte = ei.resume_decisions(registre)
    assert texte == ei.resume_decisions(registre) and len(texte.splitlines()) <= 14


def test_sans_registre_le_resume_le_dit_au_lieu_de_se_taire():
    assert "registre" in ei.resume_decisions([]).lower()


def _hook(depot: Path, prompt: str, session: str, shinzo: Path):
    env = {**os.environ, "SHINZO_DIR": str(shinzo), "PROJETS_DIR": str(shinzo.parent)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"session_id": session, "prompt": prompt}).encode(),
                          capture_output=True, timeout=60, cwd=depot, env=env)


def _monde(tmp_path: Path) -> tuple[Path, Path]:
    depot = tmp_path / "depot"
    depot.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=depot, check=True)
    shinzo = tmp_path / "Shinzo"
    (shinzo / "02-Projets").mkdir(parents=True)
    (shinzo / "02-Projets" / "_Decisions.json").write_text(json.dumps({"decisions": [_dec("D-2026-11-24-o", "ouverte")]}), encoding="utf-8")
    return depot, shinzo


def test_le_hook_injecte_au_premier_message_puis_se_tait_sur_un_message_ordinaire(tmp_path):
    depot, shinzo = _monde(tmp_path)
    premier = _hook(depot, "Bonjour", "s1", shinzo)
    assert premier.returncode == 0 and b"D-2026-11-24-o" in premier.stdout and "ÉTAT CALCULÉ".encode() in premier.stdout
    second = _hook(depot, "Corrige la fonction de tri", "s1", shinzo)
    assert second.returncode == 0 and second.stdout == b""


def test_le_hook_reinjecte_quand_jay_demande_un_point(tmp_path):
    depot, shinzo = _monde(tmp_path)
    _hook(depot, "Bonjour", "s2", shinzo)
    assert b"D-2026-11-24-o" in _hook(depot, "fais-moi un point", "s2", shinzo).stdout


def test_le_hook_ne_casse_jamais_un_message(tmp_path):
    depot, shinzo = _monde(tmp_path)
    assert subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=30, cwd=depot).returncode == 0
    sans_registre = tmp_path / "vide"
    sans_registre.mkdir()
    r = _hook(depot, "Bonjour", "s3", sans_registre)
    assert r.returncode == 0 and b"registre" in r.stdout.lower()
