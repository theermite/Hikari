"""Tests de `memory/memory-recall.py` — rouvrir la memoire au bon moment.

Plan d'action point 3, seconde brique.

L'INCIDENT QUI LE JUSTIFIE, mesure le 2026-09-02 : une commande dangereuse a ete
lancee alors qu'un souvenir vieux de 11 jours l'interdisait explicitement. Le
souvenir existait, il etait juste, il n'a pas ete ouvert.

Le sommaire genere rend les souvenirs VISIBLES. Il ne garantit pas qu'on les
LISE au moment ou ils comptent. Un corpus visible mais jamais rouvert reste une
archive — c'est le verdict de l'audit : 0 consultation tracee sur 10 sessions.

CONTRAT — il rappelle, il ne bloque JAMAIS, et il se tait plutot que de bavarder.
Un rappel a chaque commande deviendrait du bruit, et le bruit se filtre
mentalement en trois minutes (lecon du 2026-08-30 sur les gardes trop larges).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "memory" / "memory-recall.py"
_spec = importlib.util.spec_from_file_location("memory_recall", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

INDEX = """# Memoire

## feedback — ce qui a change ma facon de travailler (3)

- [Jamais de taskkill large](feedback-never-broad-taskkill.md) — un taskkill /IM node.exe a coupe le terminal, redemarrage force.
- [Corriger la source, pas le miroir](ne-jamais-corriger-un-miroir.md) — avant de supprimer en base, demander qui ecrit dans la table.
- [Pleine largeur](feedback-full-width-no-max-width.md) — Jay refuse tout contenu centre ou plafonne.
"""


def _index(tmp_path: Path) -> Path:
    chemin = tmp_path / "MEMORY.md"
    chemin.write_text(INDEX, encoding="utf-8")
    return chemin


# --- retrouver le souvenir qui compte ----------------------------------------


def test_finds_the_memory_that_forbade_the_command(tmp_path):
    # Le cas reel du 2026-09-02, rejoue.
    trouves = mod.souvenirs_pertinents("taskkill /IM node.exe /F", _index(tmp_path))
    assert trouves
    assert "taskkill" in trouves[0]["ligne"].lower()


def test_matches_on_several_shared_words(tmp_path):
    trouves = mod.souvenirs_pertinents("psql -c 'DELETE FROM table miroir'", _index(tmp_path))
    assert any("miroir" in t["ligne"].lower() for t in trouves)


def test_stays_silent_on_an_ordinary_command(tmp_path):
    # Se taire est la bonne reponse la plupart du temps.
    for commande in ("git status", "ls -la", "pytest -q", "echo bonjour"):
        assert mod.souvenirs_pertinents(commande, _index(tmp_path)) == [], commande


def test_a_read_only_command_never_recalls_anything(tmp_path):
    """Mesure du 2026-09-05 sur le vrai sommaire : `git status` remontait deux
    souvenirs. Du bruit sur la commande la plus courante de toutes.

    La sortie n'est pas d'allonger la liste des mots bannis — ce serait « une
    liste a rallonger », defaut nomme le 2026-08-31. C'est une liste BLANCHE des
    gestes de lecture : cet ensemble-la est stable et fini.
    """
    for commande in ("git status", "git log --oneline", "ls -la", "cat fichier.md",
                     "grep taskkill partout.txt", "pytest -q"):
        assert mod.est_routine(commande), commande
        assert mod.souvenirs_pertinents(commande, _index(tmp_path)) == [], commande


def test_a_command_that_changes_something_is_not_routine():
    for commande in ("taskkill /IM node.exe", "git push --force", "docker compose up -d"):
        assert not mod.est_routine(commande), commande


def test_a_single_common_word_is_not_enough(tmp_path):
    # « avant » ou « table » seuls ne prouvent aucune pertinence.
    assert mod.souvenirs_pertinents("cat avant.txt", _index(tmp_path)) == []


def test_returns_at_most_two_memories(tmp_path):
    beaucoup = "# M\n\n" + "\n".join(
        f"- [Souvenir {i}](m{i}.md) — taskkill node terminal redemarrage force coupe."
        for i in range(9))
    chemin = tmp_path / "MEMORY.md"; chemin.write_text(beaucoup, encoding="utf-8")
    trouves = mod.souvenirs_pertinents("taskkill node terminal", chemin)
    assert 0 < len(trouves) <= 2


def test_a_missing_index_is_not_an_error(tmp_path):
    assert mod.souvenirs_pertinents("taskkill node", tmp_path / "absent.md") == []


# --- il ne se repete pas ------------------------------------------------------


def test_a_memory_is_recalled_once_per_session(tmp_path):
    etat = tmp_path / "rappeles.json"
    assert mod.doit_rappeler("feedback-never-broad-taskkill.md", etat) is True
    assert mod.doit_rappeler("feedback-never-broad-taskkill.md", etat) is False
    assert mod.doit_rappeler("un-autre.md", etat) is True


# --- le contrat de non-blocage -----------------------------------------------


def test_the_decision_is_context_never_a_refusal(tmp_path):
    decision = mod.build_decision(
        {"tool_name": "Bash", "tool_input": {"command": "taskkill /IM node.exe"}},
        index=_index(tmp_path), deja_rappele=lambda _: True)
    assert decision is not None
    texte = str(decision)
    assert "taskkill" in texte.lower()
    assert "deny" not in texte
    assert '"continue": false' not in texte


def test_no_decision_on_an_ordinary_command(tmp_path):
    assert mod.build_decision(
        {"tool_name": "Bash", "tool_input": {"command": "git status"}},
        index=_index(tmp_path), deja_rappele=lambda _: True) is None


def test_garbage_input_never_raises(tmp_path):
    for junk in ({}, {"tool_name": "Bash"}, {"tool_name": "Bash", "tool_input": None}):
        assert mod.build_decision(junk, index=_index(tmp_path),
                                  deja_rappele=lambda _: True) is None
