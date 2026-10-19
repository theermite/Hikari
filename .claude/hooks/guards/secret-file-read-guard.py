#!/usr/bin/env python3
"""PreToolUse Read|Grep|Bash — no direct read of a file that IS a secret.

Jay 2026-10-18 (review: secrets shown in clear 6-7 times in 48 h): the output filter
(post-tool-secret-redact.py) masks what has a name or a vendor prefix; a secret with neither
slips through. A file whose whole content is a secret (.env, key files, the vault's decrypted
envs and age key, the assistant's and CLI's own tokens) is therefore refused at the door, so its
content never reaches the output at all.

Refused: .env and .env.* (not .example/.sample/.template/.dist, not code or docs that only carry
the name: .d.ts .ts .md .schema.json), *.pem *.key *.p12 *.pfx, id_rsa/id_ed25519/id_ecdsa/id_dsa
(not .pub), .netrc .npmrc .pgpass, ~/.aws/credentials, ~/.claude/.credentials.json, gh hosts.yml,
sops age keys, age-key.txt, *.tokens.env, secrets.json/toml, .secrets, .kube/config,
terraform.tfstate, and the Shinkofa-Vault `envs/` folder. Encrypted sops files stay readable.

Bash is INVERTED (fourth round, 2026-10-18). Two independent reviews in a row found the same
family of holes in a list of display forms to refuse (a glob, a wrapper, a variable, a shell, a
substitution, a pipe into xargs...): a list of forms to refuse is always overtaken by the next form.
So any command that NAMES a secret file is refused, unless the use is on a short CLOSED list:
ls chmod stat test mv cp touch wc source, `echo`/`printf` without command substitution,
`grep -q/-c/-l`, harmless `git` subcommands, and a secret passed as the value of `--env-file`
(`docker compose --env-file .env`, `node --env-file=.env`). A sentence that merely mentions the
name (a commit message, a PR body) is not a use. A search pattern or jq filter is not a path.

`--env-file` only counts as LOADING when the program launched does not print its environment
(docker compose up/build/down yes; run, exec, config, `python -c`, `env` no). A listed use that
feeds another segment which prints its input is refused (`ls .env | xargs cat`, `source .env; env`);
`cp`/`mv` to a standard stream (`/dev/stdout`, `CON`) is not a listed use; `sops -d` and `gpg -d`
print clear text and are refused. An unparsable command that names a secret is refused.

KNOWN LIMITS (fifth round, 2026-10-18; a text guard is never sealed, three reviews proved it):
a script FILE that reads the secret (`python script.py --env .env`), a name built at run time
(`'.'+'env'`), `cp .env x` followed by a read of `x`, a password given as an option
(`-p<value>`), and any program not on the lists that prints a file it was handed through a
variable the guard did not see. Sixth round, named by the fourth review: a recursive search that
never names the file (`grep -rn API_KEY .`), a program that reads the file by itself (`docker compose
config`, `dotenv list`), a glob too short to be told from an ordinary one (`cat .*`), text piped
into a shell or `eval` (`echo "cat .env" | bash`), a program that opens the file by itself (`awk 'BEGIN{getline
l < ".env"}'`), and a program not on the lists that prints a variable (`source .env && curl -v ...`).
Accepted false positives: `docker run -d --env-file .env` (it may print), `*.key` files that are not
keys (`keyboard.key`), a key used as an option (`ssh -i ~/.ssh/id_ed25519`, `curl --key`), a listed
use followed by a reader (`ls -la .env && cat package.json`), and `ssh vps 'ls ~/app/.env'` (a remote
command that names a secret is refused, even a harmless one).
2026-10-19 (four independent reviews, Jay's decision): a substitution INSIDE a message option is not
judged (`git commit -m "$(cat .env)"`, `gh pr create --title "$(head -1 .env)"`) — it would write the
value into git history or send it to GitHub. Three attempts to judge substitutions with patterns each
opened a new hole or blocked ordinary commits; Jay had decided on 2026-10-18 to stop hardening this
text guard. This hole closes with the vault, not here. A multi-line message that NAMES a secret file
in `-m "$(cat <<'EOF' ...)"` is refused; `git commit -F - <<'EOF'` carries it.
Real protection of the secrets belongs to the vault, not to this guard; the output masking and
the all-tools filter stay the backstop.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402
from secret_files import glob_names_a_secret, is_secret_file  # noqa: E402
from shell_parse import simple_commands  # noqa: E402

MESSAGE = (
    "Fichier de secrets : je ne le lis pas en direct ({name}). Les valeurs ne "
    "doivent pas arriver dans la conversation. Passe par le coffre (menu "
    "coffre.cmd) ou demande à Jay de poser la valeur lui-même. Pour connaître "
    "la liste des variables sans leurs valeurs, lis le modèle .env.example. "
    "Pour CHARGER un .env sans l'afficher : docker compose --env-file .env, "
    "node --env-file=.env, ou source .env. Pour un MESSAGE de commit qui cite ce nom : "
    "git commit -F - <<'EOF' (message sur les lignes suivantes, puis EOF)."
)

# -- Bash: a command that NAMES a secret file is refused unless the use is on the closed list -------

_READERS = frozenset(
    "cat tac type head tail less more most bat nl od xxd hexdump strings sed awk gawk grep egrep fgrep rg ag "
    "cut sort uniq tr paste column get-content gc base64 jq yq python python3 py node nodejs ruby perl php "
    "dd diff cmp vim vi nano emacs code ssh-keygen".split()
)
_SEARCHERS = frozenset({"grep", "egrep", "fgrep", "rg", "ag"})
_QUIET_FLAGS = frozenset({"-q", "--quiet", "-c", "--count", "-l", "--files-with-matches", "-L"})
# Programs that run another program: skip them (and their flags) to find what really executes.
_WRAPPERS = frozenset("sudo doas env command builtin busybox nohup nice time exec xargs stdbuf timeout setsid ionice".split())
_WRAPPER_VALUE_FLAGS = frozenset({"-u", "-g", "-h", "-p", "-c", "-n", "-s", "-t", "-a"})
# Programs that run a command held in a string: that string is read again.
_SHELLS = frozenset("bash sh zsh dash powershell pwsh cmd eval".split())
# Programs whose quoted argument is CODE, not prose: a name inside it is a use of the file.
_CODE_CARRIERS = frozenset("python python3 py node nodejs ruby perl php ssh bun deno rscript lua".split())
_INTERPRETERS = frozenset("python python3 py node nodejs ruby perl php".split())
# Closed list of uses that do not display the file. `cp .env x` is one: reading x afterwards is an honest limit.
_USES_ONLY = frozenset("ls dir chmod chown chgrp stat test [ [[ touch rm mv cp ln mkdir wc source .".split())
_STREAM_TARGET = re.compile(r"^(/dev/|/proc/|/sys/|//\./|\\\\\.\\|(con|prn|aux|nul|com\d|lpt\d)$)", re.IGNORECASE)
_GIT_SAFE = frozenset("rm mv restore status check-ignore ls-files reset checkout".split())
# Programs that read their input (or the environment): a listed use FEEDING one of them is a display.
_SPILL = frozenset("xargs tee while for mapfile readarray read".split())
_DECRYPTERS = frozenset("sops gpg gpg2 age".split())
_DECRYPT_WORDS = frozenset({"-d", "--decrypt", "decrypt"})
# grep/rg/jq: the first positional argument is a pattern or a filter, never a path.
_PATTERN_FIRST = _SEARCHERS | {"jq", "yq"}
_PATTERN_VALUE_FLAGS = frozenset({"-A", "-B", "-C", "-m", "-t", "-T", "-g", "--glob", "--type", "--max-count"})
_PATTERN_FLAGS = frozenset({"-e", "--regexp"})  # the value after these IS the pattern
_PATTERN_FILE_FLAGS = frozenset({"-f", "--file"})  # the value is a PATH (the file holds the patterns)
_TEXT_FLAGS = frozenset({"--title", "--body", "--message", "-m", "-am", "-t", "-b", "--subject", "--notes",
                         "--description"})
# Only programs that carry free text take it: `git show -m` and `less -m` are options without a value.
_TEXT_GIT_SUBCOMMANDS = frozenset({"commit", "tag", "merge", "notes"})
_ENV_FLAGS = ("--env-file", "--env", "--dotenv", "--envfile")
_CONTAINER_TOOLS = frozenset("docker docker-compose podman podman-compose".split())
_COMPOSE_LOADERS = frozenset("up build start pull down stop restart create logs ps".split())
_COMPOSE_VERBS = _COMPOSE_LOADERS | {"run", "exec", "config", "convert"}
_EVAL_FLAGS = frozenset({"-c", "-e", "--eval", "--print", "-pe"})
_PRINT_RUNTIMES = frozenset({"node", "nodejs", "bun", "deno", "perl"})  # where `-p` evaluates code and prints it
_CODE_OBJECTS = frozenset({"process.env", "import.meta.env", "deno.env", "bun.env"})  # JS objects, not files
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
_DECLARERS = frozenset({"export", "declare", "local", "readonly", "typeset"})
_VARIABLE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")
_SUBSTITUTION = re.compile(r"\$\(|`|<\(")
_GLOB_CHARS = re.compile(r"[*?\[]")
_PATHISH = re.compile(r"[^\s'\"<>|;&()=,`$]+")
_ANSI_C = re.compile(r"\\x([0-9a-fA-F]{2})")
_CANONICAL_SECRETS = (".env", ".env.local", ".env.production", ".envrc", "id_rsa", "id_ed25519", "id_ecdsa",
                      "server.pem", "server.key", "secrets.json", "credentials.json", ".netrc", ".npmrc",
                      ".pgpass", "kubeconfig", "terraform.tfstate")


def _program(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _glob_hits_a_secret(piece: str) -> bool:
    """`.en?`, `.[e]nv`, `.env*`, `*.pem`: a pattern that can only be a secret file's name."""
    base = piece.replace("\\", "/").rsplit("/", 1)[-1]
    if not _GLOB_CHARS.search(base):
        return False
    literal = _GLOB_CHARS.sub("", base).replace("]", "")
    if len(literal) >= 3 and not base.startswith("*") and any(
            fnmatch.fnmatchcase(name, base.lower()) for name in _CANONICAL_SECRETS):
        return True
    return glob_names_a_secret(piece)


