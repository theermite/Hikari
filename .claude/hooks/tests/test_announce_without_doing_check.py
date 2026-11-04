"""quality/announce-without-doing-check.py — Stop : annoncer la suite sans la faire.

Retour de Jay (2026-11-04) : « systématiquement, pendant qu'on travaille, Takumi s'arrête et me dit : la prochaine chose
que je vais faire, c'est ça, sauf qu'il ne se met pas à le faire ». Un tour qui se termine sur une annonce
inconditionnelle d'une action que Takumi peut faire seul est un tour perdu : Jay doit relancer. Le garde garde le tour
ouvert une fois. Il laisse passer : une question (vraie décision), une attente d'un événement extérieur (« dès que la
relecture passe »), du travail lancé en arrière-plan dans le tour, une déclaration `[ARRET]`, le marqueur
`[ANNONCE-OK] raison`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "announce-without-doing-check.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transcript_builder import Journal  # noqa: E402

_spec = importlib.util.spec_from_file_location("announce_check", HOOK)
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


def _flag(reply: str, background: bool = False) -> bool:
    return ac.announces(reply, background=background)


def test_the_announcements_jay_complained_about_are_flagged():
    for reply in ("Les tests sont verts. La prochaine étape : je lance la reprise automatique.",
                  "C'est poussé. Je vais maintenant m'occuper du cas de la clé.",
                  "Fait pour le garde. Ensuite, je traite le cas du Cockpit.",
                  "Voilà pour la première partie. Je passe maintenant à la règle de preuve.",
                  "Terminé. Prochaine chose à faire : je corrige le message de blocage.",
                  "OK. Je commence par le garde-fou des accords, puis j'enchaîne sur la preuve.",
                  "Tout est vert. J'enchaîne avec la relecture des fiches.",
                  "Ah, la prochaine chose que je vais faire, c'est le garde des accords.",
                  "Bon. Ce qu'il reste, c'est la reprise. La prochaine étape, c'est que je vais la coder."):
        assert _flag(reply), reply


def test_a_question_to_jay_is_a_real_decision_not_an_announcement():
    for reply in ("Fait. Je commence par le garde des accords, ou par la preuve ?",
                  "Prochaine étape possible : la reprise automatique. Tu la veux ?",
                  "Je vais d'abord faire X. Ça te va ?"):
        assert not _flag(reply), reply


def test_waiting_for_an_outside_event_is_not_an_announcement():
    for reply in ("Je pousse dès que la relecture passe.",
                  "Quand le verdict arrive, je corrige puis je pousse.",
                  "En attendant, je ne touche à rien : une fois la relecture revenue, je lance la suite.",
                  "Je vais pousser tout sur main si la relecture donne PASS."):
        assert not _flag(reply), reply


def test_background_work_launched_in_the_turn_makes_stopping_legitimate():
    assert not _flag("Les tests tournent. Ensuite, je commite et je pousse.", background=True)


def test_a_past_tense_report_or_a_plain_statement_is_untouched():
    for reply in ("C'est poussé (e024cf8). Tous les tests passent.", "J'ai lancé la relecture ; le verdict est PASS.",
                  "Voici l'état : 3 fils ouverts.", "", "Oui."):
        assert not _flag(reply), reply


def test_only_the_end_of_the_message_counts_not_a_plan_in_the_middle():
    reply = "Voici le plan : d'abord je vais lire, ensuite je corrige.\n\n" + "Détail du plan. " * 40 + "\nC'est tout pour ce point."
    assert not _flag(reply)


def test_a_quoted_or_coded_announcement_is_ignored():
    assert not _flag("Tu écrivais « je vais le faire ensuite » dans ton retour ; c'est corrigé.")
    assert not _flag("Exemple :\n```\n# Ensuite, je lance\n```\nFait.")


def test_a_declared_stop_and_the_explicit_marker_let_it_through():
    assert not _flag("[ARRET] quoi : la suite dépend de ce que tu veux obtenir\nEnsuite, je vais attendre ta réponse.")
    assert not _flag("Voici ce que je ferai, comme demandé : je vais d'abord lire puis corriger.\n[ANNONCE-OK] Jay a demandé le plan, pas l'exécution")


def _run(tmp_path, journal: Journal, reply: str, **extra):
    payload = {"hook_event_name": "Stop", "last_assistant_message": reply, "transcript_path": journal.write_to(tmp_path / "t.jsonl"), **extra}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=20)


def test_the_hook_blocks_once_with_a_message_that_says_to_do_it(tmp_path):
    out = _run(tmp_path, Journal().user("go").bash("ls", "a"), "Fait. Ensuite, je traite le cas du Cockpit.")
    assert out.returncode == 2 and b"fais-le" in out.stderr.lower()
    assert _run(tmp_path, Journal().user("go"), "Fait. Ensuite, je traite le cas.", stop_hook_active=True).returncode == 0


def test_a_background_agent_in_the_turn_lets_the_hook_through(tmp_path):
    j = Journal().user("go").tool("Agent", {"description": "relecture", "prompt": "relis"}, "Async agent launched successfully")
    assert _run(tmp_path, j, "La relecture tourne. Ensuite, je commite et je pousse.").returncode == 0
    j2 = Journal().user("go").tool("Monitor", {"command": "until ...; do sleep 5; done"}, "Monitor started")
    assert _run(tmp_path, j2, "J'attends. Ensuite, je pousse.").returncode == 0


def test_the_hook_fails_open(tmp_path):
    assert _run(tmp_path, Journal(), "Ensuite, je fais X.", last_assistant_message=12).returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"garbage", capture_output=True).returncode == 0
    assert _run(tmp_path, Journal(), "Ensuite, je fais X.", transcript_path="").returncode == 2  # no journal: judged on the text alone


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/announce-without-doing-check.py" in settings


# --- relecture PASS, faux refus à corriger ------------------------------------------------------------------------------


def test_a_past_tense_story_introduced_by_ensuite_or_puis_is_not_an_announcement():
    for reply in ("J'ai écrit le garde. Puis j'ai lancé la relecture, qui rend PASS.", "Rapport fini. Ensuite, j'ai rejoué les tests : 12 verts.",
                  "Après ça, j'ai commité.", "Ensuite, je n'ai rien touché d'autre.", "Puis je suis passé à la suite : fait.",
                  "Ensuite, je l'ai poussé sur main."):
        assert not _flag(reply), reply


def test_waiting_for_a_result_or_for_jay_is_not_an_announcement():
    for reply in ("Le test complet est lancé en arrière-plan (4 min). Je vais attendre son résultat avant de conclure.",
                  "Il me manque la clé. Je vais attendre ton retour.", "Je vais attendre que Jay valide la maquette.",
                  "Je vais patienter jusqu'au verdict."):
        assert not _flag(reply), reply


def test_an_announcement_followed_by_its_own_content_is_not_an_announcement():
    assert not _flag("Je vais maintenant te donner le détail :\n- A est fait\n- B est fait")


def test_a_bash_command_run_in_the_background_lets_the_turn_stop(tmp_path):
    j = Journal().user("go").tool("Bash", {"command": "pytest -q", "run_in_background": True}, "started")
    assert _run(tmp_path, j, "Le test tourne. Ensuite, je commite.").returncode == 0


def test_the_frequent_assistant_forms_are_caught_too():
    for reply in ("Fait. Il me reste à écrire la liste de portage.", "Fait. Reste à faire : coder la reprise automatique.",
                  "Fait. Puis je lance les tests.", "Fait. Je m'en occupe maintenant."):
        assert _flag(reply), reply
