#!/usr/bin/env python3
"""Session-end objective metrics — SessionEnd only.

Emit a small, objective snapshot of the session's *observable* state, so
that the session report (and Jay) can read it instead of relying on the
LLM's self-assessment. Three metrics, each derivable from code (no LLM
judgement involved):

1. Unpushed commits ahead of origin/main — "did you push your work ?"
2. TODO / FIXME / XXX markers added in those unpushed commits — 5S Seiri
   (eliminate the superflu) + Monozukuri #1 (chaque brique parfaite).
3. Count of [VEILLE] / [SKB] / [VEILLE-SKIP] markers in recent assistant
   text — discipline trace for Gate 1 (Context / veille evidence).

Writes the snippet to `.claude/state/last-session-metrics.md` so the
session-end skill can pick it up. Emits a one-line summary to stderr.
NEVER blocks, NEVER warns destructively — pure observability.

Design note (LLM-code split, Jay 2026-05-19):
  These metrics used to be asked of the LLM at session end ("how many
  commits ? did you push ? any TODOs left ?"). The LLM's answers were
  unreliable (forgotten commits, missed TODOs) and burned tokens at
  the most context-loaded moment of the session. Moving to a hook
  makes them deterministic and free.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))

from common import find_repo_root, pass_through, read_hook_input  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402


SNIPPET_NAME = "last-session-metrics.md"
VEILLE_RE = re.compile(r"\[(VEILLE|SKB|VEILLE-SKIP)\]")
TODO_RE = re.compile(r"^\+.*\b(TODO|FIXME|XXX)\b")


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a git command, return stdout or empty string on failure."""
    try:
        out = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _unpushed_commits(repo: Path) -> list[str]:
    out = _run(["git", "log", "origin/main..HEAD", "--oneline"], repo)
    return [line for line in out.splitlines() if line.strip()]


def _todos_in_unpushed_diff(repo: Path) -> dict[str, int]:
    out = _run(["git", "diff", "origin/main..HEAD"], repo)
    counts = {"TODO": 0, "FIXME": 0, "XXX": 0}
    for line in out.splitlines():
        m = TODO_RE.match(line)
        if m:
            counts[m.group(1)] += 1
    return counts


def _veille_markers(transcript_path: str) -> dict[str, int]:
    counts = {"VEILLE": 0, "SKB": 0, "VEILLE-SKIP": 0}
    for text in iter_assistant_text(transcript_path, limit=200):
        for m in VEILLE_RE.finditer(text):
            tag = m.group(1)
            if tag in counts:
                counts[tag] += 1
    return counts


def _render(commits: list[str], todos: dict[str, int], veille: dict[str, int]) -> str:
    todo_total = sum(todos.values())
    veille_total = sum(veille.values())
    lines = [
        "## Session Metrics (objective, code-derived)",
        "",
        f"- Unpushed commits ahead of `origin/main`: **{len(commits)}**",
    ]
    if commits:
        lines.append("")
        for c in commits[:10]:
            lines.append(f"  - `{c}`")
        if len(commits) > 10:
            lines.append(f"  - ... ({len(commits) - 10} more)")
        lines.append("")
    lines.append(
        f"- TODO/FIXME/XXX added in unpushed diff: **{todo_total}** "
        f"(TODO={todos['TODO']}, FIXME={todos['FIXME']}, XXX={todos['XXX']})"
    )
    lines.append(
        f"- Veille discipline markers in transcript: **{veille_total}** "
        f"([VEILLE]={veille['VEILLE']}, [SKB]={veille['SKB']}, "
        f"[VEILLE-SKIP]={veille['VEILLE-SKIP']})"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    _, data = read_hook_input()
    event = (data.get("hook_event_name") or "").lower()
    if event != "sessionend":
        pass_through()

    transcript_path = data.get("transcript_path", "") or ""
    repo = find_repo_root()

    commits = _unpushed_commits(repo)
    todos = _todos_in_unpushed_diff(repo)
    veille = _veille_markers(transcript_path)

    snippet = _render(commits, todos, veille)

    state_dir = repo / ".claude" / "state"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / SNIPPET_NAME).write_text(snippet, encoding="utf-8", newline="\n")
    except OSError:
        pass

    todo_total = sum(todos.values())
    veille_total = sum(veille.values())
    sys.stderr.write(
        f"[session-metrics] unpushed={len(commits)} todos+={todo_total} "
        f"veille_markers={veille_total} -> {state_dir.as_posix()}/{SNIPPET_NAME}\n"
    )
    pass_through()


if __name__ == "__main__":
    main()
