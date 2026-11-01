#!/usr/bin/env python3
"""Le CDC se lit avant la première écriture de code — PreToolUse(Write|Edit). AVERTIT, ne bloque pas.

Sur le modèle de `obsidian-mandatory-read.py` (qui bloque pour la fiche de projet), mais en rappel : à la première
écriture de code source de la séance, si le projet a un cahier des charges (`docs/CDC.md` ou `docs/CDC/`) et que
la séance ne l'a pas lu (outil Read), un rappel nomme les fichiers. Une fois par séance.

Pourquoi (Jay, 2026-11-01) : l'autonomie fait des bêtises quand le contexte manque. Le code forçait la lecture de
la fiche, jamais celle du CDC. Pas de blocage : un correctif d'une ligne n'exige pas tout le CDC.

Limites écrites : (1) un projet sans CDC n'est pas signalé ici (c'est un manque de conception, mesuré ailleurs) ;
(2) seule une lecture par l'outil Read compte, un `cat` ne la prouve pas ; (3) une lecture avant une compaction du
contexte reste comptée alors que le modèle l'a peut-être perdue.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    find_repo_root,
    format_warn,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once  # noqa: E402
from transcript_reader import iter_tool_calls  # noqa: E402
from veille_detect import needs_evidence  # noqa: E402


def est_du_code(chemin: str) -> bool:
    """Du code source du projet : même définition que la porte de veille (hors tests, docs, méthode)."""
    norm = (chemin or "").replace("\\", "/")
    nom = norm.rsplit("/", 1)[-1]
    ext = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    return needs_evidence(norm, nom, ext)


def cdc_du_projet(racine: Path) -> list[Path]:
    """Les fichiers du cahier des charges : `docs/CDC*.md` (CDC.md, CDC-P0.md, CDC-Hibiki-v6.md…) et `docs/CDC/**/*.md`."""
    docs = racine / "docs"
    dossier = docs / "CDC"
    fichiers = sorted(p for p in docs.glob("CDC*.md") if p.is_file()) if docs.is_dir() else []
    if dossier.is_dir():
        fichiers += sorted(p for p in dossier.rglob("*.md") if p.is_file())
    return fichiers


def _norm(chemin: str | Path) -> str:
    return str(chemin).replace("\\", "/").rstrip("/").lower()


def _est_un_fichier_du_cdc(chemin: str, racines_n: list[str]) -> bool:
    """Un chemin (normalisé) du CDC, dans l'une des racines du projet."""
    if not chemin or not any(chemin.startswith(r) for r in racines_n):
        return False
    if "/docs/cdc/" in chemin:
        return True
    dossier, _, nom = chemin.rpartition("/")
    return dossier.endswith("/docs") and nom.startswith("cdc") and nom.endswith(".md")


def cdc_lu(transcript: str, cdc: list[Path], racines: list[Path]) -> bool:
    """Vrai si la séance a lu (outil Read) un fichier du CDC, dans ce projet et pas dans un autre."""
    if not transcript or not cdc:
        return False
    racines_n = [_norm(r) + "/" for r in racines]
    try:
        chemins = (_norm((a.get("input") or {}).get("file_path") or "") for a in iter_tool_calls(transcript, "Read"))
        return any(_est_un_fichier_du_cdc(c, racines_n) for c in chemins)
    except Exception:
        return False


def message(cdc: list[Path]) -> str:
    noms = ", ".join(str(p) for p in cdc[:4]) + (f" (+{len(cdc) - 4})" if len(cdc) > 4 else "")
    return (f"tu écris du code sans avoir lu le cahier des charges de ce projet dans cette séance. "
            f"Lis-le (outil Read) avant d'aller plus loin : {noms}")


def _racines(repo: Path) -> list[Path]:
    """La copie de travail et, dans un worktree, le dépôt principal (le CDC y est lu aussi)."""
    racines = [repo]
    try:
        sortie = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
                                capture_output=True, text=True, timeout=5)
        commun = Path(sortie.stdout.strip())
        if sortie.returncode == 0 and sortie.stdout.strip():
            principal = (commun if commun.is_absolute() else repo / commun).resolve().parent
            if principal != repo.resolve():
                racines.append(principal)
    except (OSError, subprocess.SubprocessError):
        pass
    return racines


def main() -> None:
    _, data = read_hook_input()
    if not est_du_code(get_file_path(data)):
        pass_through()
    repo = find_repo_root()
    cdc = cdc_du_projet(repo)
    if not cdc:
        pass_through()
    session = data.get("session_id", "") or "no-session"
    if cdc_lu(data.get("transcript_path", ""), cdc, _racines(repo)):
        pass_through()
    if mark_once("cdc-read-before-code", "rappel", session_id=session):
        warn(format_warn(
            "CDC non lu avant la première écriture de code",
            message(cdc),
            reference="Shinzo/02-Projets/_Index.md (le CDC se lit avant de coder, Jay 2026-11-01)",
        ))
    pass_through()


if __name__ == "__main__":
    main()