def _spellings(piece: str) -> list[str]:
    """The ways one piece can open a file: as written, after `HEAD:`, with shell escapes undone."""
    decoded = _ANSI_C.sub(lambda m: chr(int(m.group(1), 16)), piece)
    return [piece.lstrip("<"), piece.split(":")[-1], decoded.replace("\\", ""), decoded.replace("\\", "/"),
            piece.rsplit("@", 1)[-1]]  # `curl -d @.env`, `-F file=@id_rsa`, `-d@.env`: a file sent by `@`


def _secret_in(token: str) -> str | None:
    """A secret-file path inside one token (also inside a one-liner's quoted code)."""
    for piece in [token, *_PATHISH.findall(token)]:
        if piece.lower() in _CODE_OBJECTS:
            continue  # `process.env` is a JavaScript object, not a file
        if any(is_secret_file(c) or _glob_hits_a_secret(c) for c in _spellings(piece)):
            return piece
    return None


def _expand(tokens: list[str], variables: dict[str, str]) -> list[str]:
    return [_VARIABLE.sub(lambda m: variables.get(m.group(1), m.group(0)), t) for t in tokens]


def _real_program(seg: list[str]) -> int:
    """Index of the program that really runs: past sudo/env/command/..., their flags and VAR=value."""
    i = 0
    while i < len(seg) and _program(seg[i]) in _WRAPPERS:
        i += 1
        while i < len(seg) and (seg[i].startswith("-") or _ASSIGNMENT.match(seg[i]) or seg[i].isdigit()):
            i += 2 if seg[i] in _WRAPPER_VALUE_FLAGS and not seg[i].startswith("--") else 1
    return i


