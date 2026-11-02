"""Lit une ligne de commande et dit si elle MET EN LIGNE quelque chose (déploiement ou publication).

Un texte qui CITE une commande (message de commit, echo, note) n'en est pas une : la ligne est lue par
`shell_parse`, une commande par segment, et les segments qui ne font qu'afficher (`echo`, `cat`, `grep`...) ou
qui portent un message (`git`, `gh pr`) ne mettent rien en ligne. Partagé par le garde d'audit et le garde du
test de fumée (même famille de défaut : le second lisait le texte brut et prenait une note pour un déploiement).
"""

from __future__ import annotations

import re

from common import looks_like_deploy
from shell_parse import simple_commands

_PUBLISH = re.compile(
    r"npm\s+publish|pnpm\s+(?:(?:-r|--recursive)\s+)?publish|yarn\s+publish|twine\s+upload|cargo\s+publish|"
    r"mix\s+hex\.publish|uv\s+publish|poetry\s+publish|hatch\s+publish|docker\s+(?:image\s+)?push",
    re.IGNORECASE,
)
# These read a file or print an argument; they never run it.
_PRINTERS = {
    "echo", "print", "printf", "cat", "grep", "rg", "head", "tail", "less", "more", "sed", "awk", "nl",
    "sort", "uniq", "cut", "tr", "jq", "ls", "wc", "diff", "stat", "file", "basename", "dirname", "realpath",
}
_SUBSTITUTION = re.compile(r"\$\(|`")
_RUNS_WHAT_FOLLOWS = {"-exec", "-execdir", "-ok", "-okdir"}


def _program_name(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _after_exec_flag(segment):
    """What `find -exec` hands to the shell: the search itself ships nothing, only what it runs can."""
    for i, token in enumerate(segment):
        if token in _RUNS_WHAT_FOLLOWS and i + 1 < len(segment):
            command = [t for t in segment[i + 1 :] if t not in ("{}", ";", "\\", "+")]
            matched = [t for t in segment[:i] if not t.startswith("-")]
            return command + matched
    return None


def _ships(segment, printers_are_safe=True, publishes=True):
    if not segment:
        return False
    if _program_name(segment[0]) == "find":
        nested = _after_exec_flag(segment)
        return _ships(nested, printers_are_safe, publishes) if nested is not None else False
    if _program_name(segment[0]) in _PRINTERS and printers_are_safe:
        return False
    if _program_name(segment[0]) == "git" or segment[:2] == ["gh", "pr"] or segment[:2] == ["gh", "issue"]:
        return False  # a commit message or a log search that names « npm publish » ships nothing
    text = " ".join(segment)
    return looks_like_deploy(text) or (publishes and bool(_PUBLISH.search(text)))


def is_gated(command, publishes=True):
    """True when any real command in the line deploys (or, with `publishes`, publishes). Unparseable: read raw."""
    try:
        segments = simple_commands(command)
    except ValueError:
        segments = [[command or ""]]  # fail closed
    printers_are_safe = not _SUBSTITUTION.search(command or "")
    return any(_ships(segment, printers_are_safe, publishes) for segment in segments)
