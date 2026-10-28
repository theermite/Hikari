"""What changed between the commit a review covered and HEAD (2026-10-28).

A verdict names a commit; what matters is whether a SHIPPED file moved since. Judged by git, never
by a phrase. Kept apart from the guard (file size limit)."""

from __future__ import annotations

import subprocess

from common import find_repo_root


# What a propagation does not ship: documentation. Everything under `.claude/`, `scripts/` and
# `rules-archives/` is code or rule, whatever its extension (a rule is a `.md`).
_SHIPPED_ROOTS = (".claude/", "scripts/", "rules-archives/")
_DOCUMENTATION_SUFFIXES = (".md", ".txt", ".json")


def is_documentation(path):
    p = path.replace("\\", "/")
    if p.startswith(_SHIPPED_ROOTS):
        return False
    return p.startswith(("docs/", "mnk/")) or p.endswith(_DOCUMENTATION_SUFFIXES)


def ecart_sans_code_propage(relu, head, racine=None):
    """True when no commit between the reviewed one and HEAD touched a shipped file.

    The verdict names a commit; what matters is what changed since. A phrase cannot say it, a
    git diff can (Jay 2026-10-28: two documentation commits from other sessions made a valid
    review obsolete and forced Jay to intervene). Git unable to answer is NOT a pass: an
    unresolvable commit stays refused, as before.
    """
    try:
        racine = racine or find_repo_root()
        sortie = subprocess.run(
            ["git", "-C", str(racine), "diff", "--name-only", f"{relu}..{head}"],
            capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return False
    if sortie.returncode != 0:
        return False
    return all(is_documentation(ligne) for ligne in sortie.stdout.splitlines() if ligne.strip())
