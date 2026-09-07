#!/usr/bin/env python3
"""Les notes globales de Jay remontent au demarrage, dans Takumi — SessionStart.

POURQUOI IL EXISTE. Le 2026-09-07, en rangeant les reserves de propagation, j'ai
ouvert `Shinzo/08-Notes/inbox.md` et y ai trouve des idees ecrites par Jay et
jamais traitees. `/session-start` lit quatre fichiers de Shinzo, tous lies a UN
projet ; celui-la n'en fait pas partie, donc personne ne l'ouvrait. Le canal
existait, son lecteur manquait — la meme famille que les trois controles
orphelins du 2026-09-06.

OU, ET POURQUOI LA. Choix de Jay le meme jour : ces notes remontent dans le depot
**Takumi**, « c'est avec lui que je brainstorm ou fais tout ce qui n'est pas
forcement specifique a un projet, ou qui en touche plusieurs ». Ailleurs, elles
seraient du bruit — et un signal qui parle partout finit par n'etre lu nulle part.

CE QU'IL DIT, ET CE QU'IL NE DIT PAS. Il signale que des notes attendent, et ou
les lire. Il ne les resume pas, ne les trie pas, n'en deduit aucune tache : ce
sont les mots de Jay, ils se lisent entiers. Il parle une fois par jour tant que
la note n'a pas bouge : repeter a chaque demarrage apprend a ne plus lire les
lignes de demarrage, mais se taire pour toujours perd le signal quand Jay ferme
la fenetre sans avoir lu (mesure du 2026-09-07).

Il ne bloque jamais. Shinzo peut ne pas etre clone ; une note absente est une
note vide, jamais une erreur.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # type: ignore # noqa: E402

DEPOT_PORTEUR = "Takumi"
CHEMIN_NOTES = ("Shinzo", "08-Notes", "inbox.md")
# Le gabarit du fichier vide, mot pour mot. Une inbox qui ne porte que sa propre
# phrase d'accueil n'a rien a trier.
VIDE = "(Inbox vide"


def notes_globales(racine: Path) -> Path:
    """Shinzo vit en frere de l'atelier, jamais dans le depot courant."""
    return Path(racine).parent.joinpath(*CHEMIN_NOTES)


def _ardoise(racine: Path) -> Path:
    return Path(racine) / ".claude" / "state" / "notes-globales-vues"


def _substance(texte: str) -> str:
    """Ce que Jay a ecrit, sans l'en-tete ni le gabarit du fichier.

    Sans ce tri, la simple presence du mode d'emploi ferait signaler une inbox
    vide a chaque changement de gabarit.
    """
    lignes = [
        ligne.strip()
        for ligne in texte.splitlines()
        if ligne.strip()
        and not ligne.startswith(("#", ">", "---", "*("))
        and VIDE not in ligne
    ]
    return "\n".join(lignes)


def _depot_principal(racine: Path) -> str:
    """Le nom du depot, demande a GIT et non deduit du dossier.

    Depuis un worktree, `--git-common-dir` rend le `.git` du depot principal :
    son dossier parent porte le vrai nom. Mesure du 2026-09-07 sur un worktree
    reel cree pour l'occasion — dossier `NomQuelconque`, depot principal `Kata`.
    """
    try:
        sortie = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(racine), capture_output=True, text=True, check=False)
    except OSError:
        return ""
    commun = sortie.stdout.strip()
    if sortie.returncode != 0 or not commun:
        return ""
    return (Path(racine) / commun).resolve().parent.name if commun == ".git" \
        else Path(commun).resolve().parent.name


def _est_le_depot_porteur(racine: Path) -> bool:
    """Sommes-nous dans Takumi — ou dans l'un de ses worktrees, quel que soit son nom ?

    TROIS VERSIONS EN DEUX JOURS, deux defauts opposes, un troisieme evite.
    La comparaison stricte rendait le hook muet EN SILENCE sur `takumi` et
    `TAKUMI` (Windows ignore la casse). Le prefixe ouvert qui l'a remplacee
    faisait parler `TakumiTools`, donc AFFICHAIT LES NOTES PRIVEES DE JAY dans
    un depot sans rapport. La liste fermee qui a suivi reposait sur une
    hypothese que je n'avais jamais mesuree — « git nomme ses worktrees
    `<depot>-worktree-...` ». Faux : `git worktree add` prend le nom que
    l'humain lui donne, et n'impose RIEN. `Takumi-review-pr42` serait reste
    muet.

    On ne devine donc plus le nom : on le DEMANDE a git, qui sait relier un
    worktree a son depot principal. Le nom du dossier ne sert que de repli quand
    git ne repond pas.
    """
    porteur = DEPOT_PORTEUR.lower()
    principal = _depot_principal(racine).lower()
    return (principal or Path(racine).name.lower()) == porteur


def aujourdhui() -> str:
    return date.today().isoformat()


def _deja_dit_aujourdhui(racine: Path, substance: str) -> bool:
    """A-t-on deja signale CE texte AUJOURD'HUI ? Et retient la reponse.

    L'ardoise retient ce qu'on a dit ET quand. Mesure du 2026-09-07, relecture
    croisee : ne retenir que le contenu taisait le signal POUR TOUJOURS des lors
    que Jay fermait la fenetre sans avoir lu. Ses notes attendaient deja depuis
    des semaines ; les taire apres une seule ligne serait le meme defaut, en
    pire. Un jour est la bonne maille — assez rare pour ne pas lasser, assez
    frequent pour qu'un oubli ne devienne pas une perte.
    """
    marque = f"{hashlib.sha256(substance.encode('utf-8')).hexdigest()}|{aujourdhui()}"
    ardoise = _ardoise(racine)
    try:
        if ardoise.is_file() and ardoise.read_text(encoding="utf-8").strip() == marque:
            return True
        ardoise.parent.mkdir(parents=True, exist_ok=True)
        ardoise.write_text(marque, encoding="utf-8")
    except OSError:
        # Une ardoise impossible fait repeter le signal, jamais taire une note.
        pass
    return False


def rapport(racine: Path) -> str:
    """Le texte a afficher, ou vide. Retient ce qui a ete vu."""
    racine = Path(racine)
    if not _est_le_depot_porteur(racine):
        return ""
    fichier = notes_globales(racine)
    try:
        substance = _substance(fichier.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return ""
    if not substance:
        return ""

    if _deja_dit_aujourdhui(racine, substance):
        return ""

    lignes = len(substance.splitlines())
    return (
        f"[NOTES] Jay a laisse {lignes} ligne(s) non traitees dans ses notes globales.\n"
        f"  A lire en entier : {fichier.as_posix()}\n"
        "  Ce sont ses mots — ils se lisent, ils ne se resument pas."
    )


def main() -> None:
    try:
        texte = rapport(find_repo_root())
    except Exception as erreur:  # un signal casse ne doit jamais retenir une session
        print(f"[NOTES] notes globales indisponibles ({erreur}).", file=sys.stderr)
        sys.exit(0)
    if texte:
        print(texte, file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