def _inner_commands(args: list[str]) -> list[str]:
    """The command strings a shell is asked to run: any argument with a space, and `cmd /c type .env`."""
    rest = list(args)
    while rest and rest[0].startswith(("-", "/")):
        rest.pop(0)
    joined = " ".join(rest)
    unquoted = joined.replace('"', "").replace("'", "")  # nested, escaped quotes: `bash -c \"cat .env\"`
    return [a for a in args if " " in a] + ([joined, unquoted] if rest else [])


def _text_flag_values(program: str, args: list[str]) -> set[int]:
    """Values of --title/--body/-m for the programs that carry free text (gh, git commit/tag...)."""
    carries_text = program == "gh" or (program == "git" and _git_subcommand(args) in _TEXT_GIT_SUBCOMMANDS)
    return {i + 1 for i, t in enumerate(args) if carries_text and t in _TEXT_FLAGS}


def _search_pattern_indexes(args: list[str]) -> set[int]:
    """grep/rg/jq: the first positional argument (or the value of -e) is a pattern, never a path."""
    words: set[int] = set()
    seen_pattern, i = False, 0
    while i < len(args):
        tok = args[i]
        if tok in _PATTERN_FLAGS:
            words.add(i + 1)
            seen_pattern = True
        elif tok in _PATTERN_FILE_FLAGS:
            seen_pattern = True  # `grep -f pats file`: no positional pattern, and `pats` stays a path
        elif not tok.startswith("-") and not seen_pattern:
            words.add(i)
            seen_pattern = True
        i += 2 if tok in _PATTERN_FLAGS or tok in _PATTERN_VALUE_FLAGS else 1
    return words


