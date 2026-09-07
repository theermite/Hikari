#!/usr/bin/env python3
"""Refuse un commit qui emporte un fait faux sur nous-memes — PreToolUse Bash.

Ne 2026-09-06. Sept faits faux vivaient dans des documents lus a chaque session :
601 souvenirs pour 604, 60 garde-fous pour 63, 16 regles pour 17, un inventaire
de 79 composants pour 149. Six des sept etaient calculables par une commande.

La cause n'etait pas l'absence de controle : `scripts/check-doc-facts.py` peut
tous les recalculer. La cause est qu'AUCUN controle de cette famille n'etait
branche sur un evenement — ni le parc d'experts, ni le sommaire de memoire, ni
les chiffres du conseil. Un controle que rien n'execute ne garde rien.

Le partage, choisi pour survivre :
  - un fait faux dans un document QU'ON MET EN COMMIT  -> refuse
  - un fait faux ailleurs                              -> avertit

CE QUE CE GARDE-FOU N'ATTRAPE PAS, et c'est assume : un commit qui ne porte
aucun document ne declenche rien. Or brancher un hook change `settings.json` et
un `.py`, donc « 63 garde-fous » devient faux sans qu'aucun commit ne le voie.
C'est un RETARD, pas une perte — le prochain commit portant un `.md` le dira.
L'echange : 0,7 s au lieu de 5,67 s sur chaque commit (mesure du 2026-09-06). Un
garde-fou lent finit debranche, et il emporte la vraie detection avec lui.

Bloquer sur une derive lointaine ferait echouer des commits sans rapport, et le
garde-fou finirait debranche — il emporterait la vraie detection avec lui.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import block, find_repo_root, get_command, pass_through, read_hook_input, warn  # type: ignore # noqa: E402

COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)
LECTURE_PATTERN = re.compile(r"\bgit\s+(log|status|diff|show)\b", re.IGNORECASE)


def is_git_commit(command: str) -> bool:
    if not command or LECTURE_PATTERN.search(command):
        return False
    return bool(COMMIT_PATTERN.search(command))


def fichiers_en_commit(repo_root: Path) -> list[str]:
    try:
        resultat = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if resultat.returncode != 0:
        return []
    return [ligne.strip() for ligne in resultat.stdout.splitlines() if ligne.strip()]


def partager(ecarts, en_commit: list[str], repo_root: Path):
    """Separe ce qui refuse de ce qui avertit."""
    vises = {c.replace("\\", "/") for c in en_commit}
    refuses, avertis = [], []
    for ecart in ecarts:
        try:
            relatif = Path(ecart.fichier).resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            avertis.append(ecart)
            continue
        (refuses if relatif.as_posix() in vises else avertis).append(ecart)
    return refuses, avertis


def _ligne(ecart, repo_root: Path) -> str:
    try:
        ou = Path(ecart.fichier).resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        ou = str(ecart.fichier)
    return f"  {ou}:{ecart.ligne} · {ecart.fait} · ecrit {ecart.ecrit} · reel {ecart.reel}"


def message(refuses, avertis, repo_root: Path | None = None) -> str:
    repo_root = repo_root or Path.cwd()
    morceaux = []
    if refuses:
        morceaux.append("Fait(s) faux dans un document de ce commit :")
        morceaux += [_ligne(e, repo_root) for e in refuses]
    if avertis:
        morceaux.append(f"Ailleurs dans le depot ({len(avertis)}, non bloquant) :")
        morceaux += [_ligne(e, repo_root) for e in avertis[:5]]
    morceaux.append(
        "RECOVERY: corriger le chiffre, ou dater la ligne avec "
        "<!-- photo: AAAA-MM-JJ --> si c'est un instantane historique. "
        "Detail : python scripts/check-doc-facts.py"
    )
    return "\n".join(morceaux)


def _controle(repo_root: Path):
    chemin = repo_root / "scripts" / "check-doc-facts.py"
    spec = importlib.util.spec_from_file_location("check_doc_facts", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_facts"] = module
    spec.loader.exec_module(module)
    return module


def _mesurer(repo_root: Path):
    """Les ecarts, ou une sortie propre quand le controle n'est pas la."""
    try:
        controle = _controle(repo_root)
        valeurs, injoignables = controle.valeurs_reelles(controle.FAITS, repo_root)
        if injoignables:
            # Le controle dit « une source injoignable est DITE ». Le hook la
            # jetait (`valeurs, _`) : sans Shinzo clone, les faits de memoire
            # devenaient muets et le calcul se faisait sur un dictionnaire
            # partiel, en silence. Contre-relecture du 2026-09-06.
            warn("WARNING: faits non verifies faute de source : "
                 + ", ".join(injoignables))
        return controle.ecarts(controle.FAITS, controle.documents_vivants(repo_root), valeurs)
    except FileNotFoundError:
        # Le controle vit dans `scripts/`, qui n'est PAS propage : chez un
        # receveur il est absent. Se taire plutot qu'avertir a chaque commit
        # dans 32 depots — une alarme quotidienne sans action possible apprend a
        # ignorer les alarmes (relecture independante, 2026-09-06).
        sys.exit(0)
    except Exception as erreur:  # le controle est la mais casse : on le DIT
        warn(f"WARNING: controle des faits indisponible ({erreur}). "
             "Lancer `python scripts/check-doc-facts.py` a la main.")
        sys.exit(0)


def main() -> None:
    _, data = read_hook_input()
    if not is_git_commit(get_command(data)):
        pass_through()

    repo_root = find_repo_root()
    en_commit = [f for f in fichiers_en_commit(repo_root) if f.endswith(".md")]
    # Aucun document dans ce commit : rien a verifier, et le balayage coute
    # plusieurs secondes. Mesure de la relecture independante du 2026-09-06 :
    # 5,67 s sur CHAQUE commit, contre les ~2 s annoncees. Un garde-fou lent
    # finit debranche, et il emporte la vraie detection avec lui.
    if not en_commit:
        pass_through()

    ecarts = _mesurer(repo_root)

    refuses, avertis = partager(ecarts, en_commit, repo_root)
    if refuses:
        block("BLOCKED: " + message(refuses, avertis, repo_root))
    if avertis:
        warn("WARNING: " + message([], avertis, repo_root))
    pass_through()


if __name__ == "__main__":
    main()
