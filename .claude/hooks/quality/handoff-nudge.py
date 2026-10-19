#!/usr/bin/env python3
"""Hand-off nudge — Stop hook. Takumi runs commands himself; Jay is not the executor.

Jay 2026-10-18 (methodology review): "trop de fois j'ai du rentrer moi-meme des commandes
[...] ce n'est pas a moi de faire ca". Measured on 24 local sessions: the real causes of a
hand-off are missing rights (Windows admin, refused permissions), not unwillingness, so the
hook does not forbid hand-offs, it asks Takumi to pick the right route first:
1. do it himself;
2. else run it in Jay's terminal tab (run_in_terminal: Jay approves one click instead of typing);
3. hand it over only for the closed list: a secret VALUE, a consent click or dashboard action
   at a third party, admin rights (UAC), something physical.

Fires when the last reply holds a fenced shell block AND asks Jay to run it, with none of the
closed-list reasons in the reply, and Jay did not ask for the command himself. Once per turn
(stop_hook_active), reads last_assistant_message, fails open on anything unreadable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # type: ignore  # noqa: E402
from transcript_reader import entry_message, iter_entries  # type: ignore  # noqa: E402
from user_turns import _is_real_user_message, _user_text  # type: ignore  # noqa: E402

MESSAGE = (
    "Tu demandes à Jay de lancer une commande. Ce n'est pas son rôle. 1) Fais-la toi-même. "
    "2) Si un droit te manque, lance-la dans son terminal avec run_in_terminal : il valide "
    "d'un clic au lieu de la taper. 3) Ne la lui laisse que pour un secret à saisir, un "
    "consentement ou une action chez un fournisseur, des droits administrateur ou un geste "
    "physique, et dis laquelle de ces raisons s'applique. Réécris ta réponse."
)

_FENCE = re.compile(r"```(?:bash|sh|shell|powershell|ps1|pwsh|cmd|zsh)\s*\n.+?```", re.DOTALL | re.IGNORECASE)
_ASK = re.compile(
    r"(?i)\b(peux-tu|pouvez-vous|tu peux|il faut que tu|à toi de)\b[^.\n]{0,60}"
    r"\b(lancer|relancer|exécuter|executer|taper|coller|copier|saisir)\b"
    r"|(?<!je )(?<!j')\b(lance|exécute|tape|colle)[- ](la|le|les|ceci|cela|ça|cette|ces)\b"
    r"|\bà (lancer|exécuter|taper)\b|\bdans (ton|ta) (terminal|console|powershell)\b"
)
_ALLOWED_REASON = re.compile(
    r"(?i)\b(secret|mot de passe|jeton|token|clé|cle|consentement|oauth|autoris(?:er|ation) chez|"
    r"tableau de bord|dashboard|administrateur|admin|uac|élévation|elevation|coffre|2fa|"
    r"double authentification|physique|branche|débranche|appuie sur)\b"
)
_JAY_ASKED = re.compile(r"(?i)\b(donne|écris|ecris|montre|propose|dis)[- ]moi\b[^.\n]{0,30}\bcommandes?\b|"
                        r"\bquelle commande\b|\bcomment (je )?(fais|lance|faire)\b")


def _last_jay_text(transcript_path: str) -> str:
    for entry in iter_entries(transcript_path):
        msg = entry_message(entry)
        if msg and _is_real_user_message(msg):
            text = _user_text(msg)
            if not text.lstrip().startswith("<"):
                return text
    return ""


def is_handoff(reply: str) -> bool:
    """A command block, a request to run it, and no closed-list reason."""
    return bool(_FENCE.search(reply) and _ASK.search(reply) and not _ALLOWED_REASON.search(reply))


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    if not isinstance(reply, str) or not is_handoff(reply):
        pass_through()
    path = data.get("transcript_path")
    if isinstance(path, str) and path and _JAY_ASKED.search(_last_jay_text(path)):
        pass_through()
    block(MESSAGE)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[handoff-nudge] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
