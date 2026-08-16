"""git add / git push safety checks — split out of bash-guard.py 2026-08-16
when the file crossed the 500-line BLOCKING ceiling (rules/Quality.md).

One concept: reading `git add`/`git push` tokens and deciding whether they
are broad-stage or force-push-to-main. Imported by bash-guard.py, not itself
wired as a hook in settings.json.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from shell_parse import simple_commands  # noqa: E402

# Parsing lives in lib/shell_parse.py — one reader for every Bash guard. Two
# private copies diverged within a day and each correction reopened a hole in
# the other (three independent reviews, 2026-08-10).
_simple_commands = simple_commands

# `git add` is read from SHELL TOKENS, not from a regex over the raw line. A regex
# missed `git -C "path with space" add -A`, missed `git -c k=v add -A`, and blocked a
# commit message that merely quoted the forbidden command (all found 2026-08-10).
# Tokenising solves the three at once: a quoted message is ONE token, never a command.
BROAD_ADD_ARGS = {"-A", "--all", "."}

# Repos written by several sessions at the same time. There, staging a whole
# directory carries away another session's work under your commit message
# (observed 2026-08-10). Elsewhere `git add src/` is legitimate daily work.
SHARED_REPOS = {"shinzo"}


def _is_shared(path):
    parts = Path(path.strip("\"'")).parts
    return any(part.lower() in SHARED_REPOS for part in parts)


def _skip_git_options(segment):
    """Walk git's own options. Return (repo path or None, index of subcommand)."""
    repo, i = None, 1
    while i < len(segment) and segment[i].startswith("-"):
        option = segment[i]
        takes_value = option in ("-C", "-c") and i + 1 < len(segment)
        if option == "-C" and takes_value:
            repo = segment[i + 1]
        elif option.startswith("--git-dir="):
            repo = option.split("=", 1)[1]
        i += 2 if takes_value else 1
    return repo, i


def _parse_git_add(segment):
    """Return (repo path or None, pathspecs) when the segment is a `git add`."""
    if not segment or Path(segment[0]).name not in ("git", "git.exe"):
        return None
    repo, i = _skip_git_options(segment)
    if i >= len(segment) or segment[i] != "add":
        return None
    return repo, [a for a in segment[i + 1 :] if a != "--"]


def _looks_like_a_directory(pathspec, repo):
    """The disk decides BOTH ways when the path resolves.

    Guessing from the name alone reads `LICENSE`, `Dockerfile` and `.gitignore` as
    directories. So: ask the filesystem first, and when it cannot answer, trust
    only the trailing slash — an explicit mark, not a guess.
    """
    candidate = Path(repo).expanduser() / pathspec if repo else Path(pathspec)
    try:
        candidate = candidate.expanduser()
        if candidate.exists():
            return candidate.is_dir()
    except OSError:
        # Expected fallback (Quality.md Observability): an unreadable or racy
        # path falls through to the trailing-slash heuristic below instead of
        # crashing this hook — never a silently swallowed defect.
        pass
    return pathspec.endswith("/")


def _broad_add_message():
    return (
        "BLOCKED: Broad git add detected. "
        "RECOVERY: Use 'git add <specific files>' instead. "
        "List the files you intend to commit and add them by name. "
        "This prevents accidentally staging .env, credentials, or large binaries."
    )


def _shared_directory_message(pathspec):
    return (
        f"BLOCKED: staging the directory '{pathspec}' in a shared repo. "
        "RECOVERY: name each file this session wrote — 'git add -- <path> <path>'. "
        "Another session may be writing the same repo right now; a whole directory "
        "carries its work away under your commit message (observed 2026-08-10). "
        "Verify after with 'git show --name-only HEAD'."
    )


def _git_add_violation(repo, pathspecs):
    if any(arg in BROAD_ADD_ARGS for arg in pathspecs):
        return _broad_add_message()
    if not (repo and _is_shared(repo)):
        return None
    for pathspec in pathspecs:
        if not pathspec.startswith("-") and _looks_like_a_directory(pathspec, repo):
            return _shared_directory_message(pathspec)
    return None


# Last resort when the line cannot be tokenised (unbalanced quote, exotic syntax).
# A guard that cannot read a command must still refuse the obvious broad forms —
# failing open would let a typo disable it entirely.
_BROAD_ADD_FALLBACK = re.compile(r"git add (\.|--all|-A)(\s|\"|\;|&&|\||\)|$)")


