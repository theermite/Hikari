"""La sonde nomme l'interprete que les garde-fous utilisent VRAIMENT.

Ne 2026-09-06. Le message d'accueil annoncait « interprete python3 3.14.2 »
alors que le lanceur `_run.sh` execute `python` 3.13.9 — il ecarte volontairement
le raccourci Microsoft Store et retient son choix dans un fichier.

Le defaut D2 de la relecture du 2026-09-06 avait deja nomme cette famille : la
sonde regardait « des choses que les garde-fous n'empruntent PAS ». La correction
n'a porte que sur les cibles, pas sur l'interprete. Le commentaire du code
affirmait pourtant les deux.

Ce que ca coute : une sonde qui nomme le mauvais interprete envoie le prochain
diagnostic a cote, avec l'autorite d'un chiffre. Une mesure mal lue est pire
qu'aucune mesure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
SONDE = RACINE / ".claude/hooks/lifecycle/hook-health-check.py"
_spec = importlib.util.spec_from_file_location("hook_health_check", SONDE)
sonde = importlib.util.module_from_spec(_spec)
sys.modules["hook_health_check"] = sonde
_spec.loader.exec_module(sonde)


def test_the_probe_names_the_interpreter_the_launcher_retained(tmp_path):
    cache = tmp_path / ".claude" / "state" / "hook-interpreter"
    cache.parent.mkdir(parents=True)
    cache.write_text(sys.executable, encoding="utf-8")
    nom, version = sonde._interprete_qui_tourne(tmp_path)
    assert nom == sys.executable
    assert version.startswith("3.")


def test_a_retained_interpreter_that_no_longer_runs_is_not_believed(tmp_path):
    # Le cache est une trace, pas une preuve. La preuve reste l'execution.
    cache = tmp_path / ".claude" / "state" / "hook-interpreter"
    cache.parent.mkdir(parents=True)
    cache.write_text("interprete-qui-n-existe-pas", encoding="utf-8")
    nom, _ = sonde._interprete_qui_tourne(tmp_path)
    assert nom != "interprete-qui-n-existe-pas"


def test_without_a_cache_the_store_shortcut_is_only_a_last_resort():
    # Meme regle que le lanceur : le raccourci Store demarre 3x plus lentement
    # et refuse selon le contexte. Il reste valable s'il est le seul.
    assert sonde._est_dernier_recours(r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python3.exe")
    assert not sonde._est_dernier_recours(r"C:\Python313\python.exe")


def test_the_probe_agrees_with_the_launcher_on_this_machine():
    """La preuve qui compte : les deux nomment la meme chose, ici, maintenant."""
    retenu = (RACINE / ".claude/state/hook-interpreter")
    if not retenu.is_file():
        return  # rien a confronter : le lanceur n'a pas encore choisi
    nom, _ = sonde._interprete_qui_tourne(RACINE)
    assert nom == retenu.read_text(encoding="utf-8").strip()


def test_no_interpreter_at_all_stays_reported_as_such(tmp_path, monkeypatch):
    monkeypatch.setattr(sonde, "CANDIDATS", ("interprete-absent",))
    nom, version = sonde._interprete_qui_tourne(tmp_path)
    assert nom is None
    assert version == ""
