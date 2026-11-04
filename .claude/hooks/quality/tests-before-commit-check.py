#!/usr/bin/env python3
"""Tests-before-commit check — PreToolUse Bash. Pas de commit sur des tests rouges dont la sortie n'a pas été lue.

Retour de Jay (2026-11-04) : Takumi écrit sans vérifier, puis l'avoue. Cas observé (journal Compendium) : une suite de
tests commitée alors que sa dernière ligne était une trace d'erreur, « j'ai commité trop vite ».

Le garde refuse un `git commit` dans deux cas, lus dans le tour en cours :
  1. la DERNIÈRE exécution de tests du tour est rouge ou en erreur et aucune exécution verte ne la suit ;
  2. les tests et le commit sont dans la même commande, reliés par `;`, `||`, un retour à la ligne ou un tube (`| tail`) :
     le commit part même si les tests échouent, et la sortie n'est lue qu'après coup. `&&` est la bonne forme.
Un commit de documentation ou d'entretien (sujet `docs…` ou `chore…`) ne dépend pas des tests. Sortie voulue (phase rouge
d'un cycle test d'abord) : `# TESTS-ROUGES-OK: <raison en trois mots ou plus>`.
Limites écrites : on lit le journal du tour ; les tests lancés dans un autre tour ou une autre session ne sont pas vus ;
une commande de tests inconnue (script maison) n'est pas reconnue. Échec ouvert.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, get_command, pass_through, read_hook_input  # noqa: E402
from turn_log import is_test_command, looks_red, tool_runs  # noqa: E402

_COMMIT = re.compile(r"(?<![\w-])git\s+(?:-\S+\s+(?:\S+\s+)?)*commit\b")
_MARKER = re.compile(r"#\s*TESTS-ROUGES-OK:\s*\S+(?:\s+\S+){2,}")
_SUBJECT_M = re.compile(r"""-[a-z]*m\s+["']?\$?\(?[^"'\n]*?([A-Za-z][\w()!:/-]*)""")
_SUBJECT_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\s*\n\s*(\S[^\n]*)")
_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", re.DOTALL)
_BREAK = re.compile(r";|\|\||\n|(?<!\|)\|(?!\|)")
_ERREXIT = re.compile(r"(?m)^\s*set\s+-[a-z]*e|\bset\s+-o\s+errexit")

MESSAGE = (
    "Tu t'apprêtes à commiter. {why} Lis la sortie des tests (la commande et ce qu'elle a affiché), corrige ou explique ce "
    "qui est rouge, relance les tests, puis commite avec `&&` (jamais `;` ni un tube qui cache le code de sortie). Si le "
    "rouge est voulu (phase rouge d'un cycle test d'abord), ajoute à la commande : "
    "# TESTS-ROUGES-OK: <raison en trois mots ou plus>."
)


def _real_commit(command: str):
    """The first `git commit` that is a command, not text written by a heredoc (a script that merely cites one)."""
    spans = [m.span() for m in _HEREDOC.finditer(command)]
    return next((m for m in _COMMIT.finditer(command) if not any(a <= m.start() < b for a, b in spans)), None)


def _subject(command: str, commit_at: int = 0) -> str:
    """Le sujet du message de COMMIT (après `git commit`) : première ligne d'un message en bloc, ou premier -m / -am."""
    after = command[commit_at:]
    heredoc = _SUBJECT_HEREDOC.search(after)
    if heredoc:
        return heredoc.group(2).strip()
    found = _SUBJECT_M.search(after)
    return found.group(1) if found else ""


def _chained(command: str, commit_at: int) -> bool:
    """Une commande de tests, puis un lien qui n'arrête pas le commit si elle échoue, puis le commit."""
    before = _HEREDOC.sub(" ", command[:commit_at])  # text written to a file is not a command
    before = re.sub(r"&&\s*\n|\\\n", "&& ", before)  # `&&` then a new line, or a continuation: still one safe chain
    if _ERREXIT.search(before):
        return False
    last = None
    for match in re.finditer(r"[^\n;&|]+", before):
        if is_test_command(match.group(0).strip()):
            last = match
    if last is None:
        return False
    return bool(_BREAK.search(before[last.end():]))


def _why(command: str, commit_at: int, transcript: str) -> str | None:
    if _chained(command, commit_at):
        return "Les tests et le commit sont dans la même commande, reliés par `;`, `||`, un retour à la ligne ou un tube : le commit part même si les tests échouent."
    if is_test_command(_HEREDOC.sub(" ", command[:commit_at])):
        return None  # tests chained with && in this very command: the commit only happens if they pass
    # a call without a result is the one being judged (the journal already holds it): it proves nothing
    tests = [r for r in tool_runs(transcript) if r.name == "Bash" and is_test_command(r.command) and (r.output or r.is_error)]
    if tests and looks_red(tests[-1].output, tests[-1].is_error):
        return "La dernière exécution de tests de ce tour est rouge ou en erreur, et aucune exécution verte ne la suit."
    return None


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        pass_through()
    command = get_command(data)
    commit = _real_commit(command)
    if not commit or _MARKER.search(command) or _subject(command, commit.start()).lower().startswith(("docs", "chore")):
        pass_through()
    why = _why(command, commit.start(), data.get("transcript_path") or "")
    if why:
        block(MESSAGE.format(why=why))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a tool call
        print(f"[tests-before-commit-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
