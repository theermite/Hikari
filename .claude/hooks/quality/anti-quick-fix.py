#!/usr/bin/env python3
"""Anti-quick-fix gate — PreToolUse Bash.

Trigger
-------
A `git commit -m "<msg>"` whose subject starts with `fix:` / `fix(...):`
or `hotfix:` / `hotfix(...):` (Conventional Commits style — case-insensitive).
Other commit types (feat, refactor, docs, chore, test, perf, ci, style) are
not gated by this hook — they are not claims of resolving a defect.

Why this hook exists
--------------------
"fix:" is a claim of resolution. Without an explicit reflection on durability,
root cause, and alternatives, fixes accumulate as symptom-patches: the same
defect resurfaces in a different form weeks later. The Monozukuri principle
"l'artisan repond du temps long" (rules/Monozukuri.md, comportement #6) is
satisfied only when each fix is consciously validated against three questions
BEFORE the commit is created. The marker forces the reflection to leave a
trace in the conversation, so future-Takumi (or future-Jay) can audit why a
given fix was deemed durable.

Marker — strict format
----------------------
Accepted forms in the recent transcript (latest occurrence wins):

  [ROBUSTNESS]
  - 6 mois: <pourquoi cette correction tient dans 6 mois>
  - cause racine: <oui — quelle racine | non — symptome assume car ...>
  - alternative durable: <aucune valable | voici X mais reportee car Y>

OR (legitimate skip, closed enum):

  [ROBUSTNESS-SKIP] motif: <typo|revert|test-fix|lint-fix|formatting|comment-only>

Layer model (mirrors pre-code-veille-check.py)
----------------------------------------------
- Layer A : closed SKIP enum (6 motifs) — any other text -> BLOCK.
- Layer B : if the commit message body itself contains "regression" or
  "revert" keywords AND no [ROBUSTNESS-SKIP] motif=revert is present, the
  full [ROBUSTNESS] is required (no skip allowed). Reverts are explicit
  symptom acknowledgements; regressions are root-cause-mandatory.
- Layer C : session counter on consecutive SKIPs — at the 3rd SKIP in a
  row, the hook BLOCKS until a real [ROBUSTNESS] marker resets it.

Hook exit codes
---------------
  0 = pass
  2 = block (stderr message printed with RECOVERY)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import (  # noqa: E402
    find_repo_root,
    format_block,
    get_command,
    pass_through,
    read_hook_input,
)
from session_state import read_state, write_state  # noqa: E402


# --- Configuration -----------------------------------------------------------

# Conventional Commit subject prefixes that constitute a claim of resolution.
# Pattern matches: `fix:`, `fix(scope):`, `hotfix:`, `hotfix(scope):`
# Anchored to the SUBJECT only (first -m argument), case-insensitive.
_FIX_SUBJECT_RE = re.compile(r"^\s*(fix|hotfix)(?:\([^)]*\))?\s*:", re.IGNORECASE)

# Extract the -m / --message argument (single-quoted, double-quoted, or bare token).
# We only need the SUBJECT line, so we capture the first message arg.
_MESSAGE_ARG_RE = re.compile(
    r"""
    (?:-m|--message)            # -m or --message flag
    (?:\s+|=)                   # space or equals
    (?:
        ' ([^']*) '             #  'single-quoted'
      | " ((?:[^"\\]|\\.)*) "   #  "double-quoted with escapes"
      | (\S+)                   #  bare token (no quotes)
    )
    """,
    re.VERBOSE,
)

# Detect `git commit` (any form) excluding rewrites and informational subcommands.
_COMMIT_CMD_RE = re.compile(r"\bgit\s+commit\b")
_AMEND_RE = re.compile(r"\bgit\s+commit\b[^&;|]*\b--amend\b")
_GIT_INFO_RE = re.compile(r"\bgit\s+(log|status|diff|show)\b")

# Marker scan (transcript)
_MARKER_RE = re.compile(
    r"(?:^|\s)\[(ROBUSTNESS|ROBUSTNESS-SKIP)\][^\n]*",
    re.MULTILINE,
)
_SKIP_MOTIF_RE = re.compile(
    r"\[ROBUSTNESS-SKIP\]\s+motif\s*:\s*([a-zA-Z0-9_\-]+)",
)

# Layer A — closed enum of acceptable SKIP motifs.
# Each motif corresponds to a commit class where the 3-question reflection adds
# no durability value (no logic change, or already an explicit acknowledgement).
ALLOWED_SKIP_MOTIFS = {
    "typo",            # pure typo / whitespace / wording fix, zero logic change
    "revert",          # `git revert` of an earlier commit
    "test-fix",        # adjusting a flaky / outdated test, not production code
    "lint-fix",        # formatter / linter auto-fix, no behavior change
    "formatting",      # whitespace, code style, import order
    "comment-only",    # docstring / comment edit, no code change
}

# Layer B — keywords in the SUBJECT that force full [ROBUSTNESS] (no skip allowed
# except `motif: revert`, since a revert is an explicit symptom acknowledgement).
_REGRESSION_RE = re.compile(r"\b(regression|recurr|recurring|same\s+bug|again)\b", re.IGNORECASE)
_REVERT_SUBJECT_RE = re.compile(r"^\s*Revert\s+", re.IGNORECASE)

# Layer A — body required fields (3 dashed lines after [ROBUSTNESS] line).
# We look for presence of the three labels, not their content (content is for humans).
_REQUIRED_BODY_LABELS = (
    re.compile(r"6\s*mois\s*:", re.IGNORECASE),
    re.compile(r"cause\s+racine\s*:", re.IGNORECASE),
    re.compile(r"alternative\s+durable\s*:", re.IGNORECASE),
)

TRANSCRIPT_SCAN_LIMIT = 60
SKIP_COUNT_THRESHOLD = 3
STATE_NAME = "robustness-skips"


# --- Command parsing ---------------------------------------------------------


def _command_has_git_commit(cmd: str) -> bool:
    """True only if `git` and `commit` appear as ADJACENT command tokens.

    Tokenizing with shlex means `git commit` buried inside a quoted argument to
    another program (e.g. `node -e "...git commit -m fix:..."`, `echo '...'`) is
    NOT a real commit and does not gate (Jay 2026-06-24 friction — a regex test
    string was blocked as if it were a commit). On unbalanced quotes shlex
    raises; we fall back to the conservative substring match so a genuinely
    malformed-but-real commit still gates rather than slips through.
    """
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        return bool(_COMMIT_CMD_RE.search(cmd))
    return any(
        tokens[i] == "git" and tokens[i + 1] == "commit"
        for i in range(len(tokens) - 1)
    )


def _is_real_commit_cmd(cmd: str) -> bool:
    """A real `git commit` invocation, excluding --amend and info subcommands."""
    if not cmd:
        return False
    if not _command_has_git_commit(cmd):
        return False
    if _AMEND_RE.search(cmd):
        return False
    if _GIT_INFO_RE.search(cmd):
        return False
    return True


def _extract_subject(cmd: str) -> str:
    """First -m / --message subject line, or '' when there is no message arg
    (e.g. bare `git commit` opening an editor — out of scope)."""
    m = _MESSAGE_ARG_RE.search(cmd)
    if not m:
        return ""
    raw_msg = m.group(1) or m.group(2) or m.group(3) or ""
    return raw_msg.splitlines()[0] if raw_msg else ""


def is_gated_commit(cmd: str) -> tuple[bool, str]:
    """Return (is_gated, subject). Gated only when a REAL git commit carries a
    -m subject starting with fix/hotfix."""
    if not _is_real_commit_cmd(cmd):
        return False, ""
    subject = _extract_subject(cmd)
    if not _FIX_SUBJECT_RE.match(subject):
        return False, ""
    return True, subject


# --- Transcript scan ---------------------------------------------------------


def _extract_text(entry) -> str:
    chunks: list[str] = []

    def walk(node):
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for _, v in node.items():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(entry)
    return "\n".join(chunks)


def _raw_entry_text(raw: str) -> str:
    """Plain text of one transcript JSONL line (falls back to the raw line)."""
    try:
        return _extract_text(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return raw


def _marker_from_text(text: str) -> tuple[str, str, str] | None:
    """Last marker in a text blob -> (marker_type, block_text, hash), or None.

    `block_text` is the marker line PLUS up to 8 following lines, so Layer A
    body validation can see the 3 required dashed fields.
    """
    matches = list(_MARKER_RE.finditer(text))
    if not matches:
        return None
    m = matches[-1]
    block_text = "\n".join(text[m.start():].splitlines()[:9])
    digest = hashlib.sha1(block_text.encode("utf-8")).hexdigest()[:16]
    return m.group(1), block_text, digest


def latest_marker(transcript_path: str) -> tuple[str, str, str] | None:
    """Return (marker_type, block_text, hash) of the most recent marker, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    for raw in reversed(lines[-TRANSCRIPT_SCAN_LIMIT:]):
        raw = raw.strip()
        if not raw:
            continue
        found = _marker_from_text(_raw_entry_text(raw))
        if found:
            return found
    return None


