"""Read a shell command the way a shell would — shared by every Bash guard.

Why this exists (2026-08-10): two guards each grew their own hand-rolled parsing,
and each correction reopened an adjacent hole. Three independent reviews in one
evening found the same class of defect four times:

  - `git -C "path with space" add -A` — a regex missed the quoted path
  - `git add -A` on a second line — a newline is a separator too
  - `echo "note <<EOF" ; docker compose up -d` — a quoted `<<` swallowed the rest
  - `bash -c 'git push --force'` — the executed content sat inside quotes

The cure is not another pattern: it is to stop guessing at the surface and read
tokens. One parser, one set of rules, both guards.

Honest limits — this is not a shell:
  - Command substitution, variable expansion and process substitution are not
    resolved. A guard built on this sees the text, not the runtime.
  - `_feeds_a_shell` looks at every token, not just the program name, so
    `echo bash <<EOF … EOF` reads its body as code. That over-detects, never
    under-detects: the safe direction for a guard (6th review, 2026-08-10).
  - `ssh -c <cipher>` collides with `bash -c <script>`: the cipher name gets
    parsed as if it were a script. Harmless (it yields one meaningless segment),
    but the command `ssh` actually runs remotely — its last argument — is still
    read as data, not code. Known gap, unchanged by this module.
  - Unparseable input raises ValueError so the caller can fail closed.
"""

from __future__ import annotations

import shlex

SEPARATORS = {"&&", "||", ";", "|", "&"}

# A heredoc delimiter always carries a letter (EOF, PY, SQL). Requiring one keeps
# an arithmetic shift — `$((5 << 2))` — from being read as a heredoc.
_HEREDOC_OPENERS = ("<<", "<<-")


