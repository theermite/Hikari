"""What a Bash command that only prints text says (the 'echo' channel of transcript_reader)."""

from __future__ import annotations

import shlex

_SHELL_PUNCTUATION = set("();<>|&")


def _unquoted_newline(command: str) -> bool:
    """A line break outside quotes ends the command: what follows is another one."""
    quote = ""
    escaped = False
    for ch in command.strip():
        if escaped:
            escaped = False
        elif ch == chr(92) and quote != "'":
            escaped = True
        elif quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in (chr(13), chr(10)):
            return True
    return False


def echoed_text(command) -> str:
    """What a Bash command that is ONLY `echo <text>` / `printf '%s\n' <text>` prints, else "".

    A tool call is always recorded, while the text of its message may be lost (brief 2026-10-30), and
    the permission classifier had refused the said-file as a workaround. Anything but a lone print is
    not speech: a chained command, a pipe, a redirection, a substitution, an unterminated quote.
    """
    if not isinstance(command, str) or "$(" in command or "`" in command:
        return ""
    if _unquoted_newline(command):
        return ""
    lexer = shlex.shlex(command.strip(), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return ""
    if len(tokens) < 2 or any(set(t) <= _SHELL_PUNCTUATION for t in tokens):
        return ""
    if tokens[0] == "echo":
        return "\n".join(tokens[1:])
    if tokens[0] == "printf" and tokens[1] in ("%s" + chr(92) + "n", "%s" + chr(10)):
        return chr(10).join(tokens[2:])
    return ""
