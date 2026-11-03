"""Mémoire et trace des rappels d'experts : une fois par séance et par expert, et chaque rappel écrit dans un journal.

Partagé par `quality/expert-reminder.py` (rappel par fichier) et `quality/expert-moment-reminder.py` (rappel par geste) :
le garde hebdomadaire lit un seul journal, `expert-reminders.jsonl`, pour savoir si un rappel est suivi d'un lancement.
Hors dépôt git rien n'est retenu ni écrit (l'état partirait dans un dossier au hasard).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from session_state import read_state, write_state

REMINDERS = "expert-reminders.jsonl"


def in_repository(root: Path) -> bool:
    return (root / ".git").exists()


def _state(root: Path) -> Path:
    return root / ".claude" / "state"


def give_once(root: Path, name: str, session: str, wanted: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The (agent, trigger) pairs of `wanted` not yet given in this session; they are remembered as given.

    One state file PER SESSION (`session_state`: locked, atomic): two sessions of the same repository never overwrite each
    other's memory, and a long session is never evicted by newer ones (relecture indépendante du 2026-11-02).
    """
    if not in_repository(root):
        return []
    already = set(read_state(name, session_id=session, repo_root=root).get("agents", []))
    due = [(agent, trigger) for agent, trigger in wanted if agent not in already]
    if due:
        try:
            write_state(name, {"agents": sorted(already | {agent for agent, _ in due})}, session_id=session, repo_root=root)
        except (OSError, ValueError, TimeoutError) as error:
            print(f"[DEBUG][expert-trace] state not written: {error}", file=sys.stderr)
    return due


def trace(root: Path, session: str, due: list[tuple[str, str]], where: str) -> None:
    """One line per reminder in `expert-reminders.jsonl` (`where` = the file or the gesture that triggered it)."""
    now = datetime.now().astimezone().isoformat()
    lines = [json.dumps({"at": now, "session": session, "agent": agent, "trigger": trigger, "file": where},
                        ensure_ascii=False) for agent, trigger in due]
    try:
        with (_state(root) / REMINDERS).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as error:
        print(f"[DEBUG][expert-trace] trace not written: {error}", file=sys.stderr)
