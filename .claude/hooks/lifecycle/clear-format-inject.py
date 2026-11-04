#!/usr/bin/env python3
"""Clear-format inject — UserPromptSubmit. Rappelle à Takumi ce que Jay attend d'une réponse, AVANT qu'il écrive.

Décision de Jay (2026-11-04) : plus de gabarit imposé (il faisait réécrire les réponses et alourdissait les
simples). Le rappel redit les principes de Jay en 100 mots au plus, sans titre obligatoire.

Coût borné : une fois à l'ouverture de la séance, puis tous les 25 messages (le contexte se compacte, la consigne
s'use). Le filet clear-recap-check ne contrôle plus que le jargon et les numéros de commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402

STATE_NAME = "clear-format-told"
REMIND_EVERY = 25

REMINDER = (
    "[RÉPONSES À JAY — ses principes, forme libre]\n"
    "Va à l'essentiel : court, pragmatique, simple. Jay doit toujours savoir de quoi tu parles, ce que ça implique "
    "(si pertinent) et l'impact d'une décision (si on décide). Tout s'est bien passé : dis-le en une ligne. "
    "Listes, check-lists et tableaux pour structurer ; emojis modérés pour catégoriser. "
    "Pas de nom de commande ni de numéro de commit dans le chat."
)


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict):
        return
    session_id = data.get("session_id") or None
    state = read_state(STATE_NAME, session_id=session_id)
    count = state.get("prompts", 0)
    if not isinstance(count, int):
        count = 0
    write_state(STATE_NAME, {"prompts": count + 1}, session_id=session_id)
    if count % REMIND_EVERY == 0:
        sys.stdout.buffer.write((REMINDER + "\n").encode("utf-8"))  # LF et UTF-8 : pas de \r\n sous Windows
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — fail open, never break a prompt
        print(f"[clear-format-inject] passing through: {exc}", file=sys.stderr)
    sys.exit(0)
