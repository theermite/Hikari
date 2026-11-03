"""Ce que git EXÉCUTE : un segment `git`/`gh` ne livre rien par lui-même, mais il peut lancer une commande.

Partagé par `guards/pre-deploy-review-check.py`. Un message de commit qui CITE « docker compose up » ne livre rien (3 commits
refusés le 2026-11-02) ; en revanche un alias, une clé de configuration qui lance un programme (`core.sshCommand`, `core.pager`,
`credential.helper`…), `submodule foreach`, `bisect run`, `rebase --exec`, `filter-branch`, `--upload-pack` ou une substitution
vivante `$( … )`, `<( … )`, backtick dans un argument lancent bien une commande (relectures indépendantes du 2026-11-02 :
vingt-quatre voies gardées avant l'exemption et rouvertes par elle, rendues ici).

Limite écrite : une substitution multiligne (message de commit en bloc `$(cat <<'EOF' … EOF)`) n'est pas analysable ici ; le
garde la lit en brut, comme avant (décision de Jay du 2026-10-19 : aucune analyse de substitution par motifs dans la lecture des
commandes).
"""

from __future__ import annotations

import re
from typing import Callable

_EXECUTES = {"foreach", "bisect", "-x", "filter-branch", "difftool", "mergetool"}
_EXECUTING_OPTIONS = ("--exec", "--tree-filter", "--index-filter", "--msg-filter", "--commit-filter", "--env-filter",
                      "--extcmd", "--upload-pack", "--receive-pack", "--ssh-command")
# `-c clé=valeur` : la clé est au DÉBUT du jeton, donc un message qui cite « core.sshCommand » en passant n'en est pas une.
_EXECUTING_KEY = re.compile(
    r"^(?:alias\.[^=]+|core\.(?:sshcommand|pager|editor|fsmonitor|hookspath|askpass)|sequence\.editor|credential\.helper"
    r"|protocol\.ext\.allow|gpg\.program|diff\.external|merge\.\w+\.driver)=", re.IGNORECASE)
_OPENERS = re.compile(r"\$\(|<\(|`")


def _executes(token: str) -> bool:
    t = token.lower()
    return (t in _EXECUTES or t.startswith(_EXECUTING_OPTIONS) or t.startswith("!") or bool(_EXECUTING_KEY.match(token)))


def git_runs_a_deploy(segment: list[str], text: str, is_deploy_text: Callable[[str], bool]) -> bool:
    """A git (or gh) segment that executes a command AND names a deploy: an alias, `core.sshCommand`, `bisect run`, `-x`…"""
    return any(_executes(t) for t in segment) and is_deploy_text(text)


def _balanced_from(text: str, start: int) -> str:
    """The text from `start` up to the parenthesis that closes the substitution opened just before (nesting counted)."""
    depth = 1
    for i in range(start, len(text)):
        depth += (text[i] == "(") - (text[i] == ")")
        if depth == 0:
            return text[start:i]
    return text[start:]


def substitution_ships(text: str, is_deploy_text: Callable[[str], bool]) -> bool:
    """A live `$( … )`, `<( … )` or backtick substitution inside the arguments that deploys: it runs before git does."""
    for opener in _OPENERS.finditer(text):
        inner = text[opener.end():text.find("`", opener.end())] if opener.group() == "`" else _balanced_from(text, opener.end())
        if is_deploy_text(inner):
            return True
    return False
