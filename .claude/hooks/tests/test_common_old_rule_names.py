"""block() et warn() traduisent toute mention d'une ancienne règle, pas seulement la clé `reference=`.

Audit du 2026-11-01 : 45 garde-fous citent d'anciens noms de règles (rules/Quality.md, rules/Workflows.md…) qui n'existent
plus dans les dépôts : le modèle cherche un fichier absent. La table existait déjà (reference_actuelle) mais ne
s'appliquait qu'au champ `reference=` ; les phrases libres (« See rules/Quality.md. ») passaient telles quelles.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import common  # noqa: E402


def test_block_translates_an_old_rule_name_in_free_text(capsys):
    with pytest.raises(SystemExit) as sortie:
        common.block("BLOCKED: x. See rules/Quality.md — Test Runtime Hygiene.")
    assert sortie.value.code == 2
    err = capsys.readouterr().err
    assert "03-Qualite.md" in err and "rules/Quality.md" not in err


def test_warn_translates_an_old_rule_name_in_free_text(capsys):
    common._PENDING.clear()
    common.warn("WARNING: x. See rules/Workflows.md -> 'Veille/SKB Evidence Protocol'.")
    err = capsys.readouterr().err
    assert "02-Parcours.md" in err and "rules/Workflows.md" not in err
    assert "02-Parcours.md" in common._PENDING[-1]
    common._PENDING.clear()


def test_a_current_rule_name_is_left_alone(capsys):
    with pytest.raises(SystemExit):
        common.block("BLOCKED: x. See .claude/rules/03-Qualite.md.")
    assert capsys.readouterr().err.strip().endswith(".claude/rules/03-Qualite.md.")


def test_a_file_name_cited_as_data_is_not_rewritten(capsys):
    """Le garde de dérive liste le fichier dérivé (« rules/Quality.md ») : c'est une donnée, pas une référence."""
    common._PENDING.clear()
    common.warn("WARNING: 1 file drifted: .claude/rules/Quality.md. ACTION: fix it.")
    assert "rules/Quality.md" in capsys.readouterr().err
    common._PENDING.clear()
