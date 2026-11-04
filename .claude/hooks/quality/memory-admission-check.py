#!/usr/bin/env python3
"""Memory-admission check — Stop hook. Un aveu « de mémoire / sans avoir vérifié » ne se laisse pas à Jay.

Retour de Jay (2026-11-04) : Takumi produit du code ou des documents, puis plus loin avoue ne pas avoir vérifié et avoir
écrit de mémoire, ce qui n'est pas censé arriver. Le garde ne devine pas qu'un texte est faux : il lit l'AVEU.
Si la réponse finale avoue un défaut de vérification ET qu'un fichier a été écrit dans le tour ET qu'aucune vérification
(lecture, recherche, commande autre que git add/commit/push, web) ne suit le dernier fichier écrit, le tour reste ouvert
une fois : vérifie maintenant, corrige, puis rends compte.
Limites écrites : lexical (un aveu tourné autrement passe) ; seules les écritures par Write/Edit/MultiEdit/NotebookEdit sont vues (un fichier écrit par heredoc en Bash ne l'est pas) ; une vérification quelconque après l'écriture suffit à le
laisser passer (le garde ne juge pas qu'elle porte sur le bon sujet) ; une limite honnête annoncée après vérification
n'est pas touchée. Échec ouvert, une fois par tour (stop_hook_active).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import block, pass_through, read_hook_input  # noqa: E402
from turn_log import tool_runs  # noqa: E402

_VERB = r"(?:rev[ée]rifi|v[ée]rifi|relu|lu\b|contr[ôo]l|test|regard)\w*"
_ADMIT = re.compile(
    r"(?i)\bde m[ée]moire\b|\bma m[ée]moire\b|\bmon souvenir\b|"
    r"\bsans (?:(?:les|le|la|l['’]) ?)?avoir " + _VERB + r"|"
    r"\bje n['’]ai pas (?:pu )?" + _VERB + r"|\bnon (?:rev[ée]rifi|v[ée]rifi)\w*|"
    r"\bj['’]ai (?:suppos|devin|invent)\w*"
)
_DENIAL = re.compile(r"(?i)\b(?:pas|jamais|rien|aucun\w*|ni)\b[^.\n]{0,40}\b(?:de|ma) m[ée]moire\b|\bjamais de m[ée]moire\b")
_QUOTED = re.compile("«[^»]*»|“[^”]*”")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_WRITES = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
_GIT_ONLY = re.compile(r"^\s*git\s+(?:add|commit|push|stash)\b")

MESSAGE = (
    "Tu avoues avoir produit quelque chose sans le vérifier (de mémoire, sans relire, sans tester), et aucune vérification "
    "ne suit ton dernier fichier écrit. Vérifie maintenant : lis la source, relance la commande, compare. Corrige ce qui "
    "est faux, puis rends compte avant de rendre la main : ce qui était faux, ce qui est vérifié (avec la commande et sa "
    "sortie). Ne laisse pas Jay découvrir l'aveu."
)


def _admits(reply: str) -> bool:
    text = _QUOTED.sub(" ", _FENCE.sub(" ", reply))
    return any(_ADMIT.search(s) and not _DENIAL.search(s) for s in re.split(r"(?<=[.!?…])\s+|\n+", text))


def _unchecked_write(transcript: str) -> bool:
    runs = tool_runs(transcript)
    last = max((i for i, r in enumerate(runs) if r.name in _WRITES), default=None)
    if last is None:
        return False
    return not any(r.name != "Bash" or not _GIT_ONLY.match(r.command) for r in runs[last + 1:])


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        pass_through()
    reply = data.get("last_assistant_message")
    if isinstance(reply, str) and _admits(reply) and _unchecked_write(data.get("transcript_path") or ""):
        block(MESSAGE)
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a reply
        print(f"[memory-admission-check] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