def check_git_add_broad(command):
    try:
        segments = _simple_commands(command)
    except ValueError:
        return _broad_add_message() if _BROAD_ADD_FALLBACK.search(command) else None

    cwd_target = None
    for segment in segments:
        if segment[0] == "cd" and len(segment) > 1:
            cwd_target = segment[1]
        parsed = _parse_git_add(segment)
        if parsed is None:
            continue
        repo, pathspecs = parsed
        message = _git_add_violation(repo or cwd_target, pathspecs)
        if message:
            return message
    return None


# Independent review #1, 2026-08-16: the naive `\b(main|master)\b` regex
# matched the substring inside a legitimate branch name
# (`feature/rename-main-module`) and inside a command that merely MENTIONS
# the phrase (`echo 'never force push main'`) — reproduced live, both block
# real, harmless work. First fix: tokenise, look at the actual push target.
#
# Independent review #2, 2026-08-16 — SECOND FAIL, same family, structural
# change required (Independent-Review.md: patching a case is over at the
# 2nd failure). The first fix guessed the branch by TOKEN POSITION after
# stripping flags — and went fully silent, not even a WARNING, whenever that
# guess broke: `GIT_DIR=/tmp/x git push --force origin main` (segment[0] is
# the env assignment, never "git"), and `git push --force -o ci.skip origin
# main` (a push option with a separate-token value shifts every position by
# one, so "main" reads as if it were the remote). Two different root causes,
# same failure mode: a real force-push to main slipped through with zero
# trace. The structural fix is not a third positional patch — it is to stop
# treating "branch not resolved" as "safe", full stop:
#   1. Strip a leading `VAR=value` prefix before checking the program name.
#   2. Recognise git push's own value-taking flags (a small, stable,
#      documented list — not the open-ended shell-command enumeration that
#      caused the git-add saga on 2026-08-10) so they cannot shift positions.
#   3. Never return silence for a detected `--force`: unresolved is WARNED,
#      not ignored. `check_force_push_main` can still only BLOCK a
#      positively-identified main/master, but `check_force_push_warn` now
#      fires on every force-push whose target isn't proven safe.
_FORCE_FLAGS = ("--force", "-f")

# git push's own flags that take a value in a SEPARATE token (`-o value`),
# as opposed to `--flag=value` (already excluded by the leading `-`). Missing
# one here degrades BLOCK to WARN — it can no longer make the check go silent,
# because `check_force_push_warn` treats "not resolved" as "warn anyway".
_PUSH_VALUE_FLAGS = {
    "-o", "--push-option", "--repo", "--receive-pack", "--exec",
    "--recurse-submodules",
}

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _strip_leading_assignments(segment):
    """`VAR=value git push ...` — a leading env assignment, same shell syntax
    a real shell honours. Without this, segment[0] is the assignment, never
    "git", and the whole segment is invisible to every check below."""
    i = 0
    while i < len(segment) and _ASSIGNMENT_RE.match(segment[i]):
        i += 1
    return segment[i:]


def _parse_git_push(segment):
    """Return the push's argument tokens, or None if `segment` is not `git push`."""
    segment = _strip_leading_assignments(segment)
    if not segment or Path(segment[0]).name not in ("git", "git.exe"):
        return None
    _, i = _skip_git_options(segment)
    if i >= len(segment) or segment[i] != "push":
        return None
    return segment[i + 1 :]


def _non_flag_tokens(args):
    """Push arguments with git push's own value-taking flags skipped —
    shared by force detection and branch resolution so the two never walk
    the token list two different ways."""
    non_flags = []
    i = 0
    while i < len(args):
        token = args[i]
        if token.startswith("-"):
            if token in _PUSH_VALUE_FLAGS and "=" not in token:
                i += 2  # skip the flag AND its separate-token value
                continue
            i += 1
            continue
        non_flags.append(token)
        i += 1
    return non_flags


# Push MODES that destroy a remote branch without any force flag and without
# a `+` prefix (independent review #4, 2026-08-16 — verified live: each one
# left main deleted or rewritten while the guard stayed silent).
#   --mirror  makes the remote match the local exactly, deleting what is missing
#   --delete  removes the named remote branch outright
#   :branch   the empty-source refspec, git's older spelling of --delete
_DESTRUCTIVE_MODES = {"--mirror", "--delete", "-d"}


def _has_force_flag(args):
    """True when the push can overwrite or remove what is on the remote.

    Three mechanisms, each verified against real git rather than assumed:
      1. an explicit --force / -f / --force-with-lease flag
      2. a refspec carrying git's `+` force prefix (`origin +feature:main`)
      3. a destructive MODE — --mirror, --delete, or an empty-source refspec
    Rounds 3 and 4 of independent review each found one of these missing,
    and each time a real force-push to main went through in total silence.
    """
    if any(a in _FORCE_FLAGS or a.startswith("--force-with-lease") for a in args):
        return True
    if any(a in _DESTRUCTIVE_MODES for a in args):
        return True
    tokens = _non_flag_tokens(args)
    return any(t.startswith("+") or t.startswith(":") for t in tokens)