def _pattern_indexes(program: str, args: list[str]) -> set[int]:
    """Indexes that are a search pattern, a jq filter or a free-text flag value: words, not paths."""
    words = _text_flag_values(program, args)
    return words | _search_pattern_indexes(args) if program in _PATTERN_FIRST else words


def _loads_without_printing(program: str, args: list[str]) -> bool:
    """`--env-file` loads a file; it is only that if the program launched does not print its environment."""
    if program in _CONTAINER_TOOLS:
        verb = next((t for t in args if t in _COMPOSE_VERBS), None)
        return verb in _COMPOSE_LOADERS
    if any(t in _EVAL_FLAGS for t in args):
        return False
    if "-p" in args and ({program} | set(args)) & _PRINT_RUNTIMES:
        return False  # `node -p process.env` prints the environment that --env-file just loaded
    return not any(_program(t) in ("env", "printenv", "set") for t in args if not t.startswith("-"))


def _env_flag_values(program: str, args: list[str]) -> set[int]:
    """Indexes of the arguments that are the value of --env-file (when that really only loads)."""
    if not _loads_without_printing(program, args):
        return set()
    return {i for i, tok in enumerate(args)
            if tok.startswith(tuple(f + "=" for f in _ENV_FLAGS)) or (i and args[i - 1] in _ENV_FLAGS)}


def _git_subcommand(args: list[str]) -> str:
    rest = list(args)
    while rest and rest[0] in ("-C", "-c"):
        rest = rest[2:]
    return rest[0] if rest else ""


def _is_a_listed_use(program: str, args: list[str], has_substitution: bool) -> bool:
    """True when this program, on this file, does not display it (the closed list)."""
    if program in ("cp", "mv", "ln") and any(_STREAM_TARGET.match(t) for t in args):
        return False  # `cp .env /dev/stdout` displays it in one step
    if program in _USES_ONLY:
        return True
    if program in ("echo", "printf"):
        return not has_substitution
    if program in _SEARCHERS:
        return any(t in _QUIET_FLAGS for t in args)
    return program == "git" and _git_subcommand(args) in _GIT_SAFE


