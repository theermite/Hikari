"""MEMORY.md tient dans ce que l'outil charge : 200 lignes ET 25 Ko, sans rien perdre en silence.

Constat de la séance du 2026-11-02 : 275 souvenirs chargés, 286 lignes et 37,6 Ko ; l'outil en coupait 84 en fin de
liste (de « Relecture… » à la fin de l'alphabet), sans que personne le voie. Un sommaire dont le bas est invisible
ment par omission. Remède : le sommaire chargé ne porte que le nom de fichier de chaque souvenir, rangés à plusieurs
par ligne ; titres et descriptions restent dans README.md. Et si même cela ne tient plus, il le dit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import memory_index  # noqa: E402

MAX_LIGNES = 200
MAX_OCTETS = 25_000


def _fiches(n: int, type_: str = "feedback") -> list[dict]:
    return [{"fichier": f"{type_}-une-regle-assez-longue-pour-un-vrai-nom-{i:04d}.md",
             "name": f"Un titre {i}", "description": "une description " * 6, "type": type_, "date": ""}
            for i in range(n)]


def test_the_real_volume_fits_the_harness_limits():
    texte = memory_index.rendre_index_charge(_fiches(262) + _fiches(13, "user"))
    assert len(texte.splitlines()) <= MAX_LIGNES and len(texte.encode("utf-8")) <= MAX_OCTETS


def test_no_loaded_memory_is_missing_from_the_loaded_index():
    fiches = _fiches(262) + _fiches(13, "user")
    texte = memory_index.rendre_index_charge(fiches)
    assert [f["fichier"] for f in fiches if f["fichier"].removesuffix(".md") not in texte] == []


def test_project_and_reference_stay_out():
    texte = memory_index.rendre_index_charge(_fiches(3) + _fiches(2, "project") + _fiches(2, "reference"))
    assert "project-une-regle" not in texte and "reference-une-regle" not in texte


def test_an_overflow_is_said_not_silently_cut():
    texte = memory_index.rendre_index_charge(_fiches(3000))
    assert len(texte.splitlines()) <= MAX_LIGNES and len(texte.encode("utf-8")) <= MAX_OCTETS
    assert "README.md" in texte and "de plus" in texte


def test_the_check_agrees_with_what_is_written(tmp_path):
    for fiche in _fiches(4):
        (tmp_path / fiche["fichier"]).write_text(
            f"---\nname: {fiche['name']}\ndescription: d\ntype: feedback\n---\n\ncorps\n", encoding="utf-8")
    memory_index.ecrire_index(tmp_path)
    assert memory_index.verifier(tmp_path) == []
