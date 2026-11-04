"""quality/memory-admission-check.py — Stop : un aveu « de mémoire / sans avoir vérifié » ne se laisse pas à Jay.

Retour de Jay (2026-11-04) : « il m'arrive que Takumi génère du code ou des documents et, plus loin, m'admette ne pas
avoir vérifié et avoir écrit de mémoire, ce qui n'est pas censé se passer ». Le garde ne devine pas qu'un texte est
faux : il lit l'AVEU de Takumi. Si la réponse finale avoue un défaut de vérification ET qu'un fichier a été écrit dans le
tour ET qu'aucune vérification (lecture, recherche, commande, web) ne suit le dernier fichier écrit, le tour reste
ouvert une fois : vérifie maintenant, corrige, puis rends compte.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "memory-admission-check.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transcript_builder import Journal  # noqa: E402

ADMIT = "Le rapport est écrit. J'ai rédigé les chiffres de mémoire, sans les avoir revérifiés dans le dépôt."


def _run(tmp_path: Path, journal: Journal, reply: str, **extra):
    payload = {"hook_event_name": "Stop", "last_assistant_message": reply, "transcript_path": journal.write_to(tmp_path / "t.jsonl"), **extra}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=20)


def _wrote() -> Journal:
    return Journal().user("écris le rapport").tool("Write", {"file_path": "/r.md"}, "ok")


def test_an_admission_after_a_write_with_no_check_after_it_is_sent_back(tmp_path):
    out = _run(tmp_path, _wrote(), ADMIT)
    assert out.returncode == 2 and b"v\xc3\xa9rifie" in out.stderr


def test_a_check_after_the_last_write_makes_the_admission_a_plain_limit(tmp_path):
    for check in (("Read", {"file_path": "/src.py"}), ("Grep", {"pattern": "x"}), ("Glob", {"pattern": "*.md"}),
                  ("Bash", {"command": "git log -3"}), ("WebFetch", {"url": "https://x.y"})):
        assert _run(tmp_path, _wrote().tool(check[0], check[1], "ok"), ADMIT).returncode == 0, check[0]


def test_a_check_before_the_write_does_not_cover_it(tmp_path):
    j = Journal().user("écris").tool("Read", {"file_path": "/src.py"}, "ok").tool("Edit", {"file_path": "/r.md"}, "ok")
    assert _run(tmp_path, j, ADMIT).returncode == 2


def test_an_admission_with_nothing_written_in_the_turn_is_left_alone(tmp_path):
    assert _run(tmp_path, Journal().user("dis-moi").bash("ls", "a"), ADMIT).returncode == 0


def test_every_form_of_the_admission_is_recognised(tmp_path):
    for reply in ("J'ai écrit ça de mémoire.", "Je n'ai pas vérifié les versions.", "Je n'ai pas relu le fichier avant de le citer.",
                  "J'ai supposé le nom de la fonction.", "Sans avoir lu le code, j'ai décrit son rôle.", "Contenu non vérifié.",
                  "Je me suis fié à ma mémoire pour la date.", "J'ai deviné le chemin.", "Je n'ai pas testé ce script."):
        assert _run(tmp_path, _wrote(), reply).returncode == 2, reply


def test_denials_and_plain_statements_are_not_admissions(tmp_path):
    for reply in ("Je n'ai rien écrit de mémoire : chaque chiffre vient d'une commande.", "Jamais de mémoire ici.",
                  "J'ai vérifié chaque version dans le dépôt.", "Tout est lu et testé, 40 tests verts.",
                  "Aucune valeur n'est écrite de mémoire."):
        assert _run(tmp_path, _wrote(), reply).returncode == 0, reply


def test_a_quoted_admission_and_a_code_block_are_ignored(tmp_path):
    assert _run(tmp_path, _wrote(), "Tu écrivais « de mémoire » dans ton retour ; c'est corrigé.").returncode == 0
    assert _run(tmp_path, _wrote(), "Voici le test :\n```\n# écrit de mémoire\n```\nFait.").returncode == 0


def test_the_hook_blocks_once_then_lets_the_second_stop_through(tmp_path):
    assert _run(tmp_path, _wrote(), ADMIT, stop_hook_active=True).returncode == 0


def test_the_guard_fails_open(tmp_path):
    assert _run(tmp_path, Journal(), ADMIT, last_assistant_message=12).returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"garbage", capture_output=True).returncode == 0
    assert _run(tmp_path, _wrote(), ADMIT, transcript_path="").returncode == 0


def test_the_message_asks_for_the_check_now(tmp_path):
    text = _run(tmp_path, _wrote(), ADMIT).stderr.decode("utf-8").lower()
    assert "vérifie" in text and "avant de rendre" in text


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/memory-admission-check.py" in settings


def test_git_add_and_commit_after_the_write_are_not_a_check(tmp_path):
    j = _wrote().bash("git add -- r.md && git commit -q -m 'docs: rapport'", "ok").bash("git push origin main", "ok")
    assert _run(tmp_path, j, ADMIT).returncode == 2
    assert _run(tmp_path, j.bash("git diff --stat", "r.md | 3 +"), ADMIT).returncode == 0
