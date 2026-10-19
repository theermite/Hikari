#!/usr/bin/env python3
"""UserPromptSubmit — Jay pasted something shaped like a secret.

A prompt cannot be rewritten before it enters the conversation, so this cannot
undo the paste. It does the two things that remain (Jay 2026-10-18):
- tells Jay, in his language, to renew the value (systemMessage);
- tells Takumi never to repeat, write, commit or send it (additionalContext).

Same strict detector as the output filter (names with a literal value, vendor
prefixes, PEM, credentialed URL, JWT). Silent on an ordinary prompt; never
blocks; fails open on anything unreadable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import common  # noqa: E402
import secret_mask  # noqa: E402

FOR_JAY = (
    "Ton message contient une valeur qui ressemble à un secret (clé, jeton, mot de "
    "passe). Elle est déjà dans la conversation : je ne peux pas l'effacer. Renouvelle-la "
    "chez le fournisseur, puis range la nouvelle dans le coffre."
)
FOR_TAKUMI = (
    "Le message de Jay contient une valeur qui ressemble à un secret. Ne la répète "
    "JAMAIS, ne l'écris dans aucun fichier, commande, commit ni message ; dis seulement "
    "sa longueur si besoin. Rappelle-lui de la renouveler et de la ranger dans le coffre."
)


# Framing the harness puts around text that is NOT Jay's own: agent reports,
# task notifications, reminders, relayed sessions. They can quote secret-shaped
# text without Jay having pasted anything.
_NOT_JAY = ("<agent-message", "<task-notification", "<system-reminder", "<cross-session-message",
            "[Subagent hand-back]", "[SYSTEM NOTIFICATION")


def build_decision(data: dict) -> dict | None:
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or any(m in prompt for m in _NOT_JAY):
        return None
    if not secret_mask.has_secret(prompt, strict=True):
        return None
    return {
        "systemMessage": FOR_JAY,
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": FOR_TAKUMI},
    }


def main() -> None:
    try:
        _, data = common.read_hook_input()
        decision = build_decision(data if isinstance(data, dict) else {})
    except Exception as exc:  # noqa: BLE001 — never break the prompt
        print(f"[pasted-secret-alert] passing through: {exc}", file=sys.stderr)
        decision = None
    if decision is not None:
        print(json.dumps(decision))
    sys.exit(0)


if __name__ == "__main__":
    main()
