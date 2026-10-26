"""Les commandes connues pour n'écrire aucun fichier suivi: tests, vérifications, consultations.

Le verrou d'écrivain a besoin de la question inverse de `lecture seule`: « cette séance a-t-elle écrit? ».
Une première correction (relecture n° 3) ne comptait que les écrivains connus; la relecture n° 4 a montré que
formateurs, gestionnaires de paquets et générateurs de migrations passaient alors inaperçus. Le sens de
l'erreur est donc fixé: une liste FERMÉE d'inoffensifs, et tout le reste compte comme une écriture. Oublier un
test dans cette liste coûte un avertissement de trop; oublier un formateur dans l'autre sens coûtait un commit
qui embarque le travail d'une autre séance.
"""

from __future__ import annotations

import re

_SCRIPTS_SANS_ECRITURE = re.compile(r"test(:\S+)?|lint|typecheck|check")
_LECTURES_DOCKER = {"logs", "ps", "inspect", "images", "stats", "top", "port", "version", "info"}


def _gestionnaire(args: list[str]) -> bool:
    if "--fix" in args:
        return False                                  # `lint -- --fix` réécrit le code
    if args[:1] in (["test"], ["t"]):
        return True
    return args[:1] == ["run"] and len(args) > 1 and _SCRIPTS_SANS_ECRITURE.fullmatch(args[1]) is not None


def _docker(args: list[str]) -> bool:
    if args[:1] == ["compose"]:
        return args[1:2] in (["ps"], ["logs"], ["config"], ["ls"])
    return bool(args) and args[0] in _LECTURES_DOCKER


_TOUJOURS = {"pytest", "vitest", "jest", "playwright", "curl", "ssh", "mypy", "pyright"}   # curl: la sortie vers un fichier est jugée à part
_PREMIER_ARGUMENT = {   # programme -> premiers arguments qui ne font que tester, vérifier ou consulter
    "mix": {"test", "credo", "dialyzer", "deps.audit", "hex.audit", "sobelow"},
    "cargo": {"test", "check", "clippy", "audit"}, "go": {"test", "vet"}, "docker-compose": {"ps", "logs"},
}
_GESTIONNAIRES = {"npm", "pnpm", "yarn", "bun"}


def _module_python(args: list[str]) -> bool:
    """`python -m pytest`, `python -I -m mypy .`, `python -m ruff check .`: les options avant `-m` ne changent rien."""
    if "-m" not in args or args.index("-m") + 1 >= len(args):
        return False
    if not all(a.startswith("-") for a in args[:args.index("-m")]):
        return False                                   # `python script.py -m pytest`: -m est un argument du script
    module, reste = args[args.index("-m") + 1], args[args.index("-m") + 2:]
    return module in ("pytest", "mypy", "pyright") or (module == "ruff" and reste[:1] == ["check"] and "--fix" not in reste)


def inoffensif(prog: str, args: list[str]) -> bool:
    premier = args[0] if args else ""
    if prog in _TOUJOURS:
        return True
    if prog in ("npx", "pnpx"):
        return bool(args) and inoffensif(args[0], args[1:])   # l'outil lancé juge: `npx tsc --noEmit`, `npx vitest`
    if prog in _PREMIER_ARGUMENT:
        return premier in _PREMIER_ARGUMENT[prog]
    if prog in _GESTIONNAIRES:
        return _gestionnaire(args)
    if prog == "tsc":
        return "--noEmit" in args                      # sans cela, tsc produit des .js
    if prog == "docker":
        return _docker(args) or premier == "exec"     # `exec`: ce qui s'y passe est distant
    if prog == "python":
        return _module_python(args)
    return prog == "ruff" and premier == "check" and "--fix" not in args
