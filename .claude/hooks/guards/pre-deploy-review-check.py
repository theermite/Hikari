#!/usr/bin/env python3
"""Independent review gate — PreToolUse Bash, blocking.

Enforces rules/Independent-Review.md: nothing ships until a context that did NOT
write the code has read it and given a verdict.

Why here and not at every commit (Jay 2026-08-10): reviewing each commit costs
more than it saves; shipping unreviewed code is what actually hurts. So the gate
sits where the damage becomes public — a deploy, or a propagation to every repo.

Trigger
-------
A Bash command that looks like a deploy (same detection as the other pre-deploy
guards) OR a methodology propagation (`propagate-methodology.py`, `sync-repo`),
because sending to ~30 repos multiplies a defect exactly like a deploy does.

Accepted evidence, emitted in the conversation before the deploy:

  [REVIEW] par <relecteur> le <YYYY-MM-DD> — verdict: <PASS|FAIL>, <ce qui en est sorti>
  [REVIEW-SKIP] motif: <closed enum>

A sentence claiming a review happened is NOT evidence: the marker is falsifiable,
the claim is not (Rule-Format.md — ask for an artefact, never a self-attestation).

Exit codes: 0 = pass · 2 = block (stderr message printed).

Source: Jay 2026-08-10, after three independent reviews caught eight real defects
in one evening — every one of them before the code shipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    get_command,
    looks_like_deploy,
    pass_through,
    read_hook_input,
)
from shell_parse import simple_commands  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402

# Legitimate reasons to ship without a fresh pair of eyes. Closed on purpose: an
# open motif field becomes "pas le temps" within a week.
SKIP_MOTIFS = (
    "rollback",  # going back to a state already reviewed and shipped
    "hotfix-production-down",  # service is down; review follows immediately after
    "no-code-change",  # docs, content or config only, no executable change
    "review-already-done",  # same diff already reviewed earlier in this session
)

_MARKER = re.compile(
    r"\[REVIEW\]\s+par\s+(?P<reviewer>[^\n]+?)\s+le\s+(?P<date>\d{4}-\d{2}-\d{2})"
    r"[^\n]*?verdict\s*:\s*(?P<verdict>PASS|FAIL)",
    re.IGNORECASE,
)
_SKIP = re.compile(r"\[REVIEW-SKIP\]\s+motif\s*:\s*(?P<motif>[a-z0-9-]+)", re.IGNORECASE)

# Shipping is not only a deploy: pushing and publishing put code in front of
# others just as irreversibly (independent review, 2026-08-10).
# An ordinary `git push` is NOT here (Jay 2026-08-11): a branch push is
# reversible, and gating every push would cost a review several times a day —
# the friction would kill the rule. What stays gated cannot be taken back.
_PROPAGATION = re.compile(
    r"npm\s+publish|pnpm\s+publish|yarn\s+publish|twine\s+upload|"
    r"cargo\s+publish|mix\s+hex\.publish",
    re.IGNORECASE,
)

# The propagation script counts when it is RUN, never when it is read. A token
# that ENDS with the script name is a path being executed; a `python -c` blob
# merely quoting the name is not (false stop, 2026-08-11).
_PROPAGATION_SCRIPTS = ("propagate-methodology.py", "sync-repo.sh", "sync-repo.py")


_EXECUTORS = {"python", "python3", "py", "bash", "sh", "zsh"}


def _names_a_propagation_script(token):
    cleaned = token.replace("\\", "/")
    return any(cleaned.endswith(script) for script in _PROPAGATION_SCRIPTS)


def _runs_a_propagation(segment):
    """The script is RUN, not merely named. `ruff check <script>` reads it."""
    program = _program_name(segment[0])
    if program not in _EXECUTORS and not _names_a_propagation_script(segment[0]):
        return False
    # `python -m ruff <script>` runs ruff; `python -c <code>` runs the code. In
    # both, the script named after is an argument being read, not executed.
    if "-m" in segment or "-c" in segment:
        return False
    return any(_names_a_propagation_script(token) for token in segment)

_FORCE_FLAGS = {"--force", "--force-with-lease", "-f"}


def _is_forced_push(segment):
    """A forced push, read from tokens — `git -C <path> push --force` included.

    A regex on the raw line missed exactly that form, which is how another repo
    gets pushed from here (independent review, 2026-08-11). Tokens also keep a
    `-f` quoted inside a message from counting as a flag.
    """
    if _program_name(segment[0]) != "git" or "push" not in segment:
        return False
    return any(token in _FORCE_FLAGS for token in segment)


def _program_name(token):
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()

TRANSCRIPT_LOOKBACK = 30


_CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)


def _spoken(text):
    """Text minus code samples: quoting the format is not doing the review."""
    return _CODE.sub(" ", text or "")


def find_marker(text):
    """Return the review marker match, or None when the evidence is incomplete."""
    return _MARKER.search(_spoken(text))


def find_skip(text):
    """Return the skip match only when its motif is in the closed list."""
    match = _SKIP.search(_spoken(text))
    if match and match.group("motif").lower() in SKIP_MOTIFS:
        return match
    return None


# What the reviewer was GIVEN, not only what it returned (Jay 2026-08-30).
#
# The audit of that day found nothing governed the LAUNCH: this gate checked
# that a verdict appeared afterwards, while the prompt handed to the reviewer was
# improvised each time. A reviewer with no objective can only check that the code
# agrees with itself -- exactly the bias Jay reported ("il ne prend pas en compte
# l'objectif et/ou la vision du projet, ce qui lui donne un point de vue biaise").
BRIEF_FIELDS = ("objectif", "perimetre", "zones suspectes", "consigne")

# `consigne` is a closed value, not free text: a reviewer told to CHECK confirms,
# a reviewer told to REFUTE finds. On 2026-08-10, "contredis ce code" produced 8
# findings where "relis ce code" produced a summary.
_REFUTE = re.compile(r"r[ée]fut|contredi|refuter", re.IGNORECASE)


def _brief_field(text, field):
    """The value written on the field's own line, or '' when absent/empty."""
    pattern = re.compile(
        rf"-[^\S\n]*{re.escape(field)}[^\S\n]*:[^\S\n]*(\S[^\n]*)", re.IGNORECASE
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def find_brief(text):
    """Return the launch brief when it is complete, else None.

    Complete means the four fields carry a value AND `consigne` asks for
    refutation. A brief quoted as an example is not a brief that happened, so
    code samples are stripped first -- same rule as the verdict marker.
    """
    spoken = _spoken(text)
    if "[REVIEW-BRIEF]" not in spoken:
        return None
    values = {field: _brief_field(spoken, field) for field in BRIEF_FIELDS}
    if not all(values.values()):
        return None
    if not _REFUTE.search(values["consigne"]):
        return None
    return values


def _was_briefed(recent_texts, index):
    """True when the verdict at `index` had a brief of its own.

    Texts arrive most recent first, so a brief written BEFORE the verdict sits
    AFTER it in the list. Two boundaries make the brief belong to THIS review:

    - the verdict's own message counts, since the brief may sit above it there;
    - the walk stops at an older PASS, which closed a previous review cycle. A
      FAIL does not stop it: the same launch is still open, and re-emitting four
      lines on every corrective round is friction with no added truth.

    Without this, review #1's brief would excuse review #2, improvised.
    """
    if find_brief(recent_texts[index]):
        return True
    for text in recent_texts[index + 1 :]:
        if find_brief(text):
            return True
        older = find_marker(text)
        if older and older.group("verdict").upper() == "PASS":
            return False
    return False


def _missing_brief_message():
    fields = " · ".join(f"- {name}: <...>" for name in BRIEF_FIELDS)
    return (
        "BLOCKED: the review passed, but nothing says what the reviewer was GIVEN. "
        "RECOVERY: before launching the reviewer, emit '[REVIEW-BRIEF]' then four "
        f"lines — {fields} — where `consigne` asks to REFUTE, never to validate. "
        "Then relaunch the review and emit its verdict. "
        "Why: a reviewer without the project's goal can only check that the code "
        "agrees with itself, which is the bias Jay reported on 2026-08-30. And "
        "'contredis ce code' produced 8 findings where 'relis ce code' produced a "
        "summary (2026-08-10)."
    )


# A heredoc delimiter always carries a letter (EOF, PY, SQL). Requiring one keeps
# an arithmetic shift — `$((5 << 2))` — from being read as a heredoc.
# These read a file or print an argument; they never run it. Everything else that
# carries a quoted command — `bash -c`, `sh -c`, `ssh <host>` — does run it.
# Blocking a `grep` over the propagation script is a false stop (2026-08-11), and
# a guard that fires on reading is a guard people learn to work around.
_PRINTERS = {
    "echo", "print", "printf",
    "cat", "grep", "rg", "head", "tail", "less", "more", "sed", "awk", "nl",
    "sort", "uniq", "cut", "tr", "jq", "ls", "wc", "diff", "find", "stat",
    "file", "basename", "dirname", "realpath",
}


_SUBSTITUTION = re.compile(r"\$\(|`")


# `find -exec <command>` runs whatever follows. A reader that can execute is not
# a reader (independent review, 2026-08-11).
_RUNS_WHAT_FOLLOWS = {"-exec", "-execdir", "-ok", "-okdir"}


def _after_exec_flag(segment):
    """The command `find -exec` hands to the shell, as its own segment.

    `{}` stands for the matched files, so the search terms travel with it —
    otherwise `find -name deploy.sh -exec bash {} ;` looks like a bare `bash`.
    """
    for i, token in enumerate(segment):
        if token in _RUNS_WHAT_FOLLOWS and i + 1 < len(segment):
            command = [t for t in segment[i + 1 :] if t not in ("{}", ";", "\\", "+")]
            matched = [t for t in segment[:i] if not t.startswith("-")]
            return command + matched
    return None


def _ships(segment, printers_are_safe=True):
    nested = _after_exec_flag(segment)
    if nested is not None:
        # The search itself ships nothing; only what it runs can. Judging the raw
        # line as well would block `find -name deploy.sh -exec cat {} ;` — reading
        # a file is not running it (independent review, 2026-08-11).
        return _ships(nested, printers_are_safe)
    if segment[0] in _PRINTERS and printers_are_safe:
        return False
    if _is_forced_push(segment) or _runs_a_propagation(segment):
        return True
    text = " ".join(segment)
    return looks_like_deploy(text) or bool(_PROPAGATION.search(text))


def _is_gated(command):
    """True when any real command in the line ships something.

    Reads shell tokens rather than raw text: a `<<` or a deploy verb sitting
    inside a quoted string is data, while `bash -c 'git push'` is an action.
    Unparseable input is inspected raw — a typo must not switch the gate off.
    """
    try:
        segments = simple_commands(command)
    except ValueError:
        segments = [[command or ""]]  # fail closed
    # `echo 'ne fais jamais git push'` is a sentence. `echo $(git push)` runs it:
    # the substitution executes before the printing does (4th review, 2026-08-10).
    printers_are_safe = not _SUBSTITUTION.search(command or "")
    return any(_ships(segment, printers_are_safe) for segment in segments)


def _block_message(command):
    motifs = " | ".join(SKIP_MOTIFS)
    return (
        "BLOCKED: shipping without an independent review. "
        f"COMMAND: {command.strip()[:120]}. "
        "RECOVERY: have a context that did NOT write this code read the diff "
        "(a sub-agent with a fresh memory, or another model), then emit: "
        "'[REVIEW] par <relecteur> le <YYYY-MM-DD> - verdict: <PASS|FAIL>, "
        "<ce qui en est sorti>' and retry. "
        f"Legitimate skip: '[REVIEW-SKIP] motif: <{motifs}>'. "
        "Why: on 2026-08-10, three reviews caught eight real defects, each one "
        "before it shipped. A sentence saying 'I checked' is not evidence."
    )


def verdict(command, recent_texts):
    """Return a block message, or None when the command may proceed.

    Texts arrive most recent first, so the latest verdict wins: a FAIL blocks
    until a later review says PASS. Checking only that a marker EXISTS would let
    "verdict: FAIL, 5 defauts bloquants" ship (independent review, 2026-08-10).
    """
    if not _is_gated(command):
        return None
    for index, text in enumerate(recent_texts):
        if find_skip(text):
            return None
        marker = find_marker(text)
        if marker:
            if marker.group("verdict").upper() == "PASS":
                if _was_briefed(recent_texts, index):
                    return None
                return _missing_brief_message()
            return (
                "BLOCKED: the last independent review came back FAIL and nothing "
                "says it was resolved. "
                f"VERDICT READ: {marker.group(0).strip()[:160]}. "
                "RECOVERY: fix what the review found, have it re-read, then emit a "
                "new '[REVIEW] ... verdict: PASS, <ce qui a change>' and retry."
            )
    return _block_message(command)


def main():
    _raw, data = read_hook_input()
    command = get_command(data)
    if not _is_gated(command):
        pass_through()  # most Bash calls ship nothing: do not read the transcript

    transcript = data.get("transcript_path", "")
    texts = list(iter_assistant_text(transcript, limit=TRANSCRIPT_LOOKBACK)) if transcript else []

    message = verdict(command, texts)
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    main()
