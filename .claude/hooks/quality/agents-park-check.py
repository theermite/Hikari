#!/usr/bin/env python3
"""Refuse un commit qui fait deriver le parc d'experts — PreToolUse Bash.

Ne 2026-09-06. `scripts/check-agents-park.py` existait, rendait vert, et n'etait
branche sur AUCUN evenement. Troisieme cas de la meme famille dans la meme
soiree, avec le sommaire de memoire et le controle du conseil : un point du plan
declare « livre » repose sur un controle que personne ne lance.

Un controle qu'on lance a la main ferme un cas. Un controle branche ferme la
famille — il ne demande pas si on a pense a lui.

Le partage est celui du controle des faits, avec une PORTE devant :
  - le commit ne touche aucun expert               -> on ne mesure meme pas
  - un probleme sur un expert QU'ON MET EN COMMIT  -> refuse
  - un probleme ailleurs, quand on touche un expert -> avertit

La premiere ligne est le prix a payer : mesurer le parc a chaque commit
couterait a tout le monde pour un signal que personne n'a demande. Une derive
lointaine attend donc le prochain commit qui touche un expert. L'en-tete disait
« un probleme ailleurs avertit » sans cette reserve — contre-relecture du
2026-09-06, meme famille que le defaut qu'elle corrigeait.

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

# Les archives comptent : ces experts sont destines a etre reveilles, et une
# derive rangee dans un tiroir reste une derive.
DOSSIERS_EXPERTS = (".claude/agents/", ".claude/agents-archive/")


def is_git_commit(command: str) -> bool:
    if not command or LECTURE_PATTERN.search(command):
        return False
    return bool(COMMIT_PATTERN.search(command))


def experts_en_commit(fichiers: list[str]) -> list[str]:
    vises = []
    for fichier in fichiers:
        normalise = fichier.replace("\\", "/")
        if normalise.endswith(".md") and normalise.startswith(DOSSIERS_EXPERTS):
            vises.append(normalise)
    return vises


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


def problemes_du_parc(repo_root: Path) -> list[str]:
    """Les problemes que le controle du parc trouve, ou une liste vide."""
    chemin = Path(repo_root) / "scripts" / "check-agents-park.py"
    spec = importlib.util.spec_from_file_location("check_agents_park", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_agents_park"] = module
    spec.loader.exec_module(module)
    return list(module.check_park(module.PARK, module.OTHER_DIRS))


def partager(problemes: list[str], en_commit: list[str]) -> tuple[list[str], list[str]]:
    """Separe ce qui refuse de ce qui avertit.

    Defaut trouve par la relecture independante du 2026-09-06 : ce fichier
    PROMETTAIT ce partage dans son en-tete et ne le faisait pas. Il bloquait sur
    tout le parc, donc un commit ajoutant un expert conforme etait refuse a cause
    d'un fichier qu'il ne touche pas. Un texte qui decrit un comportement que le
    code contredit — la famille meme fermee cette soiree-la.

    Chaque probleme commence par le nom de l'expert suivi de « : ». Quand ce nom
    ne se lit pas, on avertit : on n'accuse pas un commit sur un doute.
    """
    vises = {Path(chemin.replace("\\", "/")).stem for chemin in en_commit}
    refuses, avertis = [], []
    for probleme in problemes:
        nom = probleme.split(" : ", 1)[0].strip() if " : " in probleme else ""
        (refuses if nom and nom in vises else avertis).append(probleme)
    return refuses, avertis


def message(problemes: list[str]) -> str:
    lignes = ["Le parc d'experts a derive :"]
    lignes += [f"  - {probleme}" for probleme in problemes[:10]]
    if len(problemes) > 10:
        lignes.append(f"  ... et {len(problemes) - 10} autre(s)")
    lignes.append("RECOVERY: reparer l'en-tete de l'expert, ou son appelant. "
                  "Detail : python scripts/check-agents-park.py")
    return "\n".join(lignes)


def main() -> None:
    _, data = read_hook_input()
    if not is_git_commit(get_command(data)):
        pass_through()

    repo_root = find_repo_root()
    en_commit = experts_en_commit(fichiers_en_commit(repo_root))
    if not en_commit:
        pass_through()

    try:
        problemes = problemes_du_parc(repo_root)
    except FileNotFoundError:
        # Le controle vit dans `scripts/`, qui n'est PAS propage : chez un
        # receveur il est absent. Se taire, plutot qu'avertir a chaque commit
        # dans 32 depots — une alarme quotidienne sans action possible apprend a
        # ignorer les alarmes (relecture independante, 2026-09-06).
        sys.exit(0)
    except Exception as erreur:  # le controle est la mais casse : on le DIT
        warn(f"WARNING: controle du parc indisponible ({erreur}). "
             "Lancer `python scripts/check-agents-park.py` a la main.")
        sys.exit(0)

    refuses, avertis = partager(problemes, en_commit)
    if refuses:
        block("BLOCKED: " + message(refuses))
    if avertis:
        warn("WARNING: derive ailleurs dans le parc, non bloquante.\n" + message(avertis))
    pass_through()


if __name__ == "__main__":
    main()
