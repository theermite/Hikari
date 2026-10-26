"""Les commandes connues pour RÉÉCRIRE des fichiers SUIVIS: formateurs, gestionnaires de paquets, migrations.

Deux niveaux pour le verrou d'écrivain (relectures n° 4 à n° 6, 2026-10-26, FAIL en sens contraires):

- écriture CERTAINE (cette liste, plus redirections, `cp`, gestes git…): peut faire refuser le commit d'une autre séance;
- écriture POSSIBLE (toute commande ni lecture ni inoffensive connue): avertit seulement.

Une seule liste fermée ne peut pas tenir les deux erreurs: un oubli dans une liste d'inoffensifs REFUSE le commit
de l'autre séance; un oubli dans une liste d'écrivains laisse un commit embarquer son travail. Ici un oubli ne
coûte que l'avertissement. Seul ce qui réécrit un fichier SUIVI est certain: installer dans `node_modules`, `.venv`
ou `site-packages` (`npm ci`, `pip install`, `uv sync --locked`) n'écrit rien que git suive — c'est « possible ».
"""

from __future__ import annotations

import re

_GESTIONNAIRES = {"npm", "pnpm", "yarn", "bun"}
_GESTION_ECRIT = {"add", "install", "i", "remove", "rm", "uninstall", "update", "up", "dedupe", "link", "init",
                  "create", "upgrade"}
_INSTALLATION = {"install", "i", "sync"}                       # réécrivent le fichier de verrouillage, sauf figé
_FIGE = {"--frozen-lockfile", "--locked", "--frozen", "--immutable", "--ci"}
_SCRIPT_ECRIT = re.compile(r"(?:.*[:_-])?(?:format|fix)(?:[:_-].*)?")   # `migrate`: base de données, aucun fichier suivi
_SCRIPT_VERIFIE = re.compile(r".*(?:check|diff|dry).*")
_VERIFIE = {"--check", "--check-formatted", "--check-only", "--diff", "--dry-run", "-n", "-c", "-l", "-d"}
_PREMIER_ECRIT = {   # programme -> sous-commandes qui réécrivent un fichier suivi
    "mix": {"deps.get", "deps.update", "ecto.gen.migration", "new", "phx.new", "phx.gen.html", "phx.gen.live",
            "phx.gen.schema", "phx.gen.context", "phx.gen.auth", "deps.unlock"},
    "cargo": {"add", "remove", "update", "new", "init", "generate-lockfile"},
    "uv": {"add", "remove", "lock", "init"}, "poetry": {"add", "remove", "update", "lock"},
    "alembic": {"revision"},
}
_OPTION_ECRIT = {   # outil -> options qui font écrire (sans elles, l'outil affiche ou vérifie seulement)
    "prettier": {"--write", "-w"}, "eslint": {"--fix"}, "biome": {"--write", "--apply"}, "stylelint": {"--fix"},
    "gofmt": {"-w"}, "autopep8": {"-i", "--in-place"},
}
_FORMATEURS = {"black", "isort"}                        # écrivent sauf avec une option de vérification


def _fmt_du_langage(prog: str, args: list[str]) -> bool:
    """`ruff format`, `ruff check --fix`, `mix format`, `cargo fmt`, `cargo clippy --fix`: sauf option de vérification."""
    sous = {"ruff": ("format",), "mix": ("format",), "cargo": ("fmt",)}.get(prog)
    if sous is None:
        return False
    return (args[:1] == list(sous) or "--fix" in args) and not (_VERIFIE & set(args))


def _reecrit_le_code(prog: str, args: list[str]) -> bool:
    if prog in _OPTION_ECRIT:
        return bool(_OPTION_ECRIT[prog] & set(args))
    if prog in _FORMATEURS:
        return not (_VERIFIE & set(args))
    return _fmt_du_langage(prog, args)


def _outil_lance(prog: str, args: list[str]) -> bool:
    """`npx prettier --write`, `pnpm exec prettier --write`, `pnpm dlx create-vite`: l'outil lancé juge."""
    outil = args[1:] if prog in _GESTIONNAIRES else args
    if not outil:
        return False
    return outil[0].startswith("create-") or "shadcn" in outil[0] or certain(outil[0], outil[1:])


def _manage(args: list[str]) -> bool:
    return any(a.endswith("manage.py") for a in args) and "makemigrations" in args


def _gestion(args: list[str]) -> bool:
    """`pnpm add`, `npm install`, `pnpm run format`: le gestionnaire réécrit un fichier suivi (dépendances, source)."""
    premier = args[0] if args else ""
    if "--fix" in args and not (_VERIFIE & set(args)):
        return True                                         # `pnpm lint --fix`, `pnpm run lint -- --fix`
    if premier in _INSTALLATION:
        return not (_FIGE & set(args))
    if premier == "run" and len(args) > 1:
        nom = args[1]
        return _SCRIPT_ECRIT.fullmatch(nom) is not None and not (_SCRIPT_VERIFIE.fullmatch(nom) or _VERIFIE & set(args))
    return premier in _GESTION_ECRIT


def _premier(prog: str, args: list[str]) -> bool:
    if args[:1] and args[0] in _INSTALLATION and prog in ("uv", "poetry"):
        return not (_FIGE & set(args))                     # `uv sync` réécrit uv.lock, pas `uv sync --locked`
    return bool(args) and args[0] in _PREMIER_ECRIT.get(prog, ()) and "--check" not in args


def certain(prog: str, args: list[str]) -> bool:
    premier = args[0] if args else ""
    if prog in ("npx", "pnpx") or (prog in _GESTIONNAIRES and premier in ("exec", "dlx")):
        return _outil_lance(prog, args)
    if prog in _GESTIONNAIRES:
        return _gestion(args)
    return _premier(prog, args) or _reecrit_le_code(prog, args) or (prog == "python" and _manage(args))
