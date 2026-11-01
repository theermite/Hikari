#!/usr/bin/env python3
"""README after a commit — PostToolUse Bash. Refuses a commit that changed how the project is run or used
without touching the root README.md: the model is told at once and must correct it (amend, or follow-up commit).

Why (Jay 2026-10-30): the only README control was a warning at `/session-end` (4 criteria, never blocking), and
`/session-end` is not always run. A README that nobody is forced to update goes stale in the same week.

Why AFTER the commit, not before (two independent reviews in a row, 2026-10-30): a guard that runs before the
command has to GUESS what the commit will contain by reading the command like a shell. First it read the index
before the `git add` of the same command (279 of 293 commits seen in the session journals chain them); then the
default message form `-m "$(cat <<'EOF' …)"` made the command splitter fail, and an unreadable command passed.
Every form fixed revealed another (`git rm`, a subshell, named paths, `git add .` from a subfolder). So the guard
does not read the command at all: it reads the commit the repository now holds. The cost: the commit exists when
the refusal comes (unpushed, so a correction is cheap); the gain: no command form can get past it.

Gated (the commit changes how the project is installed, run or used):
  * a docker-compose file, a Dockerfile, or a `.env*` file changed or deleted;
  * a file ADDED under a `commands/` folder (a new public command).
Not gated, on purpose: lockfiles and manifests (a dependency bump changes no instruction — gating them would get
the guard unplugged), and any edit to an existing command.

Each commit is judged ONCE (its sha is recorded, the last 20, in `<git dir>/readme-judged` — never in the working
tree): the verdict belongs to the commit, so an excuse or a refusal is not replayed by the next command, nor by a
commit made in a neighbour repo. An amended commit is a NEW commit and is judged again. Known limits: the guard
judges the HEAD it finds, so two sessions committing in the same repo within seconds can swap verdicts (the
one-writer-per-repo rule makes this exceptional); `git cherry-pick A B C` and a multi-commit revert judge only HEAD;
a command that merely contains the word `revert` or `commit` (`echo revert`) may trigger the judgement early.
Passes when the root README is in that commit (any case), when the repo has no root README, when the last commit
is older than FRESH_SECONDS (this command did not make it), when it was already judged, or when the command
that made it carries `# README-OK: <motif>` with a motif from the closed list. Commits made by `git revert` and
`git cherry-pick` are judged; a MERGE commit is not (it lists no file of its own: the commits it brings were
each judged when they were made). Anything it cannot read passes: a guard that blocks what it cannot read gets
unplugged. Only the command's `-C <dir>` and `cd <dir>` are read, to find the repository; a miss means no check,
never a wrong refusal.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, find_repo_root, get_command, pass_through, read_hook_input  # noqa: E402

MOTIFS = ("no-user-visible-change", "readme-already-current")
FRESH_SECONDS = 180
_ESCAPE = re.compile(r"(?:^|\s)#\s*README-OK:\s*(?P<motif>[a-z-]+)\b", re.IGNORECASE)
_COMMIT_WORDS = re.compile(r"\bgit\b[^\n]*?\b(?:commit|revert|cherry-pick)\b")
STATE_NAME = "readme-judged"   # inside the repo's git directory
KEEP_JUDGED = 20               # how many judged commits are remembered (a branch round trip must not rejudge one)
_CHDIR = re.compile(r"""(?:^|[\s;&|(])(?:-C|cd)\s+(?:"([^"]+)"|'([^']+)'|([^\s;&|)]+))""")
_RUN_FILES = (
    re.compile(r"(^|/)(docker-)?compose[^/]*\.ya?ml$", re.IGNORECASE),
    re.compile(r"(^|/)Dockerfile($|\.)"),
    re.compile(r"(^|/)\.env"),
)
_COMMAND_FILE = re.compile(r"(^|/)commands/[^/]+$")


def _git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True,
                           text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _resolve(base: Path, target: str) -> Path:
    """`base / target`, reading a Git-Bash drive path (`/d/x`) as the Windows one (`D:/x`)."""
    drive = re.match(r"^/([a-zA-Z])/(.*)$", target)
    if drive and sys.platform == "win32":
        target = f"{drive.group(1).upper()}:/{drive.group(2)}"
    return base / target


def _repositories(command: str, cwd: Path) -> list[Path]:
    """The repository of the session, plus the ones the command names with `-C` or `cd`."""
    folders = [cwd] + [_resolve(cwd, next(g for g in m.groups() if g)) for m in _CHDIR.finditer(command)]
    roots = {find_repo_root(f) for f in folders if f.is_dir()}
    return sorted(r for r in roots if (r / ".git").exists())


