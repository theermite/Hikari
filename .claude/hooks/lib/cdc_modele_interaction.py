"""Le CDC d'un projet avec interface porte une section « Modèle d'interaction » (Jay, 2026-11-01).

Ton, états vides et erreurs, adaptation neurodivergente, parcours principal : c'est le goût de Jay, donc le code
COMPTE les manques et ne les remplit jamais. Consommateur : `scripts/garde-methode.py` (entretien hebdomadaire).

Limite écrite : « a une interface » se lit à une dépendance (React, Next, Vue, Svelte, Electron, Tauri, PySide, PyQt)
dans un `package.json` / `pyproject.toml` / `requirements*.txt` à la racine, un niveau plus bas, ou sous `apps/*` et `packages/*` ; une interface
écrite autrement (Kotlin, LiveView seul) n'est pas vue.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_DEPENDANCES_JS = ("react", "next", "vue", "svelte", "electron", "@tauri-apps/api", "solid-js")
_CLES_JS = ("dependencies", "devDependencies", "peerDependencies")
_PY_RE = re.compile(r"pyside\d?|pyqt\d?", re.IGNORECASE)
_TITRE_RE = re.compile(r"^#{1,6}[ \t]+.*mod[eè]le d['’]interaction", re.IGNORECASE | re.MULTILINE)


def _package_json_ui(fichier: Path) -> bool:
    try:
        donnees = json.loads(fichier.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return False
    if not isinstance(donnees, dict):
        return False
    noms = {n for cle in _CLES_JS for n in (donnees.get(cle) or {}) if isinstance(donnees.get(cle), dict)}
    return any(d in noms for d in _DEPENDANCES_JS)


def _python_ui(fichier: Path) -> bool:
    try:
        return bool(_PY_RE.search(fichier.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def _dossiers_a_lire(racine: Path) -> list[Path]:
    """La racine, ses sous-dossiers, et ceux de `apps/` et `packages/` (monorepos)."""
    if not racine.is_dir():
        return []
    ignores = (".", "node_modules")
    premiers = [d for d in racine.iterdir() if d.is_dir() and not d.name.startswith(ignores)]
    monorepo = [s for d in premiers if d.name in ("apps", "packages") for s in d.iterdir() if s.is_dir()]
    return [racine, *premiers, *monorepo]


def a_une_interface(racine: Path) -> bool:
    for dossier in _dossiers_a_lire(racine):
        if (dossier / "package.json").is_file() and _package_json_ui(dossier / "package.json"):
            return True
        pythons = [dossier / "pyproject.toml", *dossier.glob("requirements*.txt")]
        if any(f.is_file() and _python_ui(f) for f in pythons):
            return True
    return False


def fichiers_cdc(racine: Path) -> list[Path]:
    docs = racine / "docs"
    if not docs.is_dir():
        return []
    return sorted([*docs.glob("CDC*.md"), *(docs / "CDC").rglob("*.md")]) if (docs / "CDC").is_dir() \
        else sorted(docs.glob("CDC*.md"))


def a_la_section(racine: Path) -> bool:
    for f in fichiers_cdc(racine):
        try:
            if _TITRE_RE.search(f.read_text(encoding="utf-8", errors="replace")):
                return True
        except OSError:
            continue
    return False


def manquants(projets: list[str], dossier: Path) -> list[str]:
    """Projets avec interface ET un CDC, mais sans section « Modèle d'interaction »."""
    return [n for n in projets
            if (dossier / n).is_dir() and fichiers_cdc(dossier / n) and a_une_interface(dossier / n)
            and not a_la_section(dossier / n)]
