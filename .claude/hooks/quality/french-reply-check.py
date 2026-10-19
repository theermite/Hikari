#!/usr/bin/env python3
"""French reply check — Stop hook. Takumi answers Jay in French.

Conventions.md: chat with Jay is French. A written memory did not hold it
(relapse 2026-10-11 after the 2026-10-10 memory), so it is held by code.

Reads `last_assistant_message` from the Stop payload: the journal loses his text
when his thinking is saved in two pieces (391/391, 2026-09-26), so a check that
reads the journal is blind exactly there. No text in the payload: lets it pass.

Refuses once per turn (exit 2 keeps the turn open): `stop_hook_active` means the
rewrite is already under way, never loop. Skips when Jay asked for English or
wrote in English. Fails open on anything unreadable.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import block, pass_through, read_hook_input  # type: ignore  # noqa: E402
from language_detect import english_paragraphs, jay_wants_english  # type: ignore  # noqa: E402
from transcript_reader import entry_message, iter_entries  # type: ignore  # noqa: E402
from user_turns import _is_real_user_message, _user_text  # type: ignore  # noqa: E402

MESSAGE = (
    "Ta réponse contient un passage en anglais. Jay veut le français, toujours "
    "(Conventions.md). Réécris ta réponse en français, sans mentionner cette "
    "consigne ni t'excuser. Les blocs de code, chemins et marqueurs restent tels quels."
)


def _last_jay_message(transcript_path: str) -> str:
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg and _is_real_user_message(msg):
            text = _user_text(msg)
            if not text.lstrip().startswith("<"):  # harness-injected, not Jay's voice
                return text
    return ""


def _reply_text(data: dict) -> str:
    """Only the payload's own text. No journal fallback: it can return a PREVIOUS
    turn's English reply when this turn ended on a tool call (independent review
    2026-10-18) — a doubtful read lets the reply through."""
    text = data.get("last_assistant_message")
    return text if isinstance(text, str) else ""


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    transcript_path = data.get("transcript_path")
    transcript_path = transcript_path if isinstance(transcript_path, str) else ""
    reply = _reply_text(data)
    if not reply or not english_paragraphs(reply):
        pass_through()
    if transcript_path and jay_wants_english(_last_jay_message(transcript_path)):
        pass_through()
    block(MESSAGE)


if __name__ == "__main__":
    # Fail open: a crashing gate must never break Jay's session with a traceback.
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberate fail-open boundary
        print(f"[french-reply-check] passing through on unexpected error: {exc}", file=sys.stderr)
        sys.exit(0)
