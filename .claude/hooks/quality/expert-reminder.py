#!/usr/bin/env python3
"""Rappel de l'expert par la matière — PreToolUse Write|Edit. Rappelle, ne bloque jamais, et LAISSE UNE TRACE.

Remplace `matter-expert-suggest.py` (2026-11-01). Deux défauts de l'ancien : son fichier d'état n'était jamais vidé, donc
« une fois par séance » voulait dire « une fois par dépôt, pour toujours » ; et il ne laissait aucune trace, donc personne
ne pouvait dire si un rappel était suivi. Ici : une fois par séance et par expert, les déclencheurs lus dans le registre
unique `agents-wiring.json` (mode « rappel »), et chaque rappel écrit dans `.claude/state/expert-reminders.jsonl`.
Le garde hebdomadaire (`scripts/garde-methode.py`) croise ce journal avec les lancements d'agents : un expert rappelé
souvent et jamais lancé est un déclencheur à retirer ou à renforcer (doctrine § 5 : une consultation ne compte que si elle
change quelque chose).

Il ne bloque pas : un garde-fou qui gêne le travail courant finit débranché (leçon du 2026-08-30). Le blocage existe pour
les classes Critique et Sensible, à la poussée (`guards/expert-push-check.py`).
Sans hook : ouvrir `agents-wiring.json`, et dire dans le rapport quel expert a été consulté, ou pourquoi aucun.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_wiring import reminders_for  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input  # noqa: E402

REMINDERS = "expert-reminders.jsonl"
SEEN = "expert-reminders-seen.json"
KEEP_SESSIONS = 20


def _state(root: Path) -> Path:
    return root / ".claude" / "state"


def _seen(root: Path) -> dict[str, list[str]]:
    try:
        data = json.loads((_state(root) / SEEN).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _remember(root: Path, seen: dict[str, list[str]]) -> None:
    kept = dict(list(seen.items())[-KEEP_SESSIONS:])
    try:
        (_state(root) / SEEN).write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8", newline="\n")
    except OSError as error:
        print(f"[DEBUG][expert-reminder] state not written: {error}", file=sys.stderr)


def _trace(root: Path, session: str, due: list[tuple[str, str]], path: str) -> None:
    now = datetime.now().astimezone().isoformat()
    lines = [json.dumps({"at": now, "session": session, "agent": agent, "trigger": trigger, "file": path},
                        ensure_ascii=False) for agent, trigger in due]
    try:
        with (_state(root) / REMINDERS).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as error:
        print(f"[DEBUG][expert-reminder] trace not written: {error}", file=sys.stderr)


def build_message(agents: list[str]) -> str:
    names = ", ".join(f"**{a}**" for a in agents)
    return (
        f"[EXPERT] Ce fichier relève de : {names}. Les lancer n'est pas obligatoire à chaque fichier : le déclencheur est la "
        "décision (nouvelle structure, choix d'architecture, comportement délicat). Pour le faire : outil Agent, "
        "subagent_type = son nom, avec un brief qui demande de REFUTER ou d'étudier, pas de valider. Sinon, une ligne dans "
        "le rapport : « aucun expert consulté — <raison> ». Ce rappel est tracé et mesuré chaque semaine "
        "(.claude/rules-ondemand/agents-wiring.json)."
    )


def _reminders_due(data: dict, path: str) -> tuple[Path, str, list[tuple[str, str]]]:
    """(repository, session, the reminders not yet given in this session), and remembers them as given."""
    root = find_repo_root(Path(data.get("cwd") or Path.cwd()))
    session = str(data.get("session_id") or "no-session")
    seen = _seen(root)
    already = set(seen.get(session, []))
    due = [(agent, trigger) for agent, trigger in reminders_for(path) if agent not in already]
    if due:
        _state(root).mkdir(parents=True, exist_ok=True)
        seen[session] = sorted(already | {agent for agent, _ in due})
        _remember(root, seen)
    return root, session, due


def main() -> None:
    try:
        _, data = read_hook_input()
        path = str(((data.get("tool_input") if isinstance(data, dict) else None) or {}).get("file_path") or "")
        root, session, due = _reminders_due(data, path) if path else (Path("."), "", [])
        if due:
            _trace(root, session, due, path)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "additionalContext": build_message([a for a, _ in due])}},
                             ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — a reminder never breaks a write
        print(f"[DEBUG][expert-reminder] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