def _is_prose(token: str, program: str) -> bool:
    """A sentence (commit message, PR body) that merely cites the name; code and substitutions are not prose."""
    if " " not in token or program in _CODE_CARRIERS or _SUBSTITUTION.search(token):
        return False
    # `"D:/My Projects/app/.env"` is a path with a space; `"cat .env.local"` handed to a container is a
    # command. A sentence that merely cites the name is told apart by the programs that carry free text.
    return not is_secret_file(token) and _secret_in(token) is None


def _unlisted_mention(program: str, args: list[str]) -> str | None:
    """The first secret this call names outside a loaded --env-file value, a pattern or plain prose."""
    skip = _env_flag_values(program, args) | _pattern_indexes(program, args)
    for i, tok in enumerate(args):
        if i in skip or _is_prose(tok, program):
            continue
        hit = _secret_in(tok)
        if hit:
            return hit
    return None


def _strip_redirections(seg: list[str]) -> list[str]:
    """`< .env prog`: keep the file as an argument of the program that follows."""
    while len(seg) > 2 and seg[0] == "<":
        seg = seg[2:] + [seg[1]]
    return seg


def _inside_a_shell(args: list[str], depth: int) -> str | None:
    for inner in _inner_commands(args):
        hit = _bash_secret_read(inner, depth + 1)
        if hit:
            return hit
    return None


def _dumps_environment(seg: list[str]) -> bool:
    """`env`, `printenv`, `set`, `export -p`: prints what a previous `source .env` loaded."""
    prog, rest = _program(seg[0]), seg[1:]
    if prog == "printenv":
        return True
    if prog in ("env", "set"):
        return not rest
    return prog in ("export", "declare", "typeset") and all(t in ("-p", "-x", "-xp", "-px") for t in rest)


def _shows_a_variable(program: str, args: list[str]) -> bool:
    """`echo $DB_PASSWORD` after a `source .env`: prints one variable the file just loaded."""
    return program in ("echo", "printf") and any("$" in a for a in args)


def _prints_its_input(program: str, args: list[str]) -> bool:
    """A reader prints what it is fed; an interpreter only does with code on the command line (-c, -e)."""
    if program in _INTERPRETERS:
        return any(t in _EVAL_FLAGS for t in args)
    return program in _READERS


def _spills(seg: list[str], program: str, args: list[str]) -> bool:
    """True when this segment prints what it is fed (a reader, an env dump)."""
    return _dumps_environment(seg) or _program(seg[0]) in _SPILL or _prints_its_input(program, args)


def _is_sentence_only(program: str, args: list[str]) -> bool:
    """`echo "copy .env.example to .env"`: every mention sits inside a sentence, nothing is shown of the file."""
    return program in ("echo", "printf") and all(" " in t or _secret_in(t) is None for t in args)


def _is_harmless_sentence(wrapped: str | None, program: str, args: list[str], has_substitution: bool) -> bool:
    """An `echo` whose mentions are all inside sentences, with no flag value and no substitution to run."""
    return not wrapped and not has_substitution and _is_sentence_only(program, args)


def _decrypts(program: str, args: list[str]) -> bool:
    """`sops -d` / `gpg -d` print the clear text of an encrypted file."""
    return program in _DECRYPTERS and any(t in _DECRYPT_WORDS for t in args)


def _verdict(seg: list[str], i: int, has_substitution: bool) -> tuple[str | None, bool]:
    """(refused secret or None, a listed use named a secret) for the program that really runs at seg[i]."""
    program, args = _program(seg[i]), seg[i + 1:]
    if _decrypts(program, args):
        return "fichier chiffré", False
    wrapped = next((h for h in map(_secret_in, seg[1:i]) if h), None)  # `xargs -a .env`: a flag's value
    hit = wrapped or _unlisted_mention(program, args)
    if hit is None or _is_harmless_sentence(wrapped, program, args, has_substitution):
        return None, False
    listed = not wrapped and _is_a_listed_use(program, args, has_substitution)
    return (None, True) if listed else (hit, False)


