#!/usr/bin/env python3
"""Expert avant poussée — PreToolUse Bash. Refuse `git push` tant qu'un commit non poussé, sensible ou critique,
n'a pas eu l'expert que le registre `agents-wiring.json` lui attache.

Pourquoi (Jay 2026-11-01) : 27 agents sur 32 n'avaient été lancés dans aucun projet en 30 jours. Leur « appelant » était
écrit dans des textes de commandes que personne ne tape ; la suggestion par matière ne vérifie jamais qu'elle est suivie.
Le seul agent appelé en continu est le relecteur, parce qu'un garde-fou l'EXIGE avant une mise en ligne. Même mécanisme ici.

Pourquoi à la POUSSÉE : un commit local se corrige à bas coût ; ce qui part vers le dépôt distant engage. Le garde juge
les commits que git dit non poussés, pas le texte d'un commit. En revanche la DÉTECTION de la poussée lit la commande :
`command`/`env`/`(...)`/`-C`/`cd` sont lus, un alias git ou une variable (`$G push`) ne le sont pas (limite écrite).
Limites écrites aussi : un expert lancé pour autre chose dans les 120 min avant le commit compte (preuve faible, assumée) ;
la dispense est lue dans un commentaire de la commande, jamais dans un texte entre guillemets.

Seules les classes Critique et Sensible bloquent (paiement, migration, authentification, Rust `unsafe`) : un garde-fou qui
gêne le travail courant finit débranché (leçon de matter-expert-suggest, 2026-08-30). Passe quand : aucun commit non poussé
n'est concerné, l'expert a été lancé depuis un peu avant le commit (journal des lancements), la commande porte
`# EXPERT-OK: <motif>` d'une liste fermée, ou la situation est illisible (jamais de refus par panne).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_wiring import commit_diff, commit_files, experts_for, load_registry, missing_experts, unpushed_commits  # noqa: E402
from common import block, find_repo_root, get_command, pass_through, read_hook_input  # noqa: E402
from shell_parse import simple_commands  # noqa: E402

_ESCAPE = re.compile(r"(?:^|\s)#\s*EXPERT-OK:\s*(?P<motif>[a-z-]+)\b", re.IGNORECASE)
_QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'')
_GIT_OPTIONS_WITH_VALUE = {"-c", "--git-dir", "--work-tree", "--namespace"}
_WRAPPERS = {"command", "env", "sudo", "nohup", "time", "exec", "(", "{", "!"}   # the last three open a subshell, a group, a negation
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHIPS_NOTHING = {"--dry-run", "-n", "--delete", "-d"}   # a rehearsal and a branch deletion send no commit


def _program(token: str) -> str:
    return token.lstrip("(").replace("\\", "/").rsplit("/", 1)[-1].lower()


def _after_wrappers(segment: list[str]) -> list[str]:
    """The segment without leading `command`, `env`, `sudo`... and `VAR=x` assignments."""
    tokens = list(segment)
    while tokens and (tokens[0] in _WRAPPERS or _program(tokens[0]) in _WRAPPERS or _ASSIGNMENT.match(tokens[0].lstrip("("))):
        tokens.pop(0)
    return tokens


def _git_words(tokens: list[str]) -> tuple[str | None, str | None, list[str]]:
    """(subcommand, `-C <dir>`, what follows the subcommand) of `git [options] <sub> ...`."""
    folder, skip, take = None, False, False
    for index, token in enumerate(tokens):
        if take:
            folder, take = token, False
        elif skip:
            skip = False
        elif token == "-C":
            take = True
        elif token in _GIT_OPTIONS_WITH_VALUE:
            skip = True
        elif not token.startswith("-"):
            return token, folder, tokens[index + 1 :]
    return None, folder, []


def _git_push_dir(segment: list[str]) -> tuple[bool, str | None]:
    """(is a real push, the `-C <dir>` it names) for `[wrappers] [VAR=x] git [options] push ...`."""
    tokens = _after_wrappers(segment)
    if not tokens or _program(tokens[0]) not in ("git", "git.exe"):
        return False, None
    sub, folder, rest = _git_words(tokens[1:])
    return sub == "push" and not (_SHIPS_NOTHING & set(rest)), folder


def _resolve(base: Path, target: str) -> Path:
    """`base / target`, reading a Git-Bash drive path (`/d/x`) as the Windows one (`D:/x`)."""
    drive = re.match(r"^/([a-zA-Z])/(.*)$", target)
    if drive and sys.platform == "win32":
        target = f"{drive.group(1).upper()}:/{drive.group(2)}"
    return base / target


def pushed_folders(command: str, cwd: Path) -> list[Path]:
    """The folders a push in this command runs from: the session's, moved by `cd <dir>`, then by `git -C <dir>`."""
    try:
        segments = simple_commands(command)
    except ValueError:
        return []   # unreadable: a guard that refuses what it cannot read gets unplugged
    current, folders = cwd, []
    for segment in segments:
        words = _after_wrappers(segment)
        if len(words) > 1 and _program(words[0]) == "cd":
            current = _resolve(current, words[1])
            continue
        pushing, folder = _git_push_dir(segment)
        if pushing:
            folders.append(_resolve(current, folder) if folder else current)
    return folders