def _names(output: str | None) -> set[str]:
    return {line.strip().replace("\\", "/") for line in (output or "").splitlines() if line.strip()}


def _last_commit(root: Path) -> tuple[str, set[str], set[str]] | None:
    """(short sha, files it changed, files it added) of the FRESH last commit, else None."""
    head = (_git(root, "log", "-1", "--format=%ct %H") or "").split()
    if len(head) != 2 or not head[0].isdigit() or time.time() - int(head[0]) > FRESH_SECONDS:
        return None
    tree = ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root"]
    return head[1], _names(_git(root, *tree, "HEAD")), _names(_git(root, *tree, "--diff-filter=A", "HEAD"))


def _triggers(changed: set[str], added: set[str]) -> list[str]:
    return sorted(f for f in changed if any(p.search(f) for p in _RUN_FILES) or (f in added and _COMMAND_FILE.search(f)))


def _has_root_readme(root: Path) -> bool:
    try:
        return any(p.is_file() and p.name.lower() == "readme.md" for p in root.iterdir())
    except OSError:
        return False


def _escape_motif(command: str) -> bool:
    found = _ESCAPE.search(command)
    return bool(found) and found.group("motif").lower() in MOTIFS


def _state_file(root: Path) -> Path | None:
    """The record lives INSIDE git's own directory: never in the working tree, so it can never end up in a commit of
    a repo that does not ignore it (4th independent review: 14 repos of the workspace do not)."""
    out = (_git(root, "rev-parse", "--absolute-git-dir") or "").strip()
    return Path(out) / STATE_NAME if out else None


def _recorded_shas(state: Path) -> list[str]:
    try:
        return state.read_text(encoding="utf-8").split()
    except OSError:
        return []   # no record yet (first run in this repo): nothing was judged


def _record_shas(state: Path, shas: list[str]) -> None:
    try:
        state.write_text("\n".join(shas) + "\n", encoding="utf-8")
    except OSError as err:
        # No memory of it: the commit may be judged again, which is noisier but never wrong.
        print(f"[DEBUG][readme-commit-check] cannot record {shas[-1][:7]}: {err}", file=sys.stderr)


def _already_judged(root: Path, sha: str) -> bool:
    """Record `sha` as judged; True when it already was. A verdict belongs to a COMMIT, not to a command: without
    this, an excuse given to one command was ignored by the next one (third independent review, 2026-10-30)."""
    state = _state_file(root)
    if state is None:
        return False
    known = _recorded_shas(state)
    if sha in known:
        return True
    _record_shas(state, (known + [sha])[-KEEP_JUDGED:])
    return False


def _judge(root: Path, excused: bool) -> tuple[str, list[str]] | None:
    """(sha, gated files) when the fresh, not yet judged last commit of `root` breaks the rule, else None."""
    last = _last_commit(root) if _has_root_readme(root) else None
    if last is None or _already_judged(root, last[0]):
        return None
    sha, changed, added = last
    triggers = _triggers(changed, added)
    if excused or not triggers or any("/" not in f and f.lower() == "readme.md" for f in changed):
        return None
    return sha[:7], triggers


def _refusal(sha: str, triggers: list[str]) -> str:
    return (
        f"BLOCKED: the commit just made ({sha}) changes how the project is run or used ({', '.join(triggers[:5])}) "
        "but the root README.md is not in it. RECOVERY: update the README sections these files change (install "
        "steps, ports, environment, commands), then `git add README.md && git commit --amend --no-edit` if the "
        "commit is not pushed yet, or a follow-up commit if it is. If the README is already accurate, or nothing "
        f"visible changed, add `# README-OK: <motif>` to the next command, motif one of: {' | '.join(MOTIFS)}. "
        "An amended commit is a new commit: it is judged again, add the motif again if it applies. "
        "Why: an instruction nobody is forced to update is stale within a week."
    )


def main() -> None:
    _, data = read_hook_input()
    command = get_command(data)
    if not command or not _COMMIT_WORDS.search(command):
        pass_through()
    excused = _escape_motif(command)
    for root in _repositories(command, Path(data.get("cwd") or Path.cwd())):
        verdict = _judge(root, excused)
        if verdict:
            block(_refusal(*verdict))
    pass_through()


if __name__ == "__main__":
    main()
