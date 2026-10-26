"""Les fichiers qu'un programme ÉCRIT, d'après ses arguments. Nommer un fichier n'est pas l'écrire.

`python script.py` et `pytest tests/x.py` nomment un fichier sans le toucher; seuls une redirection, `tee`,
`cp`, `mv`, `sed -i`, `touch`, `curl -o`… écrivent. Pour le code d'un interpréteur (`python -c`), on ne l'exécute
pas: ses chaînes qui ressemblent à un chemin comptent comme écrites (on sur-déclenche, jamais l'inverse).
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

_VALEURS = {   # options qui prennent une valeur séparée, par programme
    "cp": ("-t", "-S", "--target-directory", "--suffix"), "install": ("-t", "-m", "-o", "-g", "-S"),
    "ln": ("-t", "-S"), "mv": ("-t", "-S", "--target-directory", "--suffix"),
    "rsync": ("-e", "--rsh", "--exclude", "--include", "-f", "--filter", "--port"),
    "scp": ("-P", "-i", "-o", "-F", "-l", "-J", "-S", "-c"), "touch": ("-d", "-t", "-r", "-s"),
    "truncate": ("-s", "-r"),
}
_WINDOWS = {"copy", "move", "xcopy", "robocopy", "ren", "rename", "del", "erase", "set-content", "add-content",
            "out-file", "new-item", "copy-item", "move-item", "rename-item", "remove-item", "tee-object",
            "clear-content", "export-csv"}
_LITTERAL = re.compile(r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)\"""")
_JETON = re.compile(r"[\w~:.\\/-]+")


def resoudre(chemin: str, cwd: str) -> str:
    c = chemin.replace("\\", "/")
    if not cwd or c.startswith(("/", "~")) or re.match(r"[A-Za-z]:/", c):
        return c
    return posixpath.normpath(posixpath.join(cwd, c))


def debut_positionnels(args: list[str], avec_valeur: tuple = ()) -> int:
    """Index du premier argument qui n'est ni une option ni la valeur d'une option."""
    i = 0
    while i < len(args):
        if args[i] == "--":
            return i + 1
        if not args[i].startswith("-") or args[i] == "-":
            return i
        i += 2 if args[i] in avec_valeur else 1
    return len(args)


def positionnels(args: list[str], avec_valeur: tuple = ()) -> list[str]:
    """Les arguments qui ne sont pas des options, ni la valeur d'une option qui en prend une."""
    sortie, i = [], 0
    while i < len(args):
        debut = debut_positionnels(args[i:], avec_valeur)
        if debut >= len(args[i:]):
            break
        sortie.append(args[i + debut])
        i += debut + 1
    return sortie


def valeurs_d_option(args: list[str], courtes: tuple, longues: tuple = ()) -> list[str]:
    """Les valeurs données à une option: `-o f`, `-of`, `--output f`, `--output=f`."""
    sortie = []
    for i, a in enumerate(args):
        suivant = args[i + 1] if i + 1 < len(args) else None
        valeur = _valeur_collee(a, courtes, longues)
        if a in courtes or a in longues:
            valeur = suivant
        if valeur is not None:
            sortie.append(valeur)
    return sortie


def _valeur_collee(a: str, courtes: tuple, longues: tuple) -> str | None:
    """La valeur attachée à l'option: `--output=f` ou `-of`."""
    for o in longues:
        if a.startswith(o + "="):
            return a.split("=", 1)[1]
    return next((a[2:] for o in courtes if len(o) == 2 and a.startswith(o) and len(a) > 2), None)


def _ressemble_a_un_chemin(jeton: str) -> bool:
    if jeton.startswith("-") or re.fullmatch(r"[\d.]+", jeton):
        return False
    return "/" in jeton or "\\" in jeton or re.search(r"\.\w{1,8}$", jeton) is not None


def chemins_du_code(code: str, nus: bool = False) -> list[str]:
    """Les chaînes d'un code qui ressemblent à un chemin (`nus`: aussi les mots nus, pour PowerShell, awk)."""
    sources = [a or b for a, b in _LITTERAL.findall(code)]
    if nus:
        sources.append(code)
    return [j for s in sources for j in _JETON.findall(s) if _ressemble_a_un_chemin(j)]


def _destinations(destination: str, sources: list[str], cwd: str) -> list[str]:
    """`cp a docs/` écrit `docs/a`: un dossier destination reçoit le nom de chaque source."""
    if destination.endswith(("/", "\\")) or Path(resoudre(destination, cwd)).is_dir():
        return [posixpath.join(destination.replace("\\", "/"), posixpath.basename(s.rstrip("/"))) for s in sources]
    return [destination]


def _copie(prog: str, args: list[str], cwd: str) -> list[str]:
    positions = positionnels(args, _VALEURS[prog])
    cible = (valeurs_d_option(args, ("-t",), ("--target-directory",)) or [""])[0]
    if cible:
        return [cible] + _destinations(cible + "/", positions, cwd)
    if len(positions) < 2:
        return []
    sortie = _destinations(positions[-1], positions[:-1], cwd)
    return sortie + (positions[:-1] if prog == "mv" else [])


def _sed(prog: str, args: list[str], cwd: str) -> list[str]:
    sur_place = any((a.startswith("-") and not a.startswith("--") and "i" in a[1:]) or a.startswith("--in-place")
                    for a in args)
    if not sur_place:
        return []
    positions = positionnels(args, ("-e", "-f", "--expression", "--file"))
    script_en_option = any(a in ("-e", "-f", "--expression", "--file") for a in args)
    return positions if script_en_option else positions[1:]


def _windows(prog: str, args: list[str], cwd: str) -> list[str]:
    return [j for a in args for j in _JETON.findall(a) if _ressemble_a_un_chemin(j)]


_ECRIVEURS = {
    "tee": lambda prog, args, cwd: positionnels(args),
    "touch": lambda prog, args, cwd: positionnels(args, _VALEURS["touch"]),
    "truncate": lambda prog, args, cwd: positionnels(args, _VALEURS["truncate"]),
    "dd": lambda prog, args, cwd: [a[3:] for a in args if a.startswith("of=")],
    "curl": lambda prog, args, cwd: valeurs_d_option(args, ("-o",), ("--output",)),
    "wget": lambda prog, args, cwd: valeurs_d_option(args, ("-O", "-P"), ("--output-document", "--directory-prefix")),
    "sort": lambda prog, args, cwd: valeurs_d_option(args, ("-o",), ("--output",)),
    "sed": _sed,
    **{p: _copie for p in ("cp", "install", "ln", "rsync", "scp", "mv")},
    **{p: _windows for p in _WINDOWS},
}


def neutre(chemin: str) -> bool:
    """Le puits (`/dev/null`, `NUL`) ou la sortie standard (`-`): écrire là n'écrit aucun fichier."""
    return chemin.startswith("/dev/") or chemin == "-" or chemin.lower() in ("nul", "nul:", "con")


def ecrits_du_programme(prog: str, args: list[str], cwd: str) -> list[str]:
    ecriveur = _ECRIVEURS.get(prog)
    return [resoudre(x, cwd) for x in ecriveur(prog, args, cwd) if not neutre(x)] if ecriveur else []
