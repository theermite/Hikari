#!/usr/bin/env python3
"""Clear-format inject — UserPromptSubmit. Dit la forme de réponse AVANT que Takumi écrive.

Reproche de Jay (2026-11-02) : quality/clear-recap-check.py (Stop) corrige après coup ; la réponse est écrite deux
fois, ce qui coûte des jetons (mesure corrigée du 2026-11-02 : 4 réécritures en 7 jours, 1 664 mots jetés) et alourdit la lecture.
Aucun crochet ne lit une réponse avant son envoi : le seul levier en amont est de poser le gabarit dans le contexte
au moment où la réponse se prépare.

Coût borné : une fois à l'ouverture de la séance, puis tous les 25 messages (le contexte se compacte, la consigne
s'use). Le gabarit vient de lib/clear_language.py, source unique avec le filet ; le filet reste en place.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from clear_language import LONG_REPORT_WORDS, TEMPLATE  # noqa: E402
from common import read_hook_input  # noqa: E402
from session_state import read_state, write_state  # noqa: E402

STATE_NAME = "clear-format-told"
REMIND_EVERY = 25

REMINDER = (
    "[FORME DES RÉPONSES À JAY — à appliquer dès la première ligne, pour ne pas réécrire ensuite]\n"
    f"Si ta réponse dépasse {LONG_REPORT_WORDS} mots, ou se termine par une question à Jay, elle s'écrit sous "
    "cette forme, sans nom de fichier, de commande ni de numéro de commit dans ces lignes (ils vont au rapport). "
    "Une réponse courte sans question reste libre.\n"
    f"{TEMPLATE}\n"
    "Sans question : la dernière rubrique devient « La suite »."
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
