#!/usr/bin/env python3
"""A failed review must teach — PreToolUse Bash on `git commit`.

Why this hook exists
--------------------
On 2026-08-10, five independent reviews in a row rejected the same family of
defect. Each time the fix addressed the case that was reported, never the cause;
the family reopened one bypass later. Jay named the real failure: "le problème
n'est pas que tu aies fait une erreur, c'est que tu as persévéré dans cette
erreur. Dès que l'erreur est détectée, il faut prendre du recul pour savoir d'où
elle vient, la corriger, et mettre en place quelque chose qui fera qu'elle n'est
pas reproduite."

So a FAIL verdict is not a warning to note in passing. It opens an obligation
that the next commit has to discharge.

What is required
----------------
After a review came back FAIL, the next commit message carries:

  [CAUSE]
  - famille: <the CLASS of defect, not the single case>
  - cause: <where it comes from>
  - ce qui empeche la repetition: <test, shared component, gate — an artefact>

At the SECOND consecutive FAIL, that is no longer enough: patching the reported
case is forbidden, and the message must also carry

  - approche changee: oui — <what is structurally different now>

because a family that survives one correction will survive the next one of the
same shape. Two failures say the approach is wrong, not the line.

Honest limits (independent review, 2026-08-10)
----------------------------------------------
- No transcript, or a verdict written inside a code block: the hook sees no FAIL
  and lets the commit through. Accepted, not hidden — the gate is an aid to
  stepping back, never a proof that stepping back happened.
- Three filled lines are not three TRUE lines: nothing checks that the family is
  named honestly. Jay stays the last verifier (Quality.md A9).
- A FAIL older than the last 40 assistant messages falls out of view.

Hook exit codes: 0 = pass · 2 = block (stderr message printed).

Source: Jay 2026-08-10. Pairs with rules/Independent-Review.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import (  # noqa: E402
    block,
    get_command,
    pass_through,
    read_hook_input,
)
from shell_parse import simple_commands  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402

# These name a command, they never run it.
_PRINTERS = {"echo", "print", "printf"}

TRANSCRIPT_LOOKBACK = 40

# Commits worth excusing: the work has nothing to do with what the review found.
# Closed list — an open motif field becomes "pas envie" within a week.
SKIP_MOTIFS = (
    "sans-rapport",  # this commit touches another subject entirely
    "revert",  # going back to a state that was fine
    "wip-sauvegarde",  # checkpoint commit, the cause work is still in progress
)

_SKIP = re.compile(r"\[CAUSE-SKIP\][^\S\n]*motif[^\S\n]*:[^\S\n]*([a-z0-9-]+)", re.IGNORECASE)
_VERDICT = re.compile(r"\[REVIEW\][^\n]*?verdict\s*:\s*(PASS|FAIL)", re.IGNORECASE)
_CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)

_FIELDS = ("famille", "cause", "ce qui empeche la repetition")
_APPROACH = re.compile(r"-\s*approche\s+chang\w+\s*:\s*oui\s*[—-]\s*\S+", re.IGNORECASE)


def is_commit(command):
    """True when a real `git commit` runs — not a sentence naming one.

    Reads shell tokens (lib/shell_parse.py). Writing this detection by hand is
    the family of defect that cost five review rounds on 2026-08-10; the shared
    parser exists precisely so it is never written by hand again.
    """
    try:
        segments = simple_commands(command)
    except ValueError:
        segments = [[command or ""]]  # fail closed
    for segment in segments:
        if segment[0] in _PRINTERS:
            continue
        if "git" in _program_names(segment) and "commit" in segment:
            return True
    return False


def _program_names(segment):
    return {token.replace("\\", "/").rsplit("/", 1)[-1].lower() for token in segment}


def find_skip(message):
    """Return the skip match only when its motif is in the closed list."""
    match = _SKIP.search(message or "")
    if match and match.group(1).lower() in SKIP_MOTIFS:
        return match
    return None


def _spoken(text):
    return _CODE.sub(" ", text or "")


def last_verdict(recent_texts):
    """PASS, FAIL, or None — the most recent review verdict spoken in chat."""
    for text in recent_texts:
        match = _VERDICT.search(_spoken(text))
        if match:
            return match.group(1).upper()
    return None


def _field_filled(message, field):
    # Horizontal space only: a value must sit on the field's own line, otherwise
    # an empty `- famille:` would borrow the next line's text as its answer.
    pattern = re.compile(rf"-[^\S\n]*{re.escape(field)}[^\S\n]*:[^\S\n]*(\S.*)", re.IGNORECASE)
    match = pattern.search(message)
    return bool(match and match.group(1).strip())


def find_cause(message):
    """Return the message when it carries a complete [CAUSE] block, else None."""
    if "[CAUSE]" not in (message or ""):
        return None
    if all(_field_filled(message, field) for field in _FIELDS):
        return message
    return None


def _missing_cause_message():
    return (
        "BLOCKED: the last independent review came back FAIL, and this commit does "
        "not say what it taught. "
        "RECOVERY: add to the commit message: '[CAUSE]' then three lines — "
        "'- famille: <la CLASSE du defaut, pas le cas signale>', "
        "'- cause: <d'ou il vient>', "
        "'- ce qui empeche la repetition: <test, composant partage, garde-fou>'. "
        "Why: on 2026-08-10, five reviews in a row rejected the same family, "
        "because each fix addressed the reported case and never the cause."
    )


def _second_failure_message():
    return (
        "BLOCKED: second review failure in a row — patching the reported case is no "
        "longer the answer. "
        "RECOVERY: step back and change the APPROACH, then write the [CAUSE] block "
        "('- famille:', '- cause:', '- ce qui empeche la repetition:') plus "
        "'- approche changee: oui — <ce qui est structurellement different>'. "
        "Why: a famille that survived one correction survives the next one of the "
        "same shape (Jay 2026-08-10). Two failures say the design is wrong, not the "
        "line. If you believe the approach is right, say so to Jay and let him "
        "decide — do not spend a third round."
    )


def verdict(commit_message, recent_texts, failures):
    """Return a block message, or None when the commit may proceed."""
    if last_verdict(recent_texts) != "FAIL":
        return None
    # Twice in a row, the demand is higher: the approach has to move, not the line.
    # No excuse holds here — a second failure is about the design, not this commit.
    if failures >= 2:
        return None if _APPROACH.search(commit_message or "") else _second_failure_message()
    if find_skip(commit_message):
        return None
    if not find_cause(commit_message):
        return _missing_cause_message()
    return None


def _count_failures(recent_texts):
    """How many FAIL verdicts in a row, most recent first."""
    failures = 0
    for text in recent_texts:
        match = _VERDICT.search(_spoken(text))
        if not match:
            continue
        if match.group(1).upper() == "FAIL":
            failures += 1
        else:
            break
    return failures


def main():
    raw, data = read_hook_input()
    command = get_command(data)
    if not is_commit(command):
        pass_through()

    transcript = data.get("transcript_path", "")
    texts = list(iter_assistant_text(transcript, limit=TRANSCRIPT_LOOKBACK)) if transcript else []
    failures = _count_failures(texts)

    message = verdict(raw, texts, failures)
    if message:
        block(message)
    pass_through()


if __name__ == "__main__":
    main()