def _push_target_branches(args):
    """EVERY destination branch named by the push, in order.

    Empty when the command names none — `git push --force` alone pushes the
    current branch, genuinely ambiguous from the command text. Callers treat
    an empty result as "not proven safe", never as "safe to ignore".

    Independent review #5, 2026-08-16 — approach changed: rounds 1 to 4 each
    resolved ONE branch at ONE position, and git accepts several refspecs in
    a single push (`--delete main feature/x`, `push origin feature/x main`).
    main slipped through whenever it sat outside the checked slot, and the
    WARNING then named the wrong branch — worse than silence, because it
    reads as "checked, and safe". Returning the whole list removes the
    concept of "the position" that caused four rounds of the same family.

    The first positional token is the remote, every one after it is a
    refspec. That single rule covers `--delete` too, since the flag itself
    is filtered out — the special case it used to need is gone.
    """
    non_flags = _non_flag_tokens(args)
    branches = []
    for refspec in non_flags[1:]:
        cleaned = refspec.lstrip("+")
        destination = cleaned.split(":", 1)[1] if ":" in cleaned else cleaned
        if destination:
            branches.append(destination)
    return branches


# Fallback for input `_simple_commands` cannot tokenise (unbalanced quote) —
# fail closed on the obvious form, same principle as `_BROAD_ADD_FALLBACK`.
_FORCE_PUSH_MAIN_FALLBACK = re.compile(
    r"git push.*(--force|--force-with-lease|-f\b).*\b(main|master)\b"
)


PROTECTED_BRANCHES = ("main", "master")


def _force_push_target(command):
    """Return (force_present, branches) for the first destructive `git push`
    segment found, or (False, []) when there is none.

    `branches` lists EVERY destination the push names; empty means the target
    could not be resolved (no branch named, or a push option consumed a token
    this parser does not walk past). Callers must treat empty as "not proven
    safe", never as "safe to ignore" (module note, independent review #2).

    Raises ValueError when `command` cannot be tokenised at all (unbalanced
    quote) — callers fall back to a raw-text scan ONLY in that case.
    """
    segments = _simple_commands(command)
    for segment in segments:
        args = _parse_git_push(segment)
        if args is None or not _has_force_flag(args):
            continue
        return True, _push_target_branches(args)
    return False, []


def _mirrors_a_remote(command):
    """`git push --mirror` names no branch yet rewrites and deletes every one
    of them, main included — so it is blocked on sight rather than resolved."""
    try:
        segments = _simple_commands(command)
    except ValueError:
        return False
    return any(
        (args := _parse_git_push(segment)) is not None and "--mirror" in args
        for segment in segments
    )


def check_force_push_main(command):
    if _mirrors_a_remote(command):
        return (
            "BLOCKED: 'git push --mirror' rewrites AND deletes every remote "
            "branch, main included. "
            "RECOVERY: push the one branch you mean, by name. "
            "Mirroring is for moving a repo, never for daily work."
        )
    try:
        _, branches = _force_push_target(command)
    except ValueError:
        if _FORCE_PUSH_MAIN_FALLBACK.search(command):
            return (
                "BLOCKED: Force push to main/master is forbidden. "
                "RECOVERY: Use a feature branch. "
                "Update main via regular merge or rebase workflow."
            )
        return None
    # ANY protected branch among the targets blocks — not just the one sitting
    # in a given slot (independent review #5).
    if any(branch in PROTECTED_BRANCHES for branch in branches):
        return (
            "BLOCKED: Force push to main/master is forbidden. "
            "RECOVERY: Use a feature branch. "
            "Update main via regular merge or rebase workflow."
        )
    return None


def check_force_push_warn(command):
    try:
        forced, branches = _force_push_target(command)
    except ValueError:
        return None
    if not forced:
        return None
    if any(branch in PROTECTED_BRANCHES for branch in branches):
        return None  # already handled as BLOCKED above
    target = (
        "branch " + ", ".join(f"'{b}'" for b in branches)
        if branches
        else "an undetermined branch"
    )
    return (
        f"WARNING: Force push detected, target is {target}. "
        "ACTION: Verify the remote branch can be safely overwritten, "
        "and that it is not main/master."
    )
