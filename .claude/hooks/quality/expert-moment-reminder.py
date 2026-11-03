#!/usr/bin/env python3
"""Rappel de l'expert par le geste — PreToolUse Bash. Commit et mise en ligne rappellent les experts du contrôle.

Reprise Kata 7.8.0 (Jay 2026-11-01) : 27 agents sur 32 n'étaient lancés nulle part. Les experts de matière sont rappelés par
le fichier qu'on touche (`expert-reminder.py`) ; ceux du contrôle (qualité du code, tests, débogage, refonte, sécurité,
conformité, performance, déploiement, supervision) n'ont pas de fichier : leur déclencheur est un GESTE. Les conditions sont
dans `lib/agent_moments.py`, le câblage dans `agents-wiring.json` (section `moments`).

Rappel seulement, jamais de blocage (un garde-fou qui gêne finit débranché, leçon du 2026-08-30), tracé dans le même journal
que les rappels par fichier : le garde hebdomadaire mesure si le rappel est suivi d'un lancement.
Limites écrites : la détection lit la commande (`git commit` après `cd` ou par alias n'est pas jugé dans le bon dossier) ;
un `commit -a` est jugé sur les fichiers suivis modifiés ; un commit sans `-m` n'a pas de type, donc pas de rappel de refonte
ni de correctif répété. Hors dépôt git rien n'est retenu ni écrit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from agent_moments import commit_moments, deploy_moments, parse_commit  # noqa: E402
from agent_wiring import load_registry  # noqa: E402
from common import find_repo_root, get_command, pass_through, read_hook_input  # noqa: E402
from deploy_reader import is_gated  # noqa: E402
from expert_trace import give_once, in_repository, trace  # noqa: E402

SEEN = "expert-moments-seen.json"


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def _commit_root(folder: str | None, cwd_root: Path) -> Path:
    """The repository a `git -C <folder> commit` runs in (a Git-Bash drive path `/d/x` is read as `D:/x` on Windows)."""
    if not folder:
        return cwd_root
    drive = re.match(r"^/([a-zA-Z])/(.*)$", folder)
    target = f"{drive.group(1).upper()}:/{drive.group(2)}" if drive and sys.platform == "win32" else folder
    found = find_repo_root(cwd_root / target)
    return found if in_repository(found) else cwd_root


def _files_of_commit(root: Path, everything: bool) -> list[str]:
    out = _git(root, "diff", "--name-only", "HEAD") if everything else _git(root, "diff", "--cached", "--name-only")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _files_fixed_recently(root: Path, days: int) -> set[str]:
    out = _git(root, "log", f"--since={days}.days", "-E", "--grep=^(fix|hotfix)", "--name-only", "--format=", "-n", "200")
    return {line.strip() for line in out.splitlines() if line.strip()}


def _owed(command: str, root: Path, registry: dict) -> tuple[list[tuple[str, str]], str]:
    """(the (agent, moment) pairs this command owes, the gesture's name)."""
    commit = parse_commit(command)
    if commit is not None:
        days = next((m.get("fenetre_jours", 30) for m in registry["moments"] if m["id"] == "correctif-repete"), 30)
        where = _commit_root(commit["directory"], root)
        fixed = _files_fixed_recently(where, days) if commit["kind"] in ("fix", "hotfix") else set()
        return commit_moments(_files_of_commit(where, commit["everything"]), commit["kind"], fixed, registry), "git commit"
    if is_gated(command, publishes=False):   # les vraies commandes, pas le texte : une note qui CITE « docker compose up » n'en est pas une
        return deploy_moments(registry), "mise en ligne"
    return [], ""


def build_message(gesture: str, agents: list[str]) -> str:
    names = ", ".join(f"**{a}**" for a in agents)
    return (
        f"[EXPERT] Ce geste ({gesture}) relève de : {names}. Pas obligatoire à chaque fois : le déclencheur est la décision "
        "(changement large, correctif qui revient, mise en ligne). Pour le faire : outil Agent, subagent_type = son nom, "
        "avec un brief qui demande de REFUTER ou d'étudier, pas de valider. Sinon, une ligne dans le rapport : « aucun "
        "expert consulté — <raison> ». Ce rappel est tracé et mesuré chaque semaine (.claude/rules-ondemand/agents-wiring.json)."
    )


def main() -> None:
    try:
        _, data = read_hook_input()
        command = get_command(data) if isinstance(data, dict) else ""
        root = find_repo_root(Path((data.get("cwd") if isinstance(data, dict) else None) or Path.cwd()))
        if command and in_repository(root):
            owed, gesture = _owed(command, root, load_registry())
            session = str(data.get("session_id") or "no-session")
            due = give_once(root, SEEN, session, owed)
            if due:
                trace(root, session, due, gesture)
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                         "additionalContext": build_message(gesture, [a for a, _ in due])}},
                                 ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — a reminder never breaks a command
        print(f"[DEBUG][expert-moment-reminder] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
