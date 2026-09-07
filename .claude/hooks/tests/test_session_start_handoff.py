"""Le resume de reprise remonte au demarrage — une fois, et seulement s'il est frais.

Demande de Jay, 2026-09-06 : « apres avoir fait le clear, comment est-ce que je
reprends ? ». En verifiant, le mecanisme n'existait que pour la compression
AUTOMATIQUE du contexte : rien n'ecrivait le resume avant un `/clear` voulu, et
rien ne le remontait ensuite. La reprise a chaud etait donc theorique — « livre
n'est pas declenche », famille de defauts deja rencontree trois fois.
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lifecycle" / "session-start-handoff.py"
_spec = importlib.util.spec_from_file_location("session_start_handoff", HOOK)
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


def _pose(dossier: Path, age_h: float = 0.0) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    p = dossier / h.NOM
    p.write_text("# Resume\n\n## Fils ouverts (1)\n- un fil\n", encoding="utf-8")
    quand = time.time() - age_h * 3600
    os.utime(p, (quand, quand))
    return p


def test_a_fresh_brief_is_surfaced(tmp_path):
    _pose(tmp_path)
    assert h.brief_en_attente(tmp_path) is not None


def test_no_brief_means_nothing_to_say(tmp_path):
    assert h.brief_en_attente(tmp_path) is None


def test_an_old_brief_describes_another_piece_of_work(tmp_path):
    # Au-dela de 12 h, remonter le resume rouvrirait un fil deja clos.
    _pose(tmp_path, age_h=13)
    assert h.brief_en_attente(tmp_path) is None


def test_the_freshness_limit_is_inclusive(tmp_path):
    _pose(tmp_path, age_h=11.9)
    assert h.brief_en_attente(tmp_path) is not None


def test_reading_it_once_stops_it_from_coming_back(tmp_path):
    # Un resume qui remonte a chaque session devient du bruit, et le bruit
    # finit ignore. L'artefact reste sur le disque, sous un autre nom.
    p = _pose(tmp_path)
    h.marquer_lu(p)
    assert h.brief_en_attente(tmp_path) is None
    assert (tmp_path / (h.NOM + ".lu")).exists()


def test_the_message_puts_the_open_threads_first(tmp_path):
    texte = h.message("# Resume\n\n## Fils ouverts (1)\n- un fil\n")
    assert "fils ouverts" in texte.lower()
    assert texte.index("REPRISE") < texte.index("Fils ouverts")
