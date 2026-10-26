"""Un seul écrivain par dépôt: deux séances qui écrivent dans le même dépôt se voient.

Doctrine § 4: « trois collisions réelles entre sessions, faute de règle ». Le verrou est un battement
de cœur, pas une serrure: une séance qui écrit laisse son identité; une autre qui arrive est avertie,
et bloquée seulement sur les gestes qui touchent à l'état partagé (commit, branche, fusion, poussée).
Jay travaille volontairement sur plusieurs séances à la fois: bloquer toute écriture serait une faute.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import writer_lock  # noqa: E402

GARDE = RACINE / ".claude/hooks/guards/writer-lock.py"


@pytest.fixture()
def depot(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_nobody_else_is_writing_when_the_repository_is_quiet(depot):
    assert writer_lock.autre_ecrivain(depot, "A", maintenant=1000.0) is None


def test_a_second_session_sees_the_first_one_who_wrote(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0)
    autre = writer_lock.autre_ecrivain(depot, "B", maintenant=1060.0)
    assert (autre["session"], autre["il_y_a_s"], autre["certain"]) == ("A", 60, True)


def test_a_session_never_sees_itself(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0)
    assert writer_lock.autre_ecrivain(depot, "A", maintenant=1010.0) is None


def test_a_writer_silent_for_five_minutes_is_gone(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0)
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1000.0 + writer_lock.TTL_S + 1) is None


def test_the_heartbeat_is_not_rewritten_on_every_call(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0)
    ecrit = writer_lock.battre(depot, "A", maintenant=1005.0)
    assert ecrit is False
    assert writer_lock.battre(depot, "A", maintenant=1000.0 + writer_lock.HEARTBEAT_S + 1) is True


def test_both_sessions_stay_known_when_they_alternate(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0)
    writer_lock.battre(depot, "B", maintenant=1040.0)
    assert writer_lock.autre_ecrivain(depot, "A", maintenant=1050.0)["session"] == "B"
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1050.0)["session"] == "A"


@pytest.mark.parametrize("commande,partage", [
    ("git commit -m x", True), ("git push", True), ("git checkout -b autre", True),
    ("git rebase main", True), ("git merge feature", True), ("git reset --hard HEAD", True),
    ("git stash", True), ("python scripts/propagate-methodology.py --apply Kobo", True),
    ("git status", False), ("pytest -q", False), ("ls", False), ("git add -- a.txt", False),
])
def test_only_gestures_touching_shared_state_are_blocked(commande, partage):
    assert writer_lock.touche_etat_partage(commande) is partage


def test_a_message_quoting_git_commit_does_not_touch_shared_state():
    assert writer_lock.touche_etat_partage('echo "puis git commit plus tard"') is False


def test_the_token_writer_ok_lets_jay_authorise_the_gesture():
    assert writer_lock.autorise_par_jay("git commit -m x # WRITER-OK: l'autre séance est la mienne")
    assert not writer_lock.autorise_par_jay("git commit -m x # WRITER-OK:")
    assert not writer_lock.autorise_par_jay("git commit -m x")


# --- le vrai garde-fou -------------------------------------------------------------------------

def _lancer(depot: Path, session: str, outil: str, entree: dict):
    charge = {"tool_name": outil, "tool_input": entree, "session_id": session, "transcript_path": ""}
    return subprocess.run([sys.executable, str(GARDE)], input=json.dumps(charge), capture_output=True,
                          text=True, cwd=depot, encoding="utf-8")


def test_the_second_session_is_warned_on_a_plain_write_but_not_blocked(depot):
    assert _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"}).returncode == 0
    r = _lancer(depot, "B", "Write", {"file_path": str(depot / "b.txt"), "content": "x"})
    assert r.returncode == 0
    assert "ÉCRIVAIN" in r.stderr


def test_the_second_session_is_blocked_on_a_commit_with_two_ways_out(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    r = _lancer(depot, "B", "Bash", {"command": "git commit -m x"})
    assert r.returncode == 2
    assert "RECOVERY" in r.stderr and "worktree" in r.stderr and "WRITER-OK" in r.stderr


def test_the_authorised_commit_goes_through(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    r = _lancer(depot, "B", "Bash", {"command": "git commit -m x # WRITER-OK: même chantier, deux fenêtres"})
    assert r.returncode == 0


def test_a_lone_session_is_never_bothered(depot):
    for outil, entree in [("Write", {"file_path": str(depot / "a.txt"), "content": "x"}),
                          ("Bash", {"command": "git commit -m x"})]:
        r = _lancer(depot, "SOLO", outil, entree)
        assert r.returncode == 0 and r.stderr == ""


def test_reading_commands_neither_register_nor_trigger(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    r = _lancer(depot, "B", "Bash", {"command": "git status"})
    assert r.returncode == 0 and r.stderr == ""


def test_a_payload_without_session_passes(depot):
    charge = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "a.txt"}})
    r = subprocess.run([sys.executable, str(GARDE)], input=charge, capture_output=True, text=True, cwd=depot)
    assert r.returncode == 0


# --- relecture indépendante du 2026-10-26 (constat 5, rejoué avant d'agir) -----------------------------
# 1. `battre()` était appelé AVANT le refus: une séance refusée devenait écrivain et refusait l'autre à son
#    tour (blocage mutuel). 2. Une séance vidée ou redémarrée change d'identifiant: son ancienne identité
#    bloquait un quart d'heure. La vivacité se lit désormais sur le journal de l'autre séance.

def test_a_refused_session_does_not_become_a_writer(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2
    assert _lancer(depot, "A", "Bash", {"command": "git commit -m x"}).returncode == 0


def _journal(depot: Path, mtime: float) -> str:
    import os
    j = depot / "journal.jsonl"
    j.write_text("{}", encoding="utf-8")
    os.utime(j, (mtime, mtime))
    return str(j)


def test_a_writer_whose_journal_keeps_moving_is_alive_without_a_new_beat(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0, journal=_journal(depot, 1350.0))
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1400.0)["session"] == "A"


def test_a_writer_whose_journal_stopped_is_gone_after_five_minutes(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0, journal=_journal(depot, 1000.0))
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1000.0 + writer_lock.TTL_S + 1) is None


def test_the_old_state_format_is_still_read(depot):
    from session_state import write_state
    write_state("writer-lock", {"ecrivains": {"A": 1000.0}}, repo_root=depot)
    autre = writer_lock.autre_ecrivain(depot, "B", maintenant=1030.0)
    assert (autre["session"], autre["il_y_a_s"], autre["certain"]) == ("A", 30, True)   # l'ancien format compte comme certain


def test_r3_the_authorisation_is_a_trailing_comment_not_a_word_in_a_message():
    # relecture n° 3 (2026-10-26): la famille « lire le texte, pas l'acte » revenait par la porte de sortie
    assert not writer_lock.autorise_par_jay('git commit -m "docs: le marqueur # WRITER-OK: raison"')
    assert not writer_lock.autorise_par_jay("git commit -m x -m 'voir # WRITER-OK: y'")
    assert not writer_lock.autorise_par_jay("echo '# WRITER-OK: z' && git push --force")
    assert writer_lock.autorise_par_jay("git commit -m x  # WRITER-OK: même chantier")


def test_r3_two_sessions_that_only_ran_tests_never_block_each_other(depot):
    _lancer(depot, "A", "Bash", {"command": "pytest -q"})
    _lancer(depot, "B", "Bash", {"command": "pnpm test"})
    assert _lancer(depot, "A", "Bash", {"command": "git commit -m x"}).returncode == 0   # B n'a fait que tester
    assert _lancer(depot, "B", "Bash", {"command": "pnpm test"}).returncode == 0          # et B continue de tester
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2    # A, lui, a commité: écrivain


# --- relecture n° 5 (2026-10-26): une écriture CERTAINE peut bloquer; une écriture POSSIBLE avertit seulement ---

def test_r5_a_possible_writer_warns_but_never_blocks_the_other_session(depot):
    _lancer(depot, "A", "Bash", {"command": "python scripts/build_site.py"})        # inconnu: écrit peut-être
    r = _lancer(depot, "B", "Bash", {"command": "git commit -m x"})
    assert r.returncode == 0 and "peut-être" in r.stderr


def test_r5_a_certain_writer_still_blocks_the_commit_of_the_other(depot):
    _lancer(depot, "A", "Bash", {"command": "pnpm add react"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2


def test_r5_a_session_never_loses_its_certain_status_by_running_something_unknown(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    _lancer(depot, "A", "Bash", {"command": "make"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2


def test_r5_a_session_that_becomes_certain_is_noted_at_once(depot):
    _lancer(depot, "A", "Bash", {"command": "make"})
    _lancer(depot, "A", "Bash", {"command": "echo x > f.txt"})                      # moins de 30 s plus tard
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2


def test_r6_a_certain_writer_stays_certain_after_a_later_beat_with_an_unknown_command(depot):
    # relecture n° 6: le test d'avant restait dans la fenêtre de 30 s, la ligne de non-rétrogradation ne s'exécutait pas
    writer_lock.battre(depot, "A", maintenant=1000.0, certain=True)
    assert writer_lock.battre(depot, "A", maintenant=1000.0 + writer_lock.HEARTBEAT_S + 5, certain=False) is True
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1050.0)["certain"] is True


def test_r6_a_possible_writer_becomes_certain_at_once_even_inside_the_beat_window(depot):
    writer_lock.battre(depot, "A", maintenant=1000.0, certain=False)
    assert writer_lock.battre(depot, "A", maintenant=1003.0, certain=True) is True
    assert writer_lock.autre_ecrivain(depot, "B", maintenant=1010.0)["certain"] is True


def test_r7_a_session_writing_only_outside_the_repository_never_blocks_the_other(depot):
    hors = depot.parent / "bloc-notes-hors-depot" / "x.txt"
    _lancer(depot, "A", "Write", {"file_path": str(hors), "content": "x"})
    _lancer(depot, "A", "Bash", {"command": "pytest -q > /tmp/out.txt"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 0


def test_r7_a_write_inside_the_repository_still_blocks(depot):
    _lancer(depot, "A", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m x"}).returncode == 2


def test_r8_committing_in_the_neighbouring_repository_neither_blocks_nor_is_blocked(depot):
    _lancer(depot, "A", "Bash", {"command": "git -C ../Shinzo commit -m x"})
    assert _lancer(depot, "B", "Bash", {"command": "git commit -m y"}).returncode == 0     # A n'a rien écrit ici
    _lancer(depot, "C", "Write", {"file_path": str(depot / "a.txt"), "content": "x"})
    sans_ici = _lancer(depot, "D", "Bash", {"command": "cd ../Shinzo && git add -- a && git commit -m z"})
    assert sans_ici.returncode == 0                                                         # D ne touche pas ce dépôt
