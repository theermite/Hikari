#!/usr/bin/env python3
"""PreToolUse Bash — rewrite suspicious commands to mask secrets in OUTPUT.

Origin: docs/Briefs/Hook-Masquage-Secrets-Sorties-Bash-2026-08-30.md. Two real
commands leaked production secrets in clear text the same evening (Incident
A: `${VAR:+..}${VAR:-..}` glue ; Incident B: `docker compose config` resolves
`.env` values). Nothing inspected command OUTPUT — only command TEXT.

Why a PreToolUse rewrite, not a PostToolUse filter (verified 2026-08-30 on
this Claude Code build): a PostToolUse hook's `updatedToolOutput` is ignored
here — the real output reaches the model untouched even when the hook
returns it. `updatedInput` on PreToolUse IS honored (tested live: a rewritten
command actually runs instead of the original). So the mask has to be baked
into the COMMAND before it runs, by piping its combined output through the
shared masker (lib/secret_mask.py).

RECOVERY PRINCIPLE: this hook never blocks. It masks, it does not forbid —
the sortie is already produced when a hook could see it; blocking protects
nothing and breaks the work (brief §3).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import common  # noqa: E402

_FILTER_MARKER = "secret_mask.py"

# The absolute path is already known via `__file__` — no need to shell out to
# `git rev-parse --show-toplevel` to find it. Independent review 2026-08-31
# round 5, proven by real execution: outside a git repository that command
# fails, the filter path resolves to garbage, and the original command's
# output silently disappears (exit code still 0 — looks like a success with
# no output, not an error). Forward slashes: this path is interpolated into
# a Bash command string, and Git Bash on Windows accepts them directly.
_FILTER_ABS_PATH = str(
    (Path(__file__).resolve().parent.parent / "lib" / _FILTER_MARKER)
).replace("\\", "/")

# Anchors the *wrapped* form so the double-wrap guard can tell "this command
# WAS wrapped" from "this command merely mentions the filter's path" (e.g. it
# `cat`s the hook file itself). Independent review 2026-08-31 found the
# double-wrap guard matching that free substring turned suspicious commands
# invisible to wrapping the moment they happened to mention it — a `docker
# exec ... cat .../secret_mask.py .../.env` leaked its `.env` unmasked.
_WRAPPED_PREFIX = "# __secret_mask_wrapped__\n"

# Commands that can surface a secret in their OUTPUT: containers, a remote
# host, environment dumps, config files, cloud/secret-store CLIs. Not every
# command — wrapping every Bash call would be exactly the kind of
# brittleness that caused the leak.
# `docker[-_]?\s*compose` (not `[-_ ]`, one char only) tolerates the hyphen
# form (`docker-compose`) AND multiple spaces/tabs between two words — a
# fixed single-char class matched neither a double space nor a tab
# (independent review 2026-08-31 round 2).
_COMPOSE = r"\bdocker[-_]?\s*compose\b"

_SUSPICIOUS_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bdocker\s+exec\b",
        rf"{_COMPOSE}.*\bconfig\b",
        rf"{_COMPOSE}.*\blogs\b",
        r"\bdocker\s+logs\b",
        r"\bdocker\s+inspect\b",
        r"\bssh\s+\S+.*\b(docker|env|printenv)\b",
        r"\bprintenv\b",
        r"\benv\b",
        r"\bcat\s+\S*\.env\S*",
        r"\bcat\s+\S*\.(pem|key)\b",
        r"\bid_rsa\b",
        r"\bkubectl\s+get\s+secret\b",
        r"\bkubectl\s+exec\b",
        r"\bsecretsmanager\s+get-secret-value\b",
        r"\bvault\s+kv\s+get\b",
        r"\bheroku\s+config\b",
        # `curl -v`/`-i`/`--verbose`/`--include` prints request/response
        # headers — the most common real-world way an `Authorization:
        # Bearer <token>` header ends up in a command's output. Found
        # entirely absent from this list, independent review 2026-08-31
        # round 8, alongside the header-name blind spot it fixed.
        r"\bcurl\b.*\s(-v|-i|--verbose|--include)(\s|$)",
    )
)
# Independent review 2026-08-31 round 2, proven exploitable on this Windows
# box: NTFS resolves an executable's case insensitively (`DOCKER exec ...`
# actually runs), so every pattern above is case-insensitive — a
# capitalized command is not a hypothetical, it is a command that runs.


def is_suspicious(command: str) -> bool:
    return any(p.search(command) for p in _SUSPICIOUS_PATTERNS)


# A `>`/`>>`/`&>`/`2>` that targets a FILE consumes the command's own output
# before our outer `2>&1 | filter` pipe ever sees it — the secret lands on
# disk in clear, unmasked, and the PostToolUse alert net cannot warn either
# (its `tool_response.stdout/stderr` is empty too). Independent review
# 2026-08-31 round 3, proven by real execution. This is a PRE-EXISTING
# architectural blind spot (verified: identical with or without wrapping —
# no hook that only sees the Bash tool's own stdout/stderr channel can ever
# observe output a command redirected straight to a file), not something a
# regex can close. `(?!&)` excludes fd duplication (`2>&1`, `>&2`): no file
# is involved there, nothing is lost.
_FILE_REDIRECT_RE = re.compile(r"(?<!\d)(?:[12]?>{1,2}|&>{1,2})(?!&)")


def has_own_redirection(command: str) -> bool:
    return bool(_FILE_REDIRECT_RE.search(command))


def wrap_command(command: str) -> str:
    """Pipe `command`'s combined stdout+stderr through the masker.

    `${PIPESTATUS[0]}` preserves the ORIGINAL command's exit code — the
    pipeline's own exit code would otherwise be the filter's (always 0).
    """
    if command.startswith(_WRAPPED_PREFIX):
        return command  # already wrapped, do not nest
    return (
        f"{_WRAPPED_PREFIX}"
        f"( {command} ) 2>&1 | "
        f'python3 "{_FILTER_ABS_PATH}" --filter; '
        f"exit ${{PIPESTATUS[0]}}"
    )


def build_decision(data: dict) -> dict | None:
    command = common.get_command(data)
    if not command or not is_suspicious(command):
        return None
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {"command": wrap_command(command)},
        }
    }
    if has_own_redirection(command):
        # Wrapping still runs (harmless), but it cannot mask what this
        # command already redirects to a file — say so instead of implying
        # protection that cannot exist here.
        output["hookSpecificOutput"]["additionalContext"] = (
            "WARNING: this command already redirects its own output to a "
            "file — that content bypasses masking entirely (it never "
            "reaches this conversation to be filtered). If it contains a "
            "secret, treat the target file as unmasked clear text: check "
            "it directly and rotate the credential if needed."
        )
    return output


def main() -> None:
    _, data = common.read_hook_input()
    decision = build_decision(data)
    if decision is not None:
        print(__import__("json").dumps(decision))
    sys.exit(0)


if __name__ == "__main__":
    main()
