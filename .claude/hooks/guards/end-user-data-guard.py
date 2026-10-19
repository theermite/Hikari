#!/usr/bin/env python3
"""Block any write that would put an end user's identifier into a file or a commit.

RECOVERY PRINCIPLE: the message tells Takumi what to do next, and never repeats
the matched word (the block must not itself leak what it protects).

Why (2026-10-10, Shizen): the pseudo of a real end user, given by Jay for a
yes/no check, was copied by Takumi into a published planning document — the
Confidentiality rule (Gate C) forbade it, and the writing did not hold. Jay:
"vraiment, énormément agaçant". The rule is now held by code.

What is checked (only NEW text — removing an identifier must stay possible):
  * Write `content`, Edit `new_string`, MultiEdit `edits[].new_string`,
    NotebookEdit `new_source` — and the FILE PATH of each of them;
  * Bash `git commit`: the message (`-m`, `-F file`, heredoc on `-F -`), the
    added lines AND the file names of what will be committed (`-a`, pathspec,
    `--include` and renames included).

The command is read the way the shell reads it (quotes, `cd`, subshells,
`git -C`), not with a regex over the raw text — the first version let
`git commit -a`, `-F file`, `(cd x && git commit)` and a quoted `-C` through
(independent review, Fable 5.1, 2026-10-10). On a commit, anything the guard
cannot establish (repository not found, git failing, message built by command
substitution) is REFUSED: fail-closed.

What is NOT checked, on purpose: other Bash commands. A read-only query may need
the word (a yes/no check Jay asks for); a file written by Bash is still caught at
the commit. Files written by Bash and never committed (e.g. /tmp) are not. Also
accepted: homoglyphs, HTML entities, URL encoding, a separator inserted INSIDE a
pseudo (`Zor-vexa`), a commit run through another interpreter (`eval`, `sh -c`,
`bash -c`, `xargs`), and `git commit -C <commit>` (it reuses a message that
already passed this guard).

Identifiers come from `lib/end_user_identifiers.py` (salted fingerprints, outside
every repository). No list on this machine (e.g. a workstation without the
account databases): the guard cannot judge, and lets the write through.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from end_user_identifiers import contains_identifier, store_present  # noqa: E402

GIT_TIMEOUT = 15
# `-m "$(cat <<'EOF' ... EOF\n)"` : forme standard des commits de Claude Code. Le
# corps est lu, et la substitution remplacee par un repere neutre (seconde
# relecture 2026-10-10 : sans cela, presque chaque commit etait refuse).
_CAT_HEREDOC = re.compile(r"\$\(\s*cat\s*<<-?\s*(['\"])(\w+)\1[^\n]*\n(.*?)\n\s*\2\s*\n?\s*\)", re.S)
# Expansion = tout ce que bash remplacerait par autre chose avant que git ne lise
# le message : `$x`, `${x}`, `$(...)`, `` `...` ``, hors guillemets simples. Lu
# caractere par caractere, avec l'etat des guillemets — trois relectures ont montre
# qu'une liste de regex laisse toujours une forme passer (troisieme : `"$M"`,
# `-m"$(...)"`, `"a"$(...)"b"`, heredoc a delimiteur non quote).
_EXPANDS_AFTER_DOLLAR = re.compile(r"[A-Za-z_0-9{(@*#?!$-]")
_KEYWORDS = {"then", "do", "else", "elif", "time", "command", "exec", "!", "{"}
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n\s*\2\s*(?:\n|$)", re.S)
_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
_MESSAGE_OPTS = {"-m", "--message"}
_FILE_OPTS = {"-F", "--file", "-t", "--template"}
_VALUE_OPTS = _MESSAGE_OPTS | _FILE_OPTS | {
    "-C", "-c", "--reuse-message", "--reedit-message", "--author", "--date",
    "--fixup", "--squash", "--cleanup", "-S", "--gpg-sign", "--trailer", "--pathspec-from-file",
}

BLOCK = (
    "BLOCKED: {where} contient un identifiant d'utilisateur final (pseudo, nom ou "
    "adresse) — Confidentiality.md, Gate C : jamais dans un fichier, un commit ou un "
    "rapport, même appris de Jay.\n"
    "RECOVERY: remplacer par une description neutre (« l'utilisatrice principale », "
    "« la personne B »), puis réessayer. Le mot n'est pas répété ici exprès. "
    "Faux positif (mot courant) : Jay peut le déclarer inoffensif — "
    "`python3 .claude/hooks/lib/end_user_identifiers.py allow`, le mot sur l'entrée "
    "standard."
)
UNSURE = (
    "BLOCKED: commit non vérifiable — {why}. Le garde-fou des données d'utilisateurs "
    "refuse ce qu'il ne peut pas lire (fail-closed).\n"
    "RECOVERY: lancer le commit depuis le dépôt (`cd <dépôt> && git commit ...`), "
    "message en `-m \"...\"` ou en heredoc sur `-F -`, sans substitution `$(...)`."
)


class Unsure(Exception):
    """The commit cannot be verified — refuse rather than guess."""


# --- Write / Edit -------------------------------------------------------------


def _texts_from_write(tool: str, tool_input: dict) -> list[tuple[str, str]]:
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    texts = [(f"Le chemin {path}", path)] if path else []
    if tool == "Write":
        texts.append((f"Le contenu de {path}", tool_input.get("content") or ""))
    elif tool == "Edit":
        texts.append((f"La modification de {path}", tool_input.get("new_string") or ""))
    elif tool == "MultiEdit":
        for edit in tool_input.get("edits") or []:
            if isinstance(edit, dict):
                texts.append((f"La modification de {path}", edit.get("new_string") or ""))
    elif tool == "NotebookEdit":
        texts.append((f"La cellule de {path}", tool_input.get("new_source") or ""))
    else:
        return []
    return texts


# --- Bash: read the command like the shell does -------------------------------


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    # shlex groupe les ponctuations voisines (`);`) en un seul jeton : les
    # separer, sinon un separateur passe inapercu (relecture 2026-10-10).
    out: list[str] = []
    for token in lexer:
        if token and all(ch in ";&|()" for ch in token):
            out.extend(re.findall(r"&&|\|\||[;&|()]", token))
        else:
            out.append(token)
    return out


def _safe_tokens(segment: str) -> list[str]:
    try:
        return _tokens(segment)
    except ValueError:
        return []


def _expand(path: str, cwd: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(path))
    return os.path.normpath(os.path.join(cwd, expanded))


def _segments(tokens: list[str], cwd: str):
    """Yield (cwd, simple-command tokens), following `cd` and subshell scope."""
    stack = [cwd]
    current: list[str] = []
    for token in tokens + [";"]:
        if token in _SEPARATORS:
            if current:
                yield stack[-1], current
                if current[0] == "cd":
                    stack[-1] = _expand(current[1] if len(current) > 1 else "~", stack[-1])
            current = []
            if token == "(":
                stack.append(stack[-1])
            elif token == ")" and len(stack) > 1:
                stack.pop()
            continue
        if not current and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token):
            continue  # VAR=value prefix
        current.append(token)


def _git_commit_args(words: list[str], cwd: str) -> tuple[str, list[str]] | None:
    """If the simple command is `git [global opts] commit ...`, return (repo dir, commit args)."""
    while words and words[0] in _KEYWORDS:
        words = words[1:]
    if not words or Path(words[0]).name != "git":
        return None
    i, here = 1, cwd
    while i < len(words):
        word = words[i]
        if word == "-C" and i + 1 < len(words):
            here = _expand(words[i + 1], here)
            i += 2
        elif word in {"-c", "--git-dir", "--work-tree", "--namespace"} and i + 1 < len(words):
            i += 2
        elif word.startswith("-"):
            i += 1
        else:
            break
    if i < len(words) and words[i] == "commit":
        return here, words[i + 1 :]
    return None


def _parse_commit(args: list[str]) -> dict:
    parsed = {"messages": [], "files": [], "all": False, "include": False, "paths": []}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            parsed["paths"].extend(args[i + 1 :])
            break
        name, eq, inline = arg.partition("=")
        if arg in {"-a", "--all"}:
            parsed["all"] = True
        elif arg in {"-i", "--include"}:
            parsed["include"] = True
        elif arg.startswith("-m") and len(arg) > 2 and not arg.startswith("--"):
            parsed["messages"].append(arg[2:])
        elif eq and name in _VALUE_OPTS:
            _take(parsed, name, inline)
        elif arg in _VALUE_OPTS and i + 1 < len(args):
            _take(parsed, arg, args[i + 1])
            i += 1
        elif not arg.startswith("-"):
            parsed["paths"].append(arg)
        i += 1
    return parsed


def _take(parsed: dict, option: str, value: str) -> None:
    if option in _MESSAGE_OPTS:
        parsed["messages"].append(value)
    elif option in _FILE_OPTS:
        parsed["files"].append(value)


def _git(repo: str, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo, *args], capture_output=True, text=True, timeout=GIT_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unsure("git n'a pas répondu") from exc
    if result.returncode != 0:
        raise Unsure("git a échoué dans ce dépôt")
    return result.stdout


def _has_head(repo: str) -> bool:
    try:
        _git(repo, "rev-parse", "--verify", "-q", "HEAD")
        return True
    except Unsure:
        return False


def _committed_changes(repo: str, parsed: dict) -> tuple[str, str]:
    """(added lines, file names) of what this commit will record."""
    against_head = parsed["all"] or bool(parsed["paths"])
    base = ["diff", "HEAD"] if against_head and _has_head(repo) else ["diff", "--cached"]
    paths = ["--", *parsed["paths"]] if parsed["paths"] else []
    diffs = [_git(repo, *base, "-U0", "--no-color", *paths)]
    names = [_git(repo, *base, "--name-only", *paths)]
    if parsed["include"] or (against_head and base[1] == "HEAD"):
        diffs.append(_git(repo, "diff", "--cached", "-U0", "--no-color"))
        names.append(_git(repo, "diff", "--cached", "--name-only"))
    added = "\n".join(
        line[1:]
        for diff in diffs
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    return added, "\n".join(names)


def _texts_from_commit(repo: str, args: list[str], raw: str) -> list[tuple[str, str]]:
    if not os.path.isdir(repo):
        raise Unsure("le dépôt visé n'existe pas")
    _git(repo, "rev-parse", "--show-toplevel")
    parsed = _parse_commit(args)
    texts = [("Le message du commit", m) for m in parsed["messages"]]
    for name in parsed["files"]:
        if name == "-":
            continue  # heredoc on stdin: covered by the raw command text below
        path = _expand(name, repo)
        try:
            texts.append(("Le message du commit", Path(path).read_text(encoding="utf-8")))
        except OSError as exc:
            raise Unsure("fichier de message illisible") from exc
    added, names = _committed_changes(repo, parsed)
    texts += [
        ("Le texte de la commande de commit", raw),
        ("Une ligne ajoutée au commit", added),
        ("Un nom de fichier du commit", names),
    ]
    return texts


def _split_raw(command: str) -> list[str]:
    """Split on ; && || | & ( ) and newlines OUTSIDE quotes and $(...), keeping raw text."""
    segments, current, i, quote, depth = [], [], 0, None, 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            current.append(c)
            quote = None if c == "'" else quote
        elif c == "\\" and i + 1 < len(command):
            current.append(command[i : i + 2])
            i += 1
        elif quote == '"':
            current.append(c)
            if c == '"':
                quote = None
            elif command.startswith("$(", i):
                depth += 1
            elif c == ")" and depth:
                depth -= 1
        elif c in "'\"":
            current.append(c)
            quote = c
        elif command.startswith("$(", i):
            depth += 1
            current.append("$(")
            i += 1
        elif depth and c == "(":
            depth += 1
            current.append(c)
        elif depth and c == ")":
            depth -= 1
            current.append(c)
        elif depth == 0 and c in ";&|()\n":
            segments.append("".join(current))
            current = []
        else:
            current.append(c)
        i += 1
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


_COMMIT_WORDS = re.compile(r"\bgit\b[\s\S]*\bcommit\b")


def _backquote_outside_single_quotes(command: str) -> bool:
    i, quote = 0, None
    while i < len(command):
        c = command[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1
        elif c == "`":
            return True
        elif c == "'" and quote is None:
            quote = "'"
        elif c == '"':
            quote = None if quote == '"' else '"'
        i += 1
    return False


def _has_expansion(segment: str) -> bool:
    """True if bash would expand something in this segment (outside single quotes)."""
    i, quote = 0, None
    while i < len(segment):
        c = segment[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1
        elif c == "`":
            return True
        elif c == "$" and segment.startswith("$'", i) and quote is None:
            end = segment.find("'", i + 2)
            i = end if end != -1 else len(segment)
        elif c == "$" and i + 1 < len(segment) and _EXPANDS_AFTER_DOLLAR.match(segment[i + 1]):
            return True
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif c == "'" and quote is None:
            quote = "'"
        i += 1
    return False


def _texts_from_bash(command: str, cwd: str) -> list[tuple[str, str]]:
    cat_bodies = [m.group(3) for m in _CAT_HEREDOC.finditer(command)]
    command = _CAT_HEREDOC.sub("message-heredoc", command)
    heredocs = list(_HEREDOC.finditer(command))
    bodies = "\n".join(cat_bodies + [m.group(3) for m in heredocs])
    # Heredoc a delimiteur NON quote : bash expanse son corps.
    expanding_heredoc = any(not m.group(1) and _has_expansion(m.group(3)) for m in heredocs)
    stripped = _HEREDOC.sub(" ", command)
    try:
        tokens = _tokens(stripped)
    except ValueError as exc:
        if re.search(r"\bgit\b.*\bcommit\b", stripped):
            raise Unsure("commande illisible (guillemets non fermés)") from exc
        return []
    texts: list[tuple[str, str]] = []
    # Un backquote hors guillemets simples execute une commande que ni l'un ni
    # l'autre lecteur ne voit comme telle (`` `git commit ...` ``, cinquieme
    # relecture) : des qu'un commit est evoque, refuser.
    if _COMMIT_WORDS.search(stripped) and _backquote_outside_single_quotes(stripped):
        raise Unsure("backquote dans une commande de commit")
    commit_segments = [s for s in _split_raw(stripped) if _git_commit_args(_safe_tokens(s), cwd)]
    if commit_segments and (expanding_heredoc or any(_has_expansion(s) for s in commit_segments)):
        raise Unsure("le commit contient une expansion du shell ($VAR, $(...), backquote)")
    commits = [(here, words) for here, words in _segments(tokens, cwd) if _git_commit_args(words, here)]
    # Deux lecteurs (texte brut, mots du shell) : s'ils ne trouvent pas le meme
    # nombre de commits, l'un des deux a mal lu — refuser plutot que deviner.
    if len(commits) != len(commit_segments):
        raise Unsure("lecture ambigue de la commande")
    for here, words in commits:
        found = _git_commit_args(words, here)
        if found:
            repo, args = found
            texts += _texts_from_commit(repo, args, command + "\n" + bodies)
    return texts


# --- entry point --------------------------------------------------------------


def _check(payload: dict) -> int:
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    try:
        if tool == "Bash":
            texts = _texts_from_bash(tool_input.get("command") or "", payload.get("cwd") or os.getcwd())
        else:
            texts = _texts_from_write(tool, tool_input)
    except Unsure as exc:
        print(UNSURE.format(why=exc), file=sys.stderr)
        return 2
    for where, text in texts:
        if contains_identifier(text):
            print(BLOCK.format(where=where), file=sys.stderr)
            return 2
    return 0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict) or not store_present():
        return 0
    try:
        return _check(payload)
    except Exception as exc:  # noqa: BLE001 — a crashed guard must say so, never block everything
        print(f"WARNING: end-user-data-guard a échoué ({type(exc).__name__}) — rien n'a été vérifié.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
