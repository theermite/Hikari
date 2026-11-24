"""quality/memory-format-gate.py — PreToolUse(Write) : un souvenir s'écrit avec ses champs, avant l'écriture.

Conversion n°4 de l'audit réactif/anticipatif (2026-11-24). Mesure du jour : 643 souvenirs, 432 au schéma plat de l'annexe,
211 au format imbriqué (`metadata:`) du harnais. La porte accepte les DEUX formats ; elle avertit (procédure, ne bloque pas)
sur ce qui manque : nom, description, type valide, « comment l'appliquer » pour un retour ou un projet, champs du schéma.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

from avertissement_helpers import avertit, dit_au_modele

HOOK = Path(__file__).resolve().parents[1] / "quality" / "memory-format-gate.py"
CHEMIN = "D:/30-Dev-Projects/Shinzo/05-Memoire/feedback-exemple.md"

PLAT = """---
name: exemple
description: un souvenir plat
type: feedback
project: Kata
audience: universal
status: approved
confidence: verified
why: parce que
date: 2026-11-24
---

La règle. **Why:** parce que. **How to apply:** toujours.
"""

IMBRIQUE = """---
name: exemple
description: "un souvenir imbriqué"
metadata:
  node_type: memory
  type: feedback
  project: Kata
  audience: universal
  status: approved
  confidence: verified
  why: "parce que"
  date: 2026-11-24
---

La règle. Comment l'appliquer : toujours.
"""


def _run(contenu: str, chemin: str = CHEMIN, outil: str = "Write"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": outil, "session_id": str(uuid.uuid4()),
               "tool_input": {"file_path": chemin, "content": contenu}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20)


def _muet(res) -> bool:
    return res.returncode == 0 and not res.stderr.strip() and not res.stdout.strip()


def test_the_flat_format_complete_passes_silently():
    assert _muet(_run(PLAT))


def test_the_nested_format_complete_passes_silently():
    assert _muet(_run(IMBRIQUE))


def test_a_missing_description_is_warned_and_reaches_the_model():
    res = _run(PLAT.replace("description: un souvenir plat\n", ""))
    assert avertit(res) and dit_au_modele(res) and b"description" in res.stderr


def test_a_missing_type_is_warned_in_both_formats():
    assert b"type" in _run(PLAT.replace("type: feedback\n", "")).stderr
    assert b"type" in _run(IMBRIQUE.replace("  type: feedback\n", "")).stderr


def test_an_unknown_type_is_warned():
    res = _run(PLAT.replace("type: feedback", "type: anecdote"))
    assert avertit(res) and b"anecdote" in res.stderr


def test_a_feedback_without_how_to_apply_is_warned_but_a_reference_is_not():
    sans = PLAT.replace("**How to apply:** toujours.", "")
    assert avertit(_run(sans)) and b"appliquer" in _run(sans).stderr
    assert _muet(_run(sans.replace("type: feedback", "type: reference")))


def test_a_missing_schema_field_is_named():
    res = _run(PLAT.replace("confidence: verified\n", ""))
    assert avertit(res) and b"confidence" in res.stderr


def test_no_frontmatter_at_all_is_warned():
    assert avertit(_run("juste du texte\n"))


def test_other_files_are_left_alone():
    assert _muet(_run("pas un souvenir", chemin="D:/30-Dev-Projects/Kata/docs/x.md"))
    assert _muet(_run("sommaire", chemin="D:/30-Dev-Projects/Shinzo/05-Memoire/MEMORY.md"))
    assert _muet(_run("sommaire", chemin="D:/30-Dev-Projects/Shinzo/05-Memoire/README.md"))
    assert _muet(_run("ancien", chemin="D:/30-Dev-Projects/Shinzo/05-Memoire/_archive-doublons-2026-09-18/x.md"))
    assert _muet(_run(PLAT, chemin="D:/30-Dev-Projects/Shinzo/05-Memoire/a.txt"))


def test_an_edit_is_left_alone_because_the_whole_file_is_not_visible():
    assert _muet(_run("morceau", outil="Edit"))


def test_the_guard_fails_open():
    assert subprocess.run([sys.executable, str(HOOK)], input=b"garbage", capture_output=True).returncode == 0
    assert _run("", chemin=CHEMIN).returncode == 0


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/memory-format-gate.py" in settings


def test_comment_appliquer_without_the_article_is_accepted():
    """Relecture du 2026-11-24 : 10 souvenirs écrivent « Comment appliquer », sans « l' »."""
    assert _muet(_run(PLAT.replace("**How to apply:** toujours.", "Comment appliquer : toujours.")))
