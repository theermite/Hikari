#!/usr/bin/env python3
"""Garde-fou des annexes — PreToolUse(Write|Edit|MultiEdit|Bash).

Les huit règles sont courtes; leur détail vit dans des annexes. Ce garde-fou refuse un travail
tant que l'annexe qu'il requiert n'a pas été lue (appel Read, ou texte déjà livré par le
harnais). Le moment de chaque annexe est dans `.claude/rules-ondemand/annexes.json`.

POURQUOI. Jay, 2026-10-26: « c'est arrivé trop de fois où l'on a démarré une plateforme, et le
socle minimal n'était pas respecté ». Une règle qu'on lit quand on y pense ne tient pas; une
règle dont l'écriture est bloquée tant qu'elle n'a pas été lue, si.

CE QU'IL NE FAIT PAS. Il ne bloque jamais si le registre est absent (une session doit pouvoir
démarrer), jamais sur une lecture, jamais sur l'édition des annexes elles-mêmes. Une fois lue,
une annexe n'est plus réclamée pendant la session.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

import annexes  # noqa: E402
from common import (  # noqa: E402
    block,
    find_repo_root,
    format_block,
    get_command,
    get_file_path,
    pass_through,
    read_hook_input,
)
from session_state import read_state, write_state  # noqa: E402
from transcript_reader import has_instructions_attachment, has_read_file  # noqa: E402

ETAT = "annexes-lues"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _journal(data: dict) -> tuple[str, bool]:
    """(journal à lire, lisible). Un sous-agent reçoit le journal de son PARENT (mesure du 2026-07-16, voir
    `reformulate-gate.py`): ses lectures sont dans le sien, `subagents/agent-<id>.jsonl`. Illisible = on laisse
    passer — un garde-fou qui se déclenche à tous les coups retire la capacité sans rien protéger."""
    parent = data.get("transcript_path", "") or ""
    agent = data.get("agent_id")
    if not agent or not isinstance(agent, str) or not SAFE_ID.match(agent):
        return parent, True
    if not parent:
        return "", False
    propre = Path(parent).with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
    return (str(propre), True) if propre.exists() else ("", False)


def _livree(transcript: str, fichier: str) -> bool:
    return has_read_file(transcript, fichier) or has_instructions_attachment(transcript, fichier)


def _appel(data: dict, racine: Path) -> tuple[str, str, str, bool]:
    outil = data.get("tool_name", "")
    chemin = get_file_path(data)
    commande = get_command(data) if outil == "Bash" else ""
    return outil, chemin, commande, (Path(chemin).exists() if chemin else True)


def _manquantes(requises: list[dict], data: dict, racine: Path) -> list[dict]:
    """Les annexes requises ni lues dans cette séance ni livrées par le harnais; mémorise les lues."""
    transcript, lisible = _journal(data)
    if not lisible:
        return []
    session = data.get("session_id", "") or "no-session"
    if isinstance(data.get("agent_id"), str) and SAFE_ID.match(data["agent_id"]):
        session = f"{session}_{data['agent_id']}"  # ce qu'un sous-agent a lu n'est pas ce que son parent a lu
    lues = set(read_state(ETAT, session_id=session, repo_root=racine).get("ids", []))
    manquantes = [a for a in requises if a["id"] not in lues and not _livree(transcript, a["fichier"])]
    vues = lues | ({a["id"] for a in requises} - {a["id"] for a in manquantes})
    if vues != lues:
        write_state(ETAT, {"ids": sorted(vues)}, session_id=session, repo_root=racine)
    return manquantes


def main() -> None:
    _, data = read_hook_input()
    racine = find_repo_root()
    registre = annexes.charger(racine)
    outil, chemin, commande, existe = _appel(data, racine)
    requises = annexes.requises(registre, outil, chemin, commande, existe) if registre else []
    manquantes = _manquantes(requises, data, racine) if requises else []
    if manquantes:
        liste = " ; ".join(a["fichier"] for a in manquantes)
        block(format_block(
            f"{len(manquantes)} annexe(s) à lire avant ce travail",
            f"Read {liste} — puis relancer. Une annexe lue n'est plus réclamée de la séance",
            reference=".claude/rules/01-Lecture.md § 7 (quand lire quelle annexe)",
        ))
    pass_through()


if __name__ == "__main__":
    main()
