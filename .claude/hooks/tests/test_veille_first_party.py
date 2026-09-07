"""Un module qui vit dans ce depot n'est pas une dependance.

Ne 2026-09-06. Le garde-fou de veille a refuse l'ecriture d'un script parce
qu'il importait `propagate_lib` — un paquet qui vit dans `scripts/` de ce depot,
deja importe par `scripts/check-receivers-park.py`. Il reclamait une recherche
web sur un registre public pour un module maison.

La preuve que le defaut est reel et pas theorique : le garde-fou lui-meme
importe cinq modules maison (`common`, `session_state`, `veille_config`,
`veille_detect`, `veille_markers`). Reecrit aujourd'hui, il se serait bloque
lui-meme.

Ce qui ne doit PAS bouger : un vrai ajout de dependance externe reste sensible.
Un garde-fou qu'on assouplit trop ne garde plus rien.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import pytest  # noqa: E402
import veille_detect  # noqa: E402

# `propagate_lib` vit dans `scripts/`, qui ne voyage pas. Les trois cas qui le
# nomment ne disent donc vrai que dans Kata ; chez un receveur ils rougissent sur
# un paquet absent et bloquent toute la propagation (mesure du 2026-09-07, 30
# depots arretes). La regle elle-meme — un module maison n'est pas une dependance
# — reste eprouvee partout par les cas voisins, qui ne citent aucun paquet local.
DANS_KATA = (RACINE / "scripts" / "propagate-methodology.py").is_file()
kata_seulement = pytest.mark.skipif(
    not DANS_KATA, reason="`propagate_lib` ne vit que dans Kata")


# --- ce qui vit dans le depot ----------------------------------------------

@kata_seulement
def test_a_package_of_this_repository_is_first_party():
    maison = veille_detect.first_party_modules(RACINE)
    assert "propagate_lib" in maison


def test_a_helper_module_of_the_hooks_is_first_party():
    maison = veille_detect.first_party_modules(RACINE)
    assert "common" in maison
    assert "veille_config" in maison


def test_a_module_that_lives_nowhere_here_is_not_first_party():
    maison = veille_detect.first_party_modules(RACINE)
    assert "requests" not in maison
    assert "httpx" not in maison


# --- le verdict -------------------------------------------------------------

def _verdict(nouveau: str, chemin: str | None = None) -> str | None:
    chemin = chemin or str(RACINE / "scripts" / "essai.py")
    return veille_detect.sensitive_change(chemin, "essai.py", "py", "", nouveau)


@kata_seulement
def test_importing_a_repository_module_is_not_a_dependency_change():
    assert _verdict("from propagate_lib.projects import PROJECTS\n") is None


def test_importing_a_real_external_package_stays_sensitive():
    motif = _verdict("import requests\n")
    assert motif is not None
    assert "requests" in motif


@kata_seulement
def test_a_mixed_import_names_only_the_external_one():
    motif = _verdict("from propagate_lib.projects import PROJECTS\nimport httpx\n")
    assert motif is not None
    assert "httpx" in motif
    assert "propagate_lib" not in motif


def test_the_standard_library_stays_silent():
    assert _verdict("import json\nfrom pathlib import Path\n") is None


# --- la regression qui prouve le defaut -------------------------------------

def test_the_veille_guard_itself_would_no_longer_block_its_own_rewrite():
    garde = RACINE / ".claude/hooks/guards/pre-code-veille-check.py"
    texte = garde.read_text(encoding="utf-8", errors="replace")
    assert veille_detect.sensitive_change(str(garde), garde.name, "py", "", texte) is None


# --- hors du depot, on reste prudent ----------------------------------------

def test_a_file_outside_any_repository_keeps_the_strict_verdict(tmp_path):
    dehors = tmp_path / "ailleurs.py"
    motif = veille_detect.sensitive_change(
        str(dehors), "ailleurs.py", "py", "", "import propagate_lib\n")
    assert motif is not None


# --- le defaut trouve par la relecture independante du 2026-09-06 -----------
# VERDICT FAIL, defaut BLOQUANT : la liste des dossiers ignores ne connaissait
# que « venv », « env » et « .venv » a l'exact. Un environnement nomme
# `venv311`, `.tox` ou un `site-packages` vendorise laissait chaque paquet
# installe se declarer maison — donc `import stripe` ne demandait plus de
# veille. J'avais affaibli un garde-fou bloquant en croyant reparer un faux
# positif.

def _depot_avec_env(tmp_path, dossier_env: str):
    (tmp_path / ".git").mkdir()
    paquet = tmp_path / dossier_env / "Lib" / "site-packages" / "stripe"
    paquet.mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    source = tmp_path / "src"
    source.mkdir()
    return source / "app.py"


def test_a_package_installed_in_a_virtualenv_is_not_ours(tmp_path):
    cible = _depot_avec_env(tmp_path, "venv311")
    motif = veille_detect.sensitive_change(str(cible), "app.py", "py", "", "import stripe\n")
    assert motif is not None and "stripe" in motif


def test_every_shape_of_environment_directory_is_ignored(tmp_path):
    for nom in ("venv", ".venv", "venv313", ".tox", "virtualenv", "env"):
        dossier = tmp_path / nom
        dossier.mkdir()
        paquet = dossier / "requests"
        paquet.mkdir()
        (paquet / "__init__.py").write_text("", encoding="utf-8")
    veille_detect._FIRST_PARTY_CACHE.clear()
    assert "requests" not in veille_detect.first_party_modules(tmp_path)


def test_a_vendored_site_packages_anywhere_is_ignored(tmp_path):
    paquet = tmp_path / "vendor" / "site-packages" / "httpx"
    paquet.mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    veille_detect._FIRST_PARTY_CACHE.clear()
    assert "httpx" not in veille_detect.first_party_modules(tmp_path)


def test_a_backup_of_a_source_directory_is_not_a_source_directory(tmp_path):
    # `scripts-backup/boto3.py` faisait passer boto3 pour un module maison :
    # la comparaison se faisait sur un prefixe de chaine, pas sur un chemin.
    sauvegarde = tmp_path / "scripts-backup"
    sauvegarde.mkdir()
    (sauvegarde / "boto3.py").write_text("", encoding="utf-8")
    veille_detect._FIRST_PARTY_CACHE.clear()
    assert "boto3" not in veille_detect.first_party_modules(tmp_path)


def test_our_real_scripts_directory_still_counts(tmp_path):
    vrai = tmp_path / "scripts"
    vrai.mkdir()
    (vrai / "mon_module.py").write_text("", encoding="utf-8")
    veille_detect._FIRST_PARTY_CACHE.clear()
    assert "mon_module" in veille_detect.first_party_modules(tmp_path)