# --- Counter state -----------------------------------------------------------


def load_counter(session_id: str | None, repo_root: Path) -> dict:
    data = read_state(STATE_NAME, session_id, repo_root)
    return {
        "skip_count": int(data.get("skip_count", 0)),
        "last_marker_hash": str(data.get("last_marker_hash", "")),
    }


def save_counter(session_id: str | None, repo_root: Path, skip_count: int, marker_hash: str) -> None:
    write_state(
        STATE_NAME,
        {"skip_count": skip_count, "last_marker_hash": marker_hash},
        session_id,
        repo_root,
    )


# --- Validation --------------------------------------------------------------


def body_has_three_labels(block_text: str) -> tuple[bool, list[str]]:
    """Return (ok, missing_labels). The 3 required labels must ALL be present."""
    missing: list[str] = []
    labels = ["6 mois", "cause racine", "alternative durable"]
    for rx, label in zip(_REQUIRED_BODY_LABELS, labels):
        if not rx.search(block_text):
            missing.append(label)
    return (len(missing) == 0), missing


def subject_demands_full_marker(subject: str) -> str | None:
    """Layer B trigger — return a reason string when SKIP is refused, else None."""
    if _REGRESSION_RE.search(subject):
        return "subject mentions a regression / recurring bug"
    if _REVERT_SUBJECT_RE.search(subject):
        return "subject starts with 'Revert ' (explicit symptom acknowledgement)"
    return None


