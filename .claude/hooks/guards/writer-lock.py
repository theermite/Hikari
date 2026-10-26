#!/usr/bin/env python3
"""Un seul écrivain par dépôt — PreToolUse(Write|Edit|MultiEdit|Bash).

Avertit quand une AUTRE séance a écrit dans ce dépôt il y a moins d'un quart d'heure; bloque
seulement les gestes qui touchent à l'état partagé (commit, branche, fusion, poussée), avec deux
issues nommées. Voir `lib/writer_lock.py` pour le pourquoi et la limite.

Ne bloque jamais sans identité de séance, jamais sur une lecture, jamais sur le verrou lui-même.
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR.parent / "lib"))

import actes  # noqa: E402
import writer_lock  # noqa: E402
from common import (  # noqa: E402
    block,
    find_repo_root,
    format_block,
    get_command,
    get_file_path,
    pass_through,
    read_hook_input,
    warn,
)
from session_state import mark_once  # noqa: E402

BLOC = (
    "(1) attendre que l'autre séance ait fini, ou travailler dans un worktree séparé "
    "(`git worktree add ../<nom> -b <branche>`) ; (2) si c'est le même chantier ouvert dans deux "
    "fenêtres, relancer la commande avec `# WRITER-OK: <raison>` à la fin — Jay l'a décidé"
)


def _niveau(data: dict, racine: str) -> str | None:
    """"certain" (écriture connue dans le dépôt), "possible" (commande qui écrit peut-être), ou None.

    None: une lecture, le verrou lui-même, ou une écriture HORS du dépôt (bloc-notes, `/tmp`): rien de suivi n'y change.
    """
    if data.get("tool_name") != "Bash":
        chemin = get_file_path(data).replace("\\", "/")
        if ".claude/state/" in chemin or not actes.dans_le_depot(chemin, racine):
            return None
        return "certain"
    commande = get_command(data)
    if actes.ecrit(commande, racine):
        return "certain"
    return "possible" if actes.peut_ecrire(commande, racine) else None


def main() -> None:
    _, data = read_hook_input()
    racine = find_repo_root()
    session, niveau = data.get("session_id", ""), _niveau(data, str(racine))
    if not session or niveau is None:
        pass_through()
    autre = writer_lock.autre_ecrivain(racine, session)
    commande = get_command(data) if data.get("tool_name") == "Bash" else ""
    bloque = autre and autre["certain"] and writer_lock.touche_etat_partage(commande, str(racine))
    if bloque and not writer_lock.autorise_par_jay(commande):
        # refusée, la séance n'écrit PAS: sans cela elle deviendrait écrivain et refuserait l'autre à son tour
        block(format_block(
            f"AUTRE ÉCRIVAIN dans ce dépôt (séance {autre['session'][:8]}, il y a {autre['il_y_a_s']} s) : "
            "ce geste change l'état qu'elle utilise",
            BLOC, reference=".claude/rules/02-Parcours.md § 7 (un seul écrivain par dépôt)"))
    writer_lock.battre(racine, session, journal=data.get("transcript_path", "") or "", certain=niveau == "certain")
    if autre and mark_once("writer-lock-prevenu", "avis", session_id=session, repo_root=racine):
        peut = "" if autre["certain"] else "peut-être "
        warn(f"AUTRE ÉCRIVAIN : la séance {autre['session'][:8]} a {peut}écrit ici il y a {autre['il_y_a_s']} s. "
             "Écrire est permis ; commit, branche, fusion et poussée seront refusés tant qu'elle écrit"
             + ("." if autre["certain"] else " (refus seulement si elle écrit pour de bon)."))
    pass_through()


if __name__ == "__main__":
    main()
