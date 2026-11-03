"""interaction-model-reminder.py — le modèle d'interaction pèse autant que le reste QUAND Takumi code l'interface.

Note de Jay (2026-08-30) : la qualité du modèle d'interaction (simple, agréable, évident) est ce qui compte le plus pour lui ;
la section existe dans les CDC, mais aucun garde-fou ne la mettait sous les yeux de Takumi au moment d'écrire un écran.
Ici : à la première modification d'un fichier d'interface par séance, la section du CDC est rendue (tronquée), ou son absence
est dite en une ligne. Rappel seulement. Le contenu reste le goût de Jay : le hook cite, il ne remplit jamais.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "interaction-model-reminder.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

import cdc_modele_interaction as cmi  # noqa: E402

CDC = """# CDC

## 5. Fonctions

Une liste.

## 6. Modèle d'interaction

Ton : chaleureux. États vides : une phrase qui invite. Erreurs : jamais de code technique.

### Parcours principal

Ouvrir, choisir, valider.

## 7. Risques

Autre section.
"""


def _depot(tmp_path: Path, cdc: str | None = CDC) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    if cdc is not None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "CDC.md").write_text(cdc, encoding="utf-8")
    return tmp_path


def _lancer(repo: Path, fichier: str, session: str = "s1"):
    entree = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": session, "cwd": str(repo),
                         "tool_input": {"file_path": str(repo / fichier)}})
    return subprocess.run([sys.executable, str(HOOK)], input=entree, capture_output=True, text=True, cwd=str(repo))


def _contexte(fait) -> str:
    return json.loads(fait.stdout)["hookSpecificOutput"]["additionalContext"] if fait.stdout.strip() else ""


def test_the_section_is_extracted_up_to_the_next_same_level_title():
    texte = cmi.section_modele_texte(CDC)
    assert "Ton : chaleureux" in texte and "Parcours principal" in texte and "Ouvrir, choisir, valider" in texte
    assert "Autre section" not in texte and "Une liste" not in texte


def test_no_section_gives_none():
    assert cmi.section_modele_texte("# CDC\n\n## 1. Rien\n") is None


def test_editing_a_screen_shows_the_section(tmp_path):
    fait = _lancer(_depot(tmp_path), "src/App.tsx")
    assert fait.returncode == 0
    contexte = _contexte(fait)
    assert "Ton : chaleureux" in contexte and "Modèle d'interaction" in contexte


def test_it_comes_once_per_session(tmp_path):
    repo = _depot(tmp_path)
    assert _contexte(_lancer(repo, "src/App.tsx")) != ""
    assert _contexte(_lancer(repo, "src/Other.tsx")) == ""
    assert _contexte(_lancer(repo, "src/App.tsx", session="s2")) != ""


def test_a_cdc_without_the_section_says_so_in_one_line(tmp_path):
    repo = _depot(tmp_path, "# CDC\n\n## 1. Rien\n")
    contexte = _contexte(_lancer(repo, "src/App.tsx"))
    assert "pas de section" in contexte.lower() and len(contexte.splitlines()) <= 3


def test_no_cdc_means_silence(tmp_path):
    assert _contexte(_lancer(_depot(tmp_path, None), "src/App.tsx")) == ""


def test_a_non_interface_file_says_nothing(tmp_path):
    repo = _depot(tmp_path)
    assert _contexte(_lancer(repo, "src/server.py")) == "" and _contexte(_lancer(repo, "src/App.test.tsx")) == ""


def test_a_long_section_is_cut(tmp_path):
    repo = _depot(tmp_path, "## Modèle d'interaction\n\n" + ("une phrase assez longue pour peser. " * 200))
    assert len(_contexte(_lancer(repo, "src/App.tsx"))) < 3000


def test_a_comment_line_inside_a_code_block_is_not_a_title():
    cdc = "## Modèle d'interaction\nA\n```bash\n# install\nnpm i\n```\nB\n## Suite\nautre\n"
    texte = cmi.section_modele_texte(cdc)
    assert "npm i" in texte and texte.rstrip().endswith("B") and "autre" not in texte
