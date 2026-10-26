"""La sonde d'entretien avertit quand la passe hebdomadaire manque, et se tait sinon.

Une boucle d'entretien dont le contrôle n'est branché nulle part n'existe pas
(doctrine § 8). La sonde ne bloque jamais : un démarrage de session passe avant elle.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
SONDE = RACINE / ".claude/hooks/lifecycle/entretien-frais-check.py"
_spec = importlib.util.spec_from_file_location("entretien_frais_check", SONDE)
sonde = importlib.util.module_from_spec(_spec)
sys.modules["entretien_frais_check"] = sonde
_spec.loader.exec_module(sonde)


def _script_canonique() -> Path:
    """Le script vit seulement dans Kata (`scripts/` n'est pas propagé): chez un receveur, le dépôt voisin `Kata`
    le porte; sans lui le test ne peut rien prouver et se saute — il ne casse pas la suite du receveur."""
    for base in (RACINE, RACINE.parent / "Kata"):
        if (base / "scripts/check-entretien-frais.py").is_file():
            return base / "scripts/check-entretien-frais.py"
    pytest.skip("scripts/check-entretien-frais.py est canonique à Kata et absent de ce dépôt")


def _depot_avec_compte(tmp_path: Path, age_jours: int | None) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    source = _script_canonique().read_text(encoding="utf-8")
    (scripts / "check-entretien-frais.py").write_text(source, encoding="utf-8")
    if age_jours is not None:
        entretien = tmp_path / "docs/Entretien"
        entretien.mkdir(parents=True)
        jour = date.today() - timedelta(days=age_jours)
        (entretien / f"{jour.isoformat()}.md").write_text("compte", encoding="utf-8")
    return tmp_path


def test_a_fresh_account_says_nothing(tmp_path):
    depot = _depot_avec_compte(tmp_path, age_jours=2)
    assert sonde.build_decision(depot) == {}


def test_a_stale_account_warns_and_names_the_command(tmp_path):
    depot = _depot_avec_compte(tmp_path, age_jours=20)
    decision = sonde.build_decision(depot)
    texte = decision["hookSpecificOutput"]["additionalContext"]
    assert "garde-methode.py" in texte
    assert decision["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "decision" not in decision  # annonce, jamais un blocage


def test_no_account_at_all_warns(tmp_path):
    depot = _depot_avec_compte(tmp_path, age_jours=None)
    assert "jamais eu lieu" in sonde.build_decision(depot)["systemMessage"]


def test_a_missing_check_script_is_announced_not_silent(tmp_path):
    decision = sonde.build_decision(tmp_path)
    assert "absent" in decision["systemMessage"]
