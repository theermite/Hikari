"""lib/decisions.py — le registre des décisions: « est-ce tranché ? » a une seule réponse, celle du fichier.

Jay 2026-11-24: les décisions n'avaient pas de maison (éparpillées entre fiche, reprises, doctrine, 270 souvenirs), donc la seule
façon de savoir si une question était close était ma lecture, et elle a failli deux fois dans la journée. Ces tests écrivent
d'abord ce que le registre doit refuser, puis ce qu'il doit retrouver.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import decisions as d  # noqa: E402


def _projets(tmp_path: Path) -> Path:
    (tmp_path / "Shinzo" / "02-Projets").mkdir(parents=True)
    (tmp_path / "Kata" / "docs").mkdir(parents=True)
    (tmp_path / "Kata" / "docs" / "Reprise.md").write_text("x", encoding="utf-8")
    return tmp_path


def _dec(**kw) -> dict:
    base = {"id": "D-2026-11-20-takumi-maitre-expert", "sujet": "Le mot pour Takumi", "qui": "jay", "statut": "tranchee",
            "reponse": "Maître expert.", "date": "2026-11-20", "source": "Kata/docs/Reprise.md",
            "mots": ["takumi", "maître expert"]}
    base.update(kw)
    return base


def test_une_decision_complete_est_valide(tmp_path):
    assert d.valider([_dec()], _projets(tmp_path)) == []


@pytest.mark.parametrize("champ", ["id", "sujet", "qui", "statut", "date", "source"])
def test_un_champ_obligatoire_manquant_est_refuse(tmp_path, champ):
    mauvaise = _dec()
    del mauvaise[champ]
    erreurs = d.valider([mauvaise], _projets(tmp_path))
    assert erreurs and champ in " ".join(erreurs)


def test_les_valeurs_fermees_sont_imposees(tmp_path):
    p = _projets(tmp_path)
    assert d.valider([_dec(statut="peut-etre")], p)
    assert d.valider([_dec(qui="quelqu-un")], p)


def test_une_date_impossible_ou_future_est_refusee(tmp_path):
    p = _projets(tmp_path)
    assert d.valider([_dec(date="2026-13-40")], p)
    assert d.valider([_dec(date="2999-01-01")], p)


def test_une_source_qui_n_existe_pas_est_refusee(tmp_path):
    erreurs = d.valider([_dec(source="Kata/docs/Absent.md")], _projets(tmp_path))
    assert erreurs and "source" in " ".join(erreurs)


def test_une_decision_tranchee_porte_sa_reponse_une_ouverte_n_en_a_pas(tmp_path):
    p = _projets(tmp_path)
    assert d.valider([_dec(reponse="")], p)
    assert d.valider([_dec(statut="ouverte", reponse="Déjà une réponse.")], p)
    assert d.valider([_dec(statut="ouverte", reponse="")], p) == []


def test_un_identifiant_en_double_ou_mal_forme_est_refuse(tmp_path):
    p = _projets(tmp_path)
    assert d.valider([_dec(), _dec()], p)
    assert d.valider([_dec(id="n-importe-quoi")], p)


def test_une_decision_remplacee_nomme_celle_qui_la_remplace(tmp_path):
    p = _projets(tmp_path)
    ancienne = _dec(statut="remplacee", remplace_par="D-2026-11-21-autre")
    nouvelle = _dec(id="D-2026-11-21-autre", sujet="Autre")
    assert d.valider([ancienne, nouvelle], p) == []
    assert d.valider([ancienne], p), "le remplaçant doit exister"
    assert d.valider([_dec(statut="remplacee")], p), "une décision remplacée sans remplaçant est refusée"


def test_trouver_par_identifiant_ou_par_mots(tmp_path):
    registre = [_dec(), _dec(id="D-2026-11-22-autre", sujet="Autre", mots=["compaction", "seuil"])]
    assert [x["id"] for x in d.trouver("Que dit D-2026-11-20-takumi-maitre-expert ?", registre)] == ["D-2026-11-20-takumi-maitre-expert"]
    assert [x["id"] for x in d.trouver("Un seul mot pour dire ce qu'est Takumi : maître expert ?", registre)] == ["D-2026-11-20-takumi-maitre-expert"]
    assert d.trouver("Quel seuil de couleur ?", registre) == [], "tous les mots du registre doivent figurer"
    assert d.trouver("sans rapport", registre) == []


def test_charger_lit_le_fichier_et_rend_vide_si_absent(tmp_path):
    p = _projets(tmp_path)
    assert d.charger(p / "Shinzo" / "02-Projets" / "_Decisions.json") == []
    (p / "Shinzo" / "02-Projets" / "_Decisions.json").write_text(json.dumps({"decisions": [_dec()]}), encoding="utf-8")
    assert [x["id"] for x in d.charger(p / "Shinzo" / "02-Projets" / "_Decisions.json")] == ["D-2026-11-20-takumi-maitre-expert"]


def test_un_fichier_illisible_ne_casse_rien(tmp_path):
    f = tmp_path / "_Decisions.json"
    f.write_text("{pas du json", encoding="utf-8")
    assert d.charger(f) == []


def test_ouvertes_liste_les_ouvertes_et_les_a_recouper(tmp_path):
    registre = [_dec(), _dec(id="D-2026-11-22-a", statut="ouverte", reponse=""), _dec(id="D-2026-11-22-b", statut="a_recouper", reponse="")]
    assert [x["id"] for x in d.ouvertes(registre)] == ["D-2026-11-22-a", "D-2026-11-22-b"]


def test_un_mot_cle_s_apprend_au_debut_d_un_mot_pas_au_milieu():
    registre = [_dec(id="D-2026-11-24-lot", mots=["lot"])]
    assert d.trouver("Quel premier projet pilote ?", registre) == [], "lot n'est pas dans pilote"
    assert [x["id"] for x in d.trouver("Un lot entier ?", registre)] == ["D-2026-11-24-lot"]


def test_une_decision_ouverte_dont_le_sujet_reveille_une_tranchee_est_refusee_a_l_enregistrement(tmp_path):
    tranchee = _dec(id="D-2026-11-24-cadre", sujet="Cadre", mots=["relecteur", "calibration"])
    ouverte = _dec(id="D-2026-11-24-marge", sujet="Marge de la calibration comme relecteur", statut="ouverte", reponse="", mots=["marge"])
    projets = _projets(tmp_path)
    erreurs = d.valider([tranchee, ouverte], projets)
    assert erreurs and "collision" in " ".join(erreurs)
    assert d.valider([tranchee, {**ouverte, "sujet": "Quelle marge accepter ?"}], projets) == []


def test_un_sujet_ouvert_de_jay_qui_reprend_les_mots_d_une_decision_de_takumi_est_refuse(tmp_path):
    takumi = _dec(id="D-2026-11-19-rapport", qui="takumi", statut="a_recouper", reponse="", sujet="Rapport", mots=["rapport", "trace complete"])
    ouverte = _dec(id="D-2026-11-24-q", qui="jay", statut="ouverte", reponse="", sujet="Le rapport et sa trace complete", mots=["q"])
    erreurs = d.valider([takumi, ouverte], _projets(tmp_path))
    assert erreurs and "collision" in " ".join(erreurs)
