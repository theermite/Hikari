"""MEMORY.md coupe a 200 lignes OU 25 Ko, selon ce qui arrive en premier -- mesure
reelle le 2026-09-18 sur le fichier de Jay : 25 Ko tombait a la ligne 115, bien
avant les 200 lignes, a cause de descriptions longues (phrase complete). Le
sommaire CHARGE (MEMORY.md) doit donc porter une description courte ; le sommaire
COMPLET (README.md) garde la description entiere -- rien n'est perdu, seulement
moins verbeux dans la vue chargee a chaque session.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import memory_index  # noqa: E402


def _fiche(desc: str) -> dict:
    return {"fichier": "feedback-x.md", "name": "X", "description": desc, "type": "feedback", "date": ""}


def test_a_short_description_is_left_untouched():
    court = "Toujours pousser."
    assert len(court) <= memory_index.LIMITE_DESCRIPTION_CHARGEE
    assert memory_index._ligne_courte(_fiche(court)) == \
        f"- [X](feedback-x.md) — {court}"


def test_a_long_description_is_cut_with_an_ellipsis():
    long = "A " * 80  # bien au-dela de la limite
    rendu = memory_index._ligne_courte(_fiche(long))
    assert rendu.endswith("…")
    desc_rendue = rendu.split("— ", 1)[1]
    assert len(desc_rendue) <= memory_index.LIMITE_DESCRIPTION_CHARGEE + 1  # +1 pour l'ellipse


def test_the_cut_lands_on_a_word_boundary_not_mid_word():
    fiche = _fiche("Un mot-tres-long-qui-ne-doit-jamais-etre-coupe-en-plein-milieu " * 3)
    rendu = memory_index._ligne_courte(fiche)
    # rien juste avant l'ellipse ne doit etre un fragment de mot coupe a la lettre
    corps = rendu.split("— ", 1)[1][:-1]  # retire le prefixe et le '…' final
    assert corps.endswith(" ") is False  # pas d'espace trainant
    assert not corps or fiche["description"].startswith(corps.rstrip())


def test_readme_full_index_keeps_the_untruncated_description():
    long = "Une description tres longue qui doit rester entiere dans le README. " * 3
    fiches = [{"fichier": "feedback-x.md", "name": "X", "description": long,
               "type": "feedback", "date": ""}]
    rendu = memory_index.rendre_index_complet(fiches)
    assert long in rendu


def test_loaded_index_uses_the_short_line_for_feedback_and_user_types():
    long = "Une description tres longue qui ne doit PAS apparaitre entiere ici. " * 3
    fiches = [{"fichier": "feedback-x.md", "name": "X", "description": long,
               "type": "feedback", "date": ""}]
    rendu = memory_index.rendre_index_charge(fiches)
    assert long not in rendu
    assert "…" in rendu


def test_real_file_now_fits_under_the_25kb_byte_cap(tmp_path):
    # Garde a l'envers concret : regenere sur un jeu de fiches realiste (memes
    # longueurs que celles trouvees ce soir) et verifie que le resultat tient.
    fiches = [
        {"fichier": f"feedback-{i}.md", "name": f"Titre {i}",
         "description": "Une phrase de correction assez longue comme celles "
                         "ecrites ce soir, avec du contexte et une raison. " * 2,
         "type": "feedback", "date": ""}
        for i in range(180)
    ]
    rendu = memory_index.rendre_index_charge(fiches)
    assert len(rendu.encode("utf-8")) < 25_000