def _judge(seg: list[str], has_substitution: bool, depth: int) -> tuple[str | None, bool, bool]:
    """(refused secret or None, a listed use named a secret, this segment spills its input)."""
    seg = _strip_redirections(seg)
    i = _real_program(seg)
    if i >= len(seg):  # only wrappers: `env`, `sudo`
        return None, False, _dumps_environment(seg) or _program(seg[0]) in _SPILL
    program, args = _program(seg[i]), seg[i + 1:]
    spills = _spills(seg, program, args)
    if program in _SHELLS and depth < 3:
        return _inside_a_shell(args, depth), False, spills
    hit, listed = _verdict(seg, i, has_substitution)
    return hit, listed, spills


def _assignments(seg: list[str], variables: dict[str, str]) -> bool:
    """Record `F=.env` / `export F=.env`; True when the segment held nothing else."""
    rest = seg[1:] if seg and seg[0] in _DECLARERS else seg
    if not rest or not all(_ASSIGNMENT.match(t) for t in rest):
        return False
    for t in rest:
        name, _, value = t.partition("=")
        variables[name] = value
    return True


def _bash_secret_read(command: str, depth: int = 0) -> str | None:
    try:
        segments = simple_commands(command)
    except ValueError:  # unparsable: a command we cannot read that names a secret file is refused
        return _secret_in(command)
    return _scan_segments(segments, "$(" in command or "`" in command, depth)


class _Findings:
    """What the segments of one command add up to, once each was judged alone."""

    def __init__(self) -> None:
        self.listed = self.spill = self.loaded = self.shows = False

    def add(self, seg: list[str], listed: bool, spills: bool) -> None:
        self.listed = self.listed or listed
        self.spill = self.spill or (spills and not listed)
        self.loaded = self.loaded or (listed and _program(seg[0]) in ("source", "."))
        self.shows = self.shows or _shows_a_variable(_program(seg[0]), seg[1:])

    def leaks(self) -> bool:
        """`ls .env | xargs cat`, `source .env; env`: a listed use feeding ANOTHER segment that prints its input;
        `source .env; echo $TOKEN`: one variable the loaded file set."""
        return (self.listed and self.spill) or (self.loaded and self.shows)


def _scan_segments(segments: list[list[str]], has_substitution: bool, depth: int) -> str | None:
    variables: dict[str, str] = {}
    found = _Findings()
    for seg in segments:
        if not seg or _assignments(seg, variables):
            continue
        seg = _expand(seg, variables)
        hit, listed, spills = _judge(seg, has_substitution, depth)
        if hit:
            return hit
        found.add(seg, listed, spills)
    return "le fichier cité" if found.leaks() else None


def _refused_target(tool, inp: dict) -> str | None:
    """What the call aims at, if it is a secret file; None otherwise."""
    if tool == "Bash":
        command = inp.get("command")
        return _bash_secret_read(command) if isinstance(command, str) else None
    if tool == "Read":
        candidates = [(inp.get("file_path"), is_secret_file)]
    elif tool == "Grep":
        candidates = [(inp.get("path"), is_secret_file), (inp.get("glob"), glob_names_a_secret)]
    else:
        return None
    for value, test in candidates:
        if isinstance(value, str) and test(value):
            return value.replace("\\", "/").rsplit("/", 1)[-1]
    return None


def main() -> None:
    _, data = read_hook_input()
    inp = data.get("tool_input") if isinstance(data, dict) else None
    if not isinstance(inp, dict):
        pass_through()
    name = _refused_target(data.get("tool_name"), inp)
    if name is not None:
        block(MESSAGE.format(name=name.replace("\\", "/").rsplit("/", 1)[-1]))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a read
        print(f"[secret-file-read-guard] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
