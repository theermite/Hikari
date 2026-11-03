"""Experts rappelés par un GESTE : commit, mise en ligne. Les experts de matière sont rappelés par le fichier touché
(agent_wiring.reminders_for) ; ceux du contrôle (qualité du code, tests, débogage, refonte, sécurité, déploiement…) n'ont
pas de fichier à eux. Les conditions sont ici, le câblage (quel expert, quel seuil) est dans `agents-wiring.json`, section
`moments`. Rien ici ne bloque : un rappel, tracé, mesuré chaque semaine.
"""

from __future__ import annotations

import re

_TESTS = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.|\.test\.|\.spec\.", re.IGNORECASE)

# `git commit` lu sur le TEXTE de la commande, pas sur son découpage en mots : la forme la plus courante de Claude Code
# (`-m "$(cat <<'EOF' … EOF)"`) n'est pas découpable sans exécuter la substitution. Un rappel peut se permettre d'être
# approximatif ; il ne bloque jamais. Limites écrites : un alias git, une variable (`$G commit`) ne sont pas vus ; `-a` est
# lu n'importe où après `commit` ; `echo git commit` n'est pas un commit (git doit ouvrir un segment de la commande).
_START = r"(?:^|[;&|(\n])\s*"
_WRAP = r"(?:(?:command|env|nohup|time|exec)\s+|[A-Za-z_]\w*=\S*\s+|sudo(?:\s+-\S+(?:\s+[^\s-]\S*)?)*\s+)*"
_OPTS = r"(?:\s+(?:-C\s+(?P<dir>\"[^\"]+\"|'[^']+'|\S+)|-c\s+\S+|--[\w-]+(?:=\S+)?))*"
_COMMIT = re.compile(_START + _WRAP + r"git(?:\.exe)?" + _OPTS + r"\s+commit(?=\s|$)")
_MESSAGE = re.compile(
    r"""(?:\s-[a-zA-Z]*m|\s--message)[\s=]*["']?(?:\$\(cat\s+<<-?\s*['"]?\w+['"]?\s*)?([A-Za-z]+)(?:\([^)\n]*\))?!?:""")
_EVERYTHING = re.compile(r"\s(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?=\s|$)")
_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1[^\n]*\n(?P<body>.*?)\n[ \t]*\2(?=\s|$|\))", re.DOTALL)
_QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'", re.DOTALL)


def _mask_heredoc_bodies(command: str) -> str:
    """The command with the BODY of every heredoc blanked (same length, so positions still line up): a line of a text
    handed to another tool (`python - <<EOF … git commit … EOF`) is not a command."""
    return _HEREDOC.sub(lambda m: m.group(0).replace(m.group("body"), re.sub(r"[^\n]", " ", m.group("body"))), command)


def _own_flags(rest: str) -> str:
    """What follows `commit` on its own command line: quoted text removed, cut at the next `;` `&` `|` or line break."""
    return re.split(r"[;&|\n]", _QUOTED.sub('""', rest), maxsplit=1)[0]


def parse_commit(command: str) -> dict | None:
    """{kind, directory, everything} of the first `git commit` of a command, or None when it holds none.

    `kind` = the conventional type of the message (`fix`, `refactor`…) or None ; `directory` = the `-C` folder or None ;
    `everything` = `-a`/`--all` (the commit takes every tracked change, not only the staged ones).
    """
    found = _COMMIT.search(_mask_heredoc_bodies(command))
    if not found:
        return None
    rest = command[found.end():]
    message = _MESSAGE.search(rest)
    folder = (found.group("dir") or "").strip("\"'") or None
    return {"kind": message.group(1).lower() if message else None, "directory": folder,
            "everything": bool(_EVERYTHING.search(_own_flags(rest)))}


def _moment(registry: dict, moment_id: str) -> dict:
    return next((m for m in registry.get("moments", []) if m["id"] == moment_id), {"agents": []})


def _pairs(registry: dict, moment_id: str) -> list[tuple[str, str]]:
    return [(agent, moment_id) for agent in _moment(registry, moment_id)["agents"]]


def _split(files: list[str], registry: dict) -> tuple[list[str], list[str]]:
    """(code files, test files): documents never count, tests are counted apart."""
    skip = re.compile(registry["exclusion_par_defaut"], re.IGNORECASE)
    normal = [p.replace("\\", "/") for p in files]
    return [f for f in normal if not skip.search(f)], [f for f in normal if _TESTS.search(f)]


def _ids_owed(code: list[str], tests: list[str], kind: str | None, fixed_before: set[str], registry: dict) -> list[str]:
    ids = []
    if len(code) >= _moment(registry, "commit-gros").get("seuil_fichiers", 6):
        ids.append("commit-gros")
    if code and tests:
        ids.append("commit-tests")
    if code and kind == "refactor":
        ids.append("commit-refactor")
    if kind in ("fix", "hotfix") and fixed_before & set(code):
        ids.append("correctif-repete")
    return ids


def commit_moments(files: list[str], kind: str | None, fixed_before: set[str], registry: dict) -> list[tuple[str, str]]:
    """(agent, moment id) owed by a commit of these files. `fixed_before` = files a recent `fix` commit already touched."""
    code, tests = _split(files, registry)
    return [pair for moment_id in _ids_owed(code, tests, kind, fixed_before, registry) for pair in _pairs(registry, moment_id)]


def deploy_moments(registry: dict) -> list[tuple[str, str]]:
    return _pairs(registry, "mise-en-ligne")
