"""Ce qu'un `git` fait, lu APRÈS ses options globales, sur une liste fermée de lectures.

Constat de relecture (2026-10-26): `git -C . commit`, `git -c k=v commit`, l'alias `git ci`, `git branch -D`,
`git worktree add` et `git pull` échappaient au verrou d'écrivain. Règle: une sous-commande inconnue est un
état partagé; on n'énumère pas les gestes dangereux, on énumère les gestes inoffensifs.
"""

from __future__ import annotations

from shell_lecteur import Mot

OPTIONS_A_VALEUR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}

LECTURES = {
    "status", "log", "diff", "show", "blame", "describe", "rev-parse", "rev-list", "ls-files", "ls-tree",
    "ls-remote", "cat-file", "grep", "shortlog", "merge-base", "show-ref", "name-rev", "for-each-ref",
    "diff-tree", "diff-index", "count-objects", "check-ignore", "version", "help", "whatchanged", "show-branch",
    "fetch", "cherry", "",
}
_BRANCHES_LECTURE = {"-a", "-r", "-v", "-vv", "--list", "-l", "--show-current", "--all", "--remotes", "--verbose"}
_CONFIG_LECTURE = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin"}


_FILTRES = ("--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--sort", "--format")


def _liste_seule(args: list[str], drapeaux: set[str]) -> bool:
    """Que des drapeaux d'affichage et des filtres (`--contains HEAD`, `--sort=x`): jamais un nom à créer."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in _FILTRES:
            i += 2                                   # le filtre prend une valeur (parfois absente: `--merged`)
        elif a.startswith(tuple(f + "=" for f in _FILTRES)) or a in drapeaux:
            i += 1
        else:
            return False
    return True


def _branch(args: list[str]) -> tuple[bool, bool]:
    lecture = "-l" in args or "--list" in args or _liste_seule(args, _BRANCHES_LECTURE)   # `--list 'feat*'`
    return lecture, not lecture


def _tag(args: list[str]) -> tuple[bool, bool]:
    lecture = "-l" in args or "--list" in args or _liste_seule(args, {"-n"})   # `-l 'v*'`: le motif suit
    return lecture, not lecture


def _reflog(args: list[str]) -> tuple[bool, bool]:
    lecture = not args or args[0] == "show" or args[0].startswith("-")
    return lecture, not lecture


def _stash(args: list[str]) -> tuple[bool, bool]:
    lecture = args[:1] in (["list"], ["show"])
    return lecture, not lecture


def _worktree(args: list[str]) -> tuple[bool, bool]:
    lecture = args[:1] == ["list"]
    return lecture, not lecture


def _remote(args: list[str]) -> tuple[bool, bool]:
    return (not args or args[0] in ("-v", "--verbose", "show", "get-url")), False


def _config(args: list[str]) -> tuple[bool, bool]:
    return any(a in _CONFIG_LECTURE for a in args), False


_CLASSEURS = {"branch": _branch, "tag": _tag, "reflog": _reflog, "stash": _stash, "worktree": _worktree, "remote": _remote,
              "config": _config, "add": lambda args: (False, False)}


def classer(sous: str, args: list[str]) -> tuple[bool, bool]:
    """(lecture, partage). `partage`: change l'historique, la branche ou l'arbre qu'une autre séance utilise."""
    if sous in LECTURES:
        return True, False
    classeur = _CLASSEURS.get(sous)
    return classeur(args) if classeur else (False, True)


def lire(mots: list[Mot], cwd: str, resoudre) -> tuple[str, list[Mot], str]:
    """(sous-commande, ses arguments, dossier): `-C dir` change le dossier, `-c k=v` consomme sa valeur."""
    i = 0
    while i < len(mots) and mots[i].texte.startswith("-"):
        option = mots[i].texte
        if option in OPTIONS_A_VALEUR and i + 1 < len(mots):
            cwd = resoudre(mots[i + 1].texte, cwd) if option == "-C" else cwd
            i += 1
        i += 1
    sous = mots[i].texte if i < len(mots) else ""
    return sous, mots[i + 1:], cwd
