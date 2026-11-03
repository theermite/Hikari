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
les classes Critique et Sensible, à la poussée (`guards/expert-push-check.py`). Les experts sans fichier à eux sont
rappelés par un geste (commit, mise en ligne) dans `quality/expert-moment-reminder.py`.
Le chemin jugé est celui du DÉPÔT (un dossier parent du disque nommé `tests/` ne doit pas éteindre tout le dépôt) ; hors
dépôt git rien n'est retenu ni écrit.
Sans hook : ouvrir `agents-wiring.json`, et dire dans le rapport quel expert a été consulté, ou pourquoi aucun.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_wiring import reminders_for  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input  # noqa: E402
from expert_trace import give_once, in_repository, trace  # noqa: E402

SEEN = "expert-reminders-seen.json"


def build_message(agents: list[str]) -> str:
    names = ", ".join(f"**{a}**" for a in agents)
    return (
        f"[EXPERT] Ce fichier relève de : {names}. Les lancer n'est pas obligatoire à chaque fichier : le déclencheur est la "
        "décision (nouvelle structure, choix d'architecture, comportement délicat). Pour le faire : outil Agent, "
        "subagent_type = son nom, avec un brief qui demande de REFUTER ou d'étudier, pas de valider. Sinon, une ligne dans "
        "le rapport : « aucun expert consulté — <raison> ». Ce rappel est tracé et mesuré chaque semaine "
        "(.claude/rules-ondemand/agents-wiring.json)."
    )


def _relative(root: Path, path: str) -> str:
    """The file path as the repository sees it: a parent folder of the disk (`tests/`, `streaming/`) is not the project's."""
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path


def _repository_of(path: str) -> Path | None:
    """The git repository that holds this file, or None (a file outside any repository)."""
    for folder in Path(path).parents:
        if (folder / ".git").exists():
            return folder
    return None


def _reminders_due(data: dict, path: str) -> tuple[Path, str, list[tuple[str, str]]]:
    """(repository, session, the reminders not yet given in this session), and remembers them as given."""
    cwd_root = find_repo_root(Path(data.get("cwd") or Path.cwd()))
    root = _repository_of(path) or cwd_root   # the file's own repository first: its relative path is what counts
    session = str(data.get("session_id") or "no-session")
    wanted = reminders_for(_relative(root, path) if in_repository(root) else path)
    return root, session, give_once(root, SEEN, session, wanted)


def main() -> None:
    try:
        _, data = read_hook_input()
        path = str(((data.get("tool_input") if isinstance(data, dict) else None) or {}).get("file_path") or "")
        root, session, due = _reminders_due(data, path) if path else (Path("."), "", [])
        if due:
            trace(root, session, due, path)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "additionalContext": build_message([a for a, _ in due])}},
                             ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — a reminder never breaks a write
        print(f"[DEBUG][expert-reminder] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
