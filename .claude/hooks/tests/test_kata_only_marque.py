# KATA-ONLY
"""Un test qui lit `scripts/` porte la marque `# KATA-ONLY` : sinon la suite de chaque dépôt receveur casse à la collecte.

Famille revenue quatre fois (relecture indépendante du 2026-11-24). La marque est lue par `conftest.py`, qui ne collecte pas ces
tests là où `scripts/` ne voyage pas. Un test déjà gardé (`skipif` sur `DANS_KATA`, ou un `.is_file()` / `.exists()` sur le chemin
`scripts/…`) est accepté aussi : certains tests existent justement POUR le receveur et ne doivent pas être écartés là-bas.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import est_kata_seulement

TESTS = Path(__file__).resolve().parent
LIT_SCRIPTS = re.compile(r"""(?:RACINE|ROOT|parents\[\d\])\s*/\s*["']scripts["']""")
PARADE = re.compile(r"""DANS_KATA|skipif|["']scripts["'][^\n]*\.(?:is_file|exists)\(\)""")


def test_a_test_reading_scripts_is_marked_or_guarded():
    sans_marque = []
    for f in sorted(TESTS.glob("test_*.py")):
        texte = f.read_text(encoding="utf-8", errors="replace")
        if LIT_SCRIPTS.search(texte) and not est_kata_seulement(f) and not PARADE.search(texte):
            sans_marque.append(f.name)
    assert not sans_marque, f"lisent scripts/ sans `# KATA-ONLY` ni parade : {sans_marque}"


def test_the_marker_is_recognised_only_in_the_first_lines(tmp_path):
    haut = tmp_path / "test_a.py"
    haut.write_text("# KATA-ONLY\nx = 1\n", encoding="utf-8")
    bas = tmp_path / "test_b.py"
    bas.write_text("\n" * 40 + "# KATA-ONLY\n", encoding="utf-8")
    assert est_kata_seulement(haut) and not est_kata_seulement(bas)


def test_a_marked_test_is_not_collected_where_scripts_does_not_travel(tmp_path):
    """Preuve de bout en bout : un receveur simulé (`.claude/` copié sans `scripts/`) collecte sans erreur."""
    import shutil
    import subprocess
    import sys

    recu = tmp_path / "recv"
    (recu / ".claude" / "hooks" / "tests").mkdir(parents=True)
    for nom in ("conftest.py", "test_kata_only_marque.py"):
        shutil.copy(TESTS / nom, recu / ".claude" / "hooks" / "tests" / nom)
    marque = recu / ".claude" / "hooks" / "tests" / "test_lit_scripts.py"
    marque.write_text('# KATA-ONLY\nfrom pathlib import Path\nPath(__file__).parents[3].joinpath("scripts", "absent.py").read_text()\n',
                      encoding="utf-8")
    sortie = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                             str(recu / ".claude" / "hooks" / "tests")],
                            capture_output=True, text=True, cwd=recu, timeout=60)
    texte = sortie.stdout + sortie.stderr
    assert "FileNotFoundError" not in texte and "error" not in texte.lower().replace("0 error", ""), texte
    assert "test_lit_scripts" not in sortie.stdout, "le test marqué a été collecté chez le receveur"