# --- Main --------------------------------------------------------------------


def _block(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def _block_no_marker(subject: str) -> None:
    _block(format_block(
        reason=f"`fix:` / `hotfix:` commit without [ROBUSTNESS] marker (subject: {subject!r})",
        recovery=(
            "Output the marker BEFORE retrying the commit:\n"
            "  [ROBUSTNESS]\n"
            "  - 6 mois: <pourquoi cette correction tient dans 6 mois>\n"
            "  - cause racine: <oui -- quelle racine | non -- symptome assume car ...>\n"
            "  - alternative durable: <aucune valable | voici X mais reportee car Y>\n"
            "Or, for trivial commits, emit:\n"
            f"  [ROBUSTNESS-SKIP] motif: <one of {sorted(ALLOWED_SKIP_MOTIFS)}>"
        ),
        reference="rules/Monozukuri.md > Anti-Quick-Fix Marker",
    ))


def _skip_motif(block_text: str) -> str:
    m = _SKIP_MOTIF_RE.search(block_text)
    return m.group(1).lower() if m else ""


def _enforce_layer_b(subject: str, block_text: str) -> None:
    """SKIP refused when the subject is a regression / revert (except motif=revert
    on a `Revert ` subject)."""
    reason = subject_demands_full_marker(subject)
    if not reason:
        return
    if _skip_motif(block_text) == "revert" and _REVERT_SUBJECT_RE.search(subject):
        return
    _block(format_block(
        reason=f"[ROBUSTNESS-SKIP] refused -- {reason}",
        recovery=(
            "Emit the full [ROBUSTNESS] marker (3 lines) BEFORE retrying. "
            "A regression or revert demands explicit reflection on durability "
            "and root cause; a skip motif is not sufficient."
        ),
        reference="rules/Monozukuri.md > Anti-Quick-Fix Marker (Layer B)",
    ))


def _enforce_layer_a(block_text: str) -> None:
    """SKIP motif must be in the closed enum."""
    motif = _skip_motif(block_text)
    if motif not in ALLOWED_SKIP_MOTIFS:
        _block(format_block(
            reason=f"[ROBUSTNESS-SKIP] motif '{motif or '(empty)'}' not in closed enum",
            recovery=(
                f"Use one of {sorted(ALLOWED_SKIP_MOTIFS)} "
                "or emit a full [ROBUSTNESS] marker instead."
            ),
            reference="rules/Monozukuri.md > Anti-Quick-Fix Marker (Layer A)",
        ))


def _enforce_skip_counter(marker_hash: str, counter: dict,
                          session_id: str, repo_root: Path) -> None:
    """Layer C — block at the 3rd consecutive SKIP (counted once per hash)."""
    if counter["last_marker_hash"] != marker_hash:
        counter["skip_count"] += 1
    if counter["skip_count"] >= SKIP_COUNT_THRESHOLD:
        save_counter(session_id, repo_root, counter["skip_count"], marker_hash)
        _block(format_block(
            reason=(
                f"[ROBUSTNESS-SKIP] threshold reached "
                f"(consecutive skips: {counter['skip_count']}, threshold {SKIP_COUNT_THRESHOLD})"
            ),
            recovery=(
                "Emit a full [ROBUSTNESS] marker (3 lines) -- the counter "
                "resets only with a real reflection, not with another SKIP."
            ),
            reference="rules/Monozukuri.md > Anti-Quick-Fix Marker (Layer C)",
        ))
    save_counter(session_id, repo_root, counter["skip_count"], marker_hash)


def _handle_skip_marker(subject: str, block_text: str, marker_hash: str,
                        counter: dict, session_id: str, repo_root: Path) -> None:
    """Layers B (regression), A (motif enum), C (session counter) for a SKIP."""
    _enforce_layer_b(subject, block_text)
    _enforce_layer_a(block_text)
    _enforce_skip_counter(marker_hash, counter, session_id, repo_root)


def _handle_full_marker(block_text: str, marker_hash: str, counter: dict,
                        session_id: str, repo_root: Path) -> None:
    """Verify the 3 required body labels, then reset the skip counter."""
    ok, missing = body_has_three_labels(block_text)
    if not ok:
        _block(format_block(
            reason=f"[ROBUSTNESS] marker is missing required label(s): {missing}",
            recovery=(
                "The marker MUST include all three lines:\n"
                "  - 6 mois: ...\n"
                "  - cause racine: ...\n"
                "  - alternative durable: ...\n"
                "Re-emit the marker with the missing line(s) before retrying."
            ),
            reference="rules/Monozukuri.md > Anti-Quick-Fix Marker",
        ))
    if counter["last_marker_hash"] != marker_hash:
        save_counter(session_id, repo_root, 0, marker_hash)


def main() -> None:
    _, data = read_hook_input()
    gated, subject = is_gated_commit(get_command(data))
    if not gated:
        pass_through()

    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    repo_root = find_repo_root()

    latest = latest_marker(transcript_path)
    if latest is None:
        _block_no_marker(subject)

    marker_type, block_text, marker_hash = latest
    counter = load_counter(session_id, repo_root)

    if marker_type == "ROBUSTNESS-SKIP":
        _handle_skip_marker(subject, block_text, marker_hash, counter, session_id, repo_root)
    else:
        _handle_full_marker(block_text, marker_hash, counter, session_id, repo_root)
    sys.exit(0)


if __name__ == "__main__":
    main()
