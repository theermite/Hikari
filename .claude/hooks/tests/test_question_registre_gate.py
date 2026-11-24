"""guards/question-registre-gate.py — PreToolUse sur AskUserQuestion: on ne pose pas à Jay une décision déjà tranchée.

Jay 2026-11-24: « Ces questions, j'y ai déjà répondu ». La porte est AVANT la question (le geste est refusé, Jay ne voit rien).
Elle ne juge pas le sens: elle compare au registre. Une question à Jay doit citer l'identifiant d'une décision OUVERTE de Jay.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "question-registre-gate.py"


def _dec(ident, statut, qui="jay", reponse="", mots=None):
    return {"id": ident, "sujet": f"Sujet {ident}", "qui": qui, "statut": statut, "reponse": reponse, "date": "2026-11-20",
            "source": "Kata/docs/Reprise.md", "mots": mots or []}


REGISTRE = [
    _dec("D-2026-11-20-takumi-maitre-expert", "tranchee", reponse="Maître expert.", mots=["takumi", "un seul mot"]),
    _dec("D-2026-11-24-calibration", "ouverte"),
    _dec("D-2026-11-24-comment-technique", "ouverte", qui="takumi"),
    _dec("D-2026-11-19-libre-arbitre", "a_recouper"),
]


def _lancer(tmp_path: Path, question: str, registre=REGISTRE, outil="AskUserQuestion"):
    shinzo = tmp_path / "Shinzo"
    (shinzo / "02-Projets").mkdir(parents=True, exist_ok=True)
    if registre is not None:
        (shinzo / "02-Projets" / "_Decisions.json").write_text(json.dumps({"decisions": registre}), encoding="utf-8")
    charge = {"hook_event_name": "PreToolUse", "tool_name": outil, "session_id": "s",
              "tool_input": {"questions": [{"question": question, "header": "Choix",
                                            "options": [{"label": "Oui", "description": "x"}, {"label": "Non", "description": "y"}]}]}}
    env = {**os.environ, "SHINZO_DIR": str(shinzo), "PROJETS_DIR": str(tmp_path)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(charge).encode(), capture_output=True, timeout=30, env=env, cwd=tmp_path)


def test_une_question_deja_tranchee_est_refusee_avec_la_reponse(tmp_path):
    r = _lancer(tmp_path, "Un seul mot pour dire ce qu'est Takumi pour toi ?")
    assert r.returncode == 2
    assert b"D-2026-11-20-takumi-maitre-expert" in r.stderr and "Maître expert.".encode() in r.stderr


def test_citer_l_identifiant_d_une_tranchee_est_refuse_aussi(tmp_path):
    assert _lancer(tmp_path, "Que fait-on de D-2026-11-20-takumi-maitre-expert ?").returncode == 2


def test_une_question_qui_cite_une_decision_ouverte_de_jay_passe(tmp_path):
    assert _lancer(tmp_path, "Marge pour D-2026-11-24-calibration ?").returncode == 0


def test_une_decision_a_recouper_peut_etre_posee(tmp_path):
    assert _lancer(tmp_path, "Où écrire le libre arbitre (D-2026-11-19-libre-arbitre) ?").returncode == 0


def test_une_decision_de_takumi_n_est_jamais_posee_a_jay(tmp_path):
    r = _lancer(tmp_path, "Quel comment technique (D-2026-11-24-comment-technique) ?")
    assert r.returncode == 2 and b"Takumi" in r.stderr


def test_une_question_sans_identifiant_ouvert_est_refusee_avec_la_commande_pour_l_enregistrer(tmp_path):
    r = _lancer(tmp_path, "Quelle couleur pour le bouton ?")
    assert r.returncode == 2 and b"decisions.py ouvrir" in r.stderr


def test_sans_registre_la_porte_s_ouvre_elle_ne_devine_pas(tmp_path):
    assert _lancer(tmp_path, "Quelle couleur pour le bouton ?", registre=None).returncode == 0


def test_un_autre_outil_n_est_pas_concerne(tmp_path):
    assert _lancer(tmp_path, "Un seul mot pour dire ce qu'est Takumi", outil="Bash").returncode == 0


def test_une_entree_illisible_ne_bloque_rien(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input=b"pas du json", capture_output=True, timeout=30, cwd=tmp_path)
    assert r.returncode == 0


def test_une_decision_ouverte_posee_avec_son_sujet_n_est_pas_refusee_par_les_mots_d_une_tranchee(tmp_path):
    """Relecture du 2026-11-24 (FAIL): l'identifiant ouvert cite l'emporte sur les mots d'une decision tranchee."""
    registre = [
        _dec("D-2026-11-24-cadre", "tranchee", reponse="Opus ou DeepSeek.", mots=["relecteur", "calibration"]),
        _dec("D-2026-11-24-calibration-marge", "ouverte"),
    ]
    q = "D-2026-11-24-calibration-marge : quelle marge de calibration pour admettre un relecteur ?"
    assert _lancer(tmp_path, q, registre=registre).returncode == 0
    assert _lancer(tmp_path, q + " Et D-2026-11-24-cadre ?", registre=registre).returncode == 2, "l'identifiant explicite d'une tranchee refuse toujours"


def test_les_arrets_secret_blocage_tiers_sortant_se_declarent_et_passent(tmp_path):
    for motif in ("secret", "blocage", "tiers", "sortant"):
        assert _lancer(tmp_path, f"[ARRET] {motif} : il me manque la valeur de la cle\nQuelle valeur ?").returncode == 0, motif
    assert _lancer(tmp_path, "[ARRET] gout : deux voies possibles ici\nLaquelle ?").returncode == 2, "un choix de gout passe par le registre"
    assert _lancer(tmp_path, "[ARRET] secret : x\nQuelle valeur ?").returncode == 2, "une raison de moins de trois mots n'est pas une declaration"


def test_arret_ne_leve_pas_le_refus_d_une_decision_tranchee_ni_de_takumi(tmp_path):
    """Relecture 4116a6d, remarque 1: la declaration d'arret ne dispense que de citer une decision ouverte."""
    assert _lancer(tmp_path, "[ARRET] tiers : il faut ton avis\nOn revoit D-2026-11-20-takumi-maitre-expert ?").returncode == 2
    assert _lancer(tmp_path, "[ARRET] blocage : garde qui refuse\nUn seul mot pour dire ce qu'est Takumi ?").returncode == 2
    assert _lancer(tmp_path, "[ARRET] tiers : avis requis vite\nQuel comment technique (D-2026-11-24-comment-technique) ?").returncode == 2


def test_les_mots_d_une_decision_de_takumi_ne_refusent_pas_une_question_qui_cite_une_ouverte_de_jay(tmp_path):
    registre = [_dec("D-2026-11-19-rapport", "a_recouper", qui="takumi", mots=["rapport", "trace complete"]),
                _dec("D-2026-11-24-premier-projet", "ouverte")]
    q = "D-2026-11-24-premier-projet : le rapport donne-t-il la trace complete du premier projet ?"
    assert _lancer(tmp_path, q, registre=registre).returncode == 0
    assert _lancer(tmp_path, q + " D-2026-11-19-rapport ?", registre=registre).returncode == 2