def is_push(command: str) -> bool:
    return bool(pushed_folders(command, Path(".")))


def _excused(command: str, registry: dict) -> bool:
    """A comment of the command, never a word inside a quoted message (`commit -m "# EXPERT-OK: ..."`)."""
    found = _ESCAPE.search(_QUOTED.sub('""', command))
    return bool(found) and found.group("motif").lower() in registry["dispenses"]


def _refusal(owed: list[tuple[str, list[str]]], registry: dict) -> str:
    lines = [f"- commit {sha[:7]} : {', '.join(agents)}" for sha, agents in owed]
    return (
        "BLOCKED: unpushed commit(s) touch a sensitive or critical area and the expert has not been launched since:\n"
        + "\n".join(lines)
        + "\nRECOVERY: launch each expert with the Agent tool (subagent_type = its name) on the commit, with a brief that "
        "asks it to REFUTE, not to validate; fix what it finds (amend, or a follow-up commit), then push again. If the "
        "commit changes nothing the expert judges, add `# EXPERT-OK: <motif>` to the push command, motif one of: "
        + " | ".join(registry["dispenses"])
        + ". Why: an expert nothing calls is a profile nobody reads; the blocking classes are the ones where a miss costs "
        "most (rules/03-Qualite.md 2 bis). Registry: .claude/rules-ondemand/agents-wiring.json."
    )


def _repository_of(folder: Path) -> Path | None:
    for candidate in (folder, *folder.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def judge(command: str, cwd: Path) -> str | None:
    """The refusal text for the pushes this command runs, in the repositories they run from, or None."""
    folders = pushed_folders(command, cwd)
    registry = load_registry() if folders else {}
    if not folders or _excused(command, registry):
        return None
    owed = [item for root in _roots(folders) for item in _owed_in(root, registry)]
    return _refusal(owed, registry) if owed else None


def _roots(folders: list[Path]) -> list[Path]:
    """The distinct repositories these folders belong to; a folder that does not exist is no repository."""
    found = {_repository_of(folder) for folder in folders if folder.is_dir()}
    return sorted(root for root in found if root)


def _owed_in(root: Path, registry: dict) -> list[tuple[str, list[str]]]:
    """(sha, experts still to launch) for each unpushed commit of `root` that the registry gates."""
    owed = []
    for sha, when in unpushed_commits(root):
        wanted = experts_for(commit_files(root, sha), commit_diff(root, sha), registry)
        absent = missing_experts(root, when, wanted, registry) if wanted else []
        if absent:
            owed.append((sha, absent))
    return owed


def main() -> None:
    _, data = read_hook_input()
    command = get_command(data)
    if not command or "push" not in command:
        pass_through()
    try:
        refusal = judge(command, Path(data.get("cwd") or Path.cwd()))
    except Exception as error:  # noqa: BLE001 — a failure of the guard itself never blocks a push
        print(f"[DEBUG][expert-push-check] {type(error).__name__}: {error}", file=sys.stderr)
        pass_through()
    if refusal:
        block(refusal)
    pass_through()


if __name__ == "__main__":
    main()