def _tokenize(line: str) -> list[str]:
    """Tokenise one line. Raises ValueError when quotes do not close."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""  # a backslash is a Windows path separator here, not an escape
    return list(lexer)


def _is_heredoc_delimiter(token: str) -> bool:
    return any(char.isalpha() or char == "_" for char in token)


def _strip_heredoc(tokens: list[str]) -> tuple[list[str], str | None]:
    """Remove `<< DELIM` from a token list. Return (tokens, delimiter or None)."""
    kept: list[str] = []
    delimiter = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        following = tokens[i + 1] if i + 1 < len(tokens) else ""
        if token in _HEREDOC_OPENERS and _is_heredoc_delimiter(following):
            delimiter = following
            i += 2
            continue
        kept.append(token)
        i += 1
    return kept, delimiter


# A heredoc fed to a SHELL is code, not data — `bash <<EOF … EOF` really runs it.
# Fed to anything else (python, node), the body is that language's source, and
# reading it as shell would invent commands nobody typed.
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "ksh", "dash", "ssh"}


def _join_continuations(command: str) -> str:
    """`git \\` + newline + `add -A` is ONE command (4th review, 2026-08-10)."""
    return (command or "").replace("\\\n", " ")


def _split_on_separators(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in SEPARATORS:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return segments


def _program_name(token: str) -> str:
    """`C:\\Git\\bin\\BASH.EXE` and `/usr/bin/bash` both read as `bash`.

    Windows is the platform these guards run on: `bash.exe` is the real name, and
    the filesystem is case-insensitive (5th independent review, 2026-08-10).
    """
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _feeds_a_shell(tokens: list[str]) -> bool:
    return any(_program_name(token) in SHELL_INTERPRETERS for token in tokens)


def _remote_command(segment: list[str]) -> str | None:
    """What `ssh <host> <command>` runs on the other side — code, not an argument."""
    rest = segment[1:]
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in ("-c", "-i", "-p", "-o", "-l") else rest[1:]
    return " ".join(rest[1:]) if len(rest) > 1 else None


def _inline_shell_script(segment: list[str]) -> str | None:
    """The code a shell is handed: `bash -c '<script>'`, or `ssh <host> <command>`.

    Only for a shell: `python -c 'print(1)'` is Python source, and reading it as
    shell would invent commands nobody typed.
    """
    if not segment or _program_name(segment[0]) not in SHELL_INTERPRETERS:
        return None
    if _program_name(segment[0]) == "ssh":
        return _remote_command(segment)
    for i, token in enumerate(segment[:-1]):
        if token == "-c":
            return segment[i + 1]
    return None


# Nested heredocs recurse. Past this depth the input is adversarial, not real:
# raising lets callers fail closed, where a crash would exit 1 — which the hook
# contract reads as "warning", not "block" (5th independent review, 2026-08-10).
MAX_HEREDOC_DEPTH = 10


def _quote_states(text: str):
    """(index, char, in_single_quotes, in_double_quotes) for each character, reading quotes as bash does.

    Inside double quotes a backslash escapes the next character (`\\"` is a literal quote and the string goes
    on); inside single quotes nothing is special (review 2026-11-01). The flags are the state BEFORE the char.
    """
    in_single = in_double = skip = False
    for index, char in enumerate(text):
        yield index, char, in_single, in_double
        if skip:
            skip = False
        elif char == "\\" and in_double:
            skip = True
        elif char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double


def _has_live_substitution(text: str) -> bool:
    """`$(` or a backtick outside single quotes: the shell RUNS what is inside, whatever the double quotes say."""
    return any(
        not in_single and (char == "`" or (char == "$" and text[index + 1 : index + 2] == "("))
        for index, char, in_single, _ in _quote_states(text)
    )


def _bash_leaves_quotes_open(text: str) -> bool:
    """True when bash itself would still be inside a quoted string at the end of `text`."""
    *_, (_, _, in_single, in_double) = _quote_states(text + " ")
    return in_single or in_double


def _tokenize_logical_line(lines: list[str], i: int) -> tuple[list[str], int]:
    """Tokens of the command starting at `lines[i]`, and the index of its LAST physical line.

    A quoted string may span lines (every multi-line commit message does): while the quotes are still open,
    the next physical line belongs to the same command. A quote that never closes still raises ValueError,
    so the callers keep failing closed (2026-11-01: a multi-line message made the reader give up, and the
    deploy guard then searched the raw text and refused a note that merely QUOTED « docker compose up »).
    """
    line, last = lines[i], i
    while True:
        try:
            tokens = _tokenize(line)
            tokenizer_open = False
        except ValueError:
            tokens, tokenizer_open = [], True
        if tokenizer_open != _bash_leaves_quotes_open(line):
            # The tokenizer reads `\"` as a closing quote, bash does not: the two disagree on where the string
            # ends, so nothing it says about the rest of the line can be trusted (relecture 7.7.0, 2026-11-01).
            raise ValueError("the tokenizer and bash read the quotes of this line differently")
        if tokenizer_open:
            if last + 1 >= len(lines):
                raise ValueError("No closing quotation")
            last += 1
            line += "\n" + lines[last]
            continue
        if last > i and _has_live_substitution(line):
            raise ValueError("a multi-line string holds a command substitution: it is code, not text")
        if last > i and '\\"' in line:
            raise ValueError("a multi-line string holds an escaped quote: the tokenizer cannot be trusted on it")
        return tokens, last


def _with_inline_script(segment: list[str], depth: int) -> list[list[str]]:
    """The segment itself, then the commands of its inline shell script (`bash -c '…'`), if it has one."""
    script = _inline_shell_script(segment)
    return [segment, *simple_commands(script, depth + 1)] if script else [segment]


def simple_commands(command: str, _depth: int = 0) -> list[list[str]]:
    """Split a shell line into simple commands, as token lists.

    Newlines and line continuations are handled like a shell does. A heredoc body
    is data — unless it is piped into a shell, in which case it is code and gets
    parsed too. Quoted text stays one token, so a command merely NAMED inside a
    string is never mistaken for a command that runs.

    Raises ValueError on quotes that never close, or heredocs nested past
    MAX_HEREDOC_DEPTH.
    """
    if _depth > MAX_HEREDOC_DEPTH:
        raise ValueError(f"heredoc nesting deeper than {MAX_HEREDOC_DEPTH}")

    lines = _join_continuations(command).splitlines()
    segments: list[list[str]] = []
    i = 0

    while i < len(lines):
        line_tokens, i = _tokenize_logical_line(lines, i)
        tokens, delimiter = _strip_heredoc(line_tokens)
        body, i = _read_heredoc_body(lines, i + 1, delimiter)
        for segment in _split_on_separators(tokens):
            segments.extend(_with_inline_script(segment, _depth))
        if body and _feeds_a_shell(tokens):
            segments.extend(simple_commands("\n".join(body), _depth + 1))

    return [segment for segment in segments if segment]


def _read_heredoc_body(
    lines: list[str], start: int, delimiter: str | None
) -> tuple[list[str], int]:
    """Return (body lines, index of the line after the closing delimiter)."""
    if delimiter is None:
        return [], start
    body: list[str] = []
    i = start
    while i < len(lines) and lines[i].strip() != delimiter:
        body.append(lines[i])
        i += 1
    return body, i + 1  # step over the closing delimiter
