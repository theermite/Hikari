#!/usr/bin/env python3
"""Unified Bash PreToolUse guard — all checks in one script.

RECOVERY PRINCIPLE: Every BLOCKED/WARNING message MUST include
a concrete recovery action so Takumi knows what to do next.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from shell_parse import simple_commands  # noqa: E402


def read_input():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    command = data.get("command", "")
    return raw, command


def check_secrets(raw):
    patterns = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"sk_live_[a-zA-Z0-9]+",
        r"sk_test_[a-zA-Z0-9]+",
        r"pk_live_[a-zA-Z0-9]+",
        r"ghp_[a-zA-Z0-9]{36}",
        r"gho_[a-zA-Z0-9]{36}",
        r"github_pat_[a-zA-Z0-9]+",
        r"\b(?-i:Bearer)\s+[A-Za-z0-9._-]{30,}",
        r"PRIVATE KEY",
    ]
    for pattern in patterns:
        if re.search(pattern, raw, re.IGNORECASE):
            return (
                f"BLOCKED: Secret pattern detected ({pattern}). "
                "RECOVERY: Replace the secret with an environment variable "
                "reference (e.g., $VAR or process.env.VAR). "
                "Store the value in .env (gitignored). Retry without the secret."
            )
    if re.search(r'password\s*[:=]\s*"[^$][^"]{3,}"', raw, re.IGNORECASE):
        return (
            "BLOCKED: Hardcoded password detected. "
            "RECOVERY: Move password to .env file, "
            "reference via environment variable, then retry."
        )
    return None


# rm -rf detection + the RM-OK token (Jay 2026-06-14).
# Cache dirs are always safe to delete. The token lifts the block for ONE
# command after Jay's explicit authorization — but NEVER on a catastrophic
# target (root, home, project/.git, system root). A non-empty reason is required.
_SAFE_CACHE = r"(node_modules|\.next|__pycache__|\.cache|\.pytest_cache|dist/\.)"
_RM = r"(?:rm -rf|rm -fr)"
_CATASTROPHIC_RM = [
    _RM + r"\s+/(?:\s|$|\*)",                       # root  /  or  /*
    _RM + r"\s+/[a-zA-Z]/(?:\s|$|\*)",              # drive root  /c/
    _RM + r"\s+[A-Za-z]:[\\/](?:\s|$|\*)",          # Windows  C:\
    _RM + r"\s+~(?:/(?:\s|$|\*)|\s|$)",             # home  ~  or  ~/
    _RM + r"\s+\$\{?HOME\}?",                        # $HOME / ${HOME}
    _RM + r"\s+\.\.?/?(?:\s|$)",                     # cwd  .  or  ..
    _RM + r"\s+\*",                                  # glob everything  *
    _RM + r"\s+[^\s]*\.git(?:/|\s|$)",              # a repo's  .git
    _RM + r"\s+/(etc|usr|bin|boot|lib|sbin|root|var|opt|srv|home)"
          r"(?:\s|$|/\s|/$|/\*)",                    # bare system root (not a subdir)
]


def _rm_override_reason(raw):
    """Return the non-empty reason from a '# RM-OK: <reason>' token, else None.

    The reason stops at the first double-quote so the JSON envelope ("...")
    does not leak into the audit log. An empty reason is rejected (None).
    """
    m = re.search(r"#\s*RM-OK:\s*([^\s\"][^\"\n]*)", raw, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _is_catastrophic_rm(raw):
    """True if the rm target is catastrophic — token can NEVER override it."""
    target = re.sub(r"#\s*RM-OK:.*", "", raw, flags=re.DOTALL)  # ignore the reason text
    return any(re.search(p, target, re.IGNORECASE) for p in _CATASTROPHIC_RM)


def _log_rm_override(raw, reason):
    """Append an auditable trace of each token-granted deletion. Best-effort."""
    try:
        log = Path(__file__).resolve().parents[3] / ".claude" / "state" / "rm-overrides.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{ts} | reason={reason} | cmd={' '.join(raw.split())[:300]}\n")
    except Exception:
        pass


def _check_rm(raw):
    if not re.search(r"rm -rf|rm -fr|rmdir /s", raw):
        return None
    if re.search(_SAFE_CACHE, raw):
        return None  # cache cleanup is always allowed
    if _is_catastrophic_rm(raw):
        return (
            "BLOCKED: rm -rf on a catastrophic target (root /, home, project "
            "root, .git, or a system directory). RECOVERY: the '# RM-OK' token "
            "CANNOT override this. Delete a specific sub-directory instead, or "
            "ask Jay to run it manually."
        )
    reason = _rm_override_reason(raw)
    if reason:
        _log_rm_override(raw, reason)
        return None  # Jay-authorized deletion, one token = one deletion
    return (
        "BLOCKED: rm -rf on non-cache directory. RECOVERY: Use "
        "'mv <target> <target>-backup' instead. If Jay explicitly authorized "
        "this deletion, append '# RM-OK: <reason>' to the command "
        "(one deletion per token, never on root/home/.git)."
    )


def _check_destructive_sql(raw):
    if re.search(
        r"DROP (TABLE|DATABASE|SCHEMA)|TRUNCATE |DELETE FROM .* WHERE 1|DELETE FROM [a-z]+ *;",
        raw,
        re.IGNORECASE,
    ):
        return (
            "BLOCKED: Destructive SQL detected. "
            "RECOVERY: Run pg_dump backup first, then ask Jay for confirmation. "
            "Never execute destructive SQL without a verified backup."
        )
    return None


def check_destructive(raw):
    return _check_rm(raw) or _check_destructive_sql(raw)


def check_no_verify(command):
    stripped = re.sub(r'"[^"]*"', "", command)
    stripped = re.sub(r"'[^']*'", "", stripped)
    if re.search(r"--no-verify", stripped):
        return (
            "BLOCKED: --no-verify bypasses all pre-commit hooks. "
            "RECOVERY: Remove --no-verify from your command. "
            "If a hook is failing, fix the underlying issue. "
            "Run the commit without --no-verify."
        )
    return None


# `git add` is read from SHELL TOKENS, not from a regex over the raw line. A regex
# missed `git -C "path with space" add -A`, missed `git -c k=v add -A`, and blocked a
# commit message that merely quoted the forbidden command (all found 2026-08-10).
# Tokenising solves the three at once: a quoted message is ONE token, never a command.
BROAD_ADD_ARGS = {"-A", "--all", "."}

# Repos written by several sessions at the same time. There, staging a whole
# directory carries away another session's work under your commit message
# (observed 2026-08-10). Elsewhere `git add src/` is legitimate daily work.
SHARED_REPOS = {"shinzo"}


# Parsing lives in lib/shell_parse.py — one reader for every Bash guard. Two
# private copies diverged within a day and each correction reopened a hole in the
# other (three independent reviews, 2026-08-10).
_simple_commands = simple_commands


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


def check_force_push_main(command):
    if not re.search(r"git push.*(--force|--force-with-lease|-f\b)", command):
        return None
    if re.search(r"\b(main|master)\b", command):
        return (
            "BLOCKED: Force push to main/master is forbidden. "
            "RECOVERY: Use a feature branch. "
            "Update main via regular merge or rebase workflow."
        )
    return None


def check_force_push_warn(command):
    if not re.search(r"git push.*(--force|--force-with-lease|-f\b)", command):
        return None
    if re.search(r"\b(main|master)\b", command):
        return None
    return (
        "WARNING: Force push on non-main branch. "
        "ACTION: Verify the remote branch can be safely overwritten."
    )


def check_conventional_commit(command, raw):
    if "git commit" not in command or "-m" not in command:
        return None
    if re.search(r"--amend", command):
        return None
    types = r"(feat|fix|refactor|docs|chore|test|perf|ci|style)"
    if not re.search(types + r"(\([a-zA-Z0-9_-]+\))?:", raw):
        return (
            "WARNING: Commit message not in Conventional Commits format. "
            "ACTION: Use 'type(scope): description'. "
            "Types: feat, fix, refactor, docs, chore, test, perf, ci, style."
        )
    return None


def check_co_authored_by(command, raw):
    if "git commit" not in command or "-m" not in command:
        return None
    if re.search(r"--amend", command):
        return None
    if "Co-Authored-By:" not in raw:
        return (
            "WARNING: Commit missing Co-Authored-By line. "
            'ACTION: Add \'Co-Authored-By: Takumi "IA Dev Partner"\' '
            "at the end of the commit message."
        )
    return None


def check_refactor_file_count(raw):
    if "git commit" not in raw:
        return None
    msg_match = re.search(
        r"(feat|fix|refactor|docs|chore|test|perf|ci|style)(\([a-zA-Z0-9_-]+\))?:.*",
        raw,
    )
    if not msg_match or "refactor" not in msg_match.group(0).lower():
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        staged = len([f for f in result.stdout.strip().split("\n") if f])
        if staged > 3:
            return (
                f"WARNING: Refactor commit touches {staged} files (max: 3). "
                "ACTION: Split into smaller commits. "
                "Use 'git reset HEAD <files>' to unstage excess, "
                "commit first batch (max 3 related files), then commit the rest."
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def check_vitest_oom(command):
    """Warn if running vitest without verified OOM config."""
    if not re.search(r"(npx|pnpm|yarn)\s+vitest", command):
        return None
    # Check if the current project has vitest config with pool: 'forks'
    import glob
    config_files = glob.glob("vitest.config.*") + glob.glob("vite.config.*")
    for cfg in config_files:
        try:
            with open(cfg, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if "'forks'" in content and "maxForks" in content:
                return None
        except OSError:
            pass
    return (
        "WARNING: Running vitest without verified OOM protection. "
        "ACTION: Ensure vitest config has pool: 'forks' and maxForks: 2 "
        "to prevent VPS memory saturation. See rules/Quality.md."
    )


def check_deploy(raw):
    deploy_patterns = [
        r"scp .* vps|rsync .* vps",
        r"ssh .*(deploy|restart|systemctl)",
        r"docker compose.*up.*-d.*vps|docker-compose.*up.*-d.*vps",
    ]
    is_deploy = any(re.search(p, raw, re.IGNORECASE) for p in deploy_patterns)
    if is_deploy:
        return (
            "WARNING: VPS deploy detected. "
            "ACTION: Before proceeding, verify: (1) all tests pass, "
            "(2) backup exists (pg_dump or git tag), (3) no uncommitted changes. "
            "If all checks pass, continue. If not, run the missing checks first."
        )
    return None


def check_db_migration(raw):
    if re.search(r"alembic upgrade|prisma migrate|prisma db push", raw, re.IGNORECASE):
        return (
            "WARNING: DB migration detected. "
            "ACTION: Run pg_dump backup BEFORE the migration. "
            "If already done in this session, continue. If not, run: "
            "pg_dump -Fc <dbname> > backup-$(date +%Y%m%d-%H%M).dump, then retry."
        )
    return None


def check_dependency_version(raw):
    if re.search(r"npm install [a-z@]|pnpm add [a-z@]|pip install [a-z]|yarn add [a-z@]", raw, re.IGNORECASE):
        if re.search(r"@[0-9]+\.[0-9]+|==[0-9]+\.[0-9]+|>=[0-9]+\.[0-9]+", raw):
            return (
                "WARNING: Specific version in install command. "
                "ACTION: Verify this version exists via npm/pypi/web "
                "(training data is months stale). If already verified, continue."
            )
    return None


def main():
    raw, command = read_input()

    for msg in [check_secrets(raw), check_destructive(raw), check_no_verify(command), check_git_add_broad(command), check_force_push_main(command)]:
        if msg:
            print(msg, file=sys.stderr)
            sys.exit(2)

    for msg in [check_refactor_file_count(raw), check_deploy(raw), check_db_migration(raw), check_dependency_version(raw), check_conventional_commit(command, raw), check_co_authored_by(command, raw), check_force_push_warn(command), check_vitest_oom(command)]:
        if msg:
            print(msg, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
