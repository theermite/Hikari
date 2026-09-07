#!/usr/bin/env python3
"""Le resume de reprise remonte tout seul au demarrage — SessionStart.

Trigger
-------
SessionStart. Si un resume de reprise recent attend, il est remonte UNE FOIS,
puis marque comme lu.

Pourquoi
--------
Le mecanisme de resume existait, mais il ne se declenchait qu'a la compression
automatique du contexte. Apres un `/clear` volontaire — la reprise a chaud
demandee par Jay le 2026-09-06 — rien ne l'ecrivait, et rien ne le remontait.
La reprise restait donc theorique : « livre n'est pas declenche ».

Une seule fois : un resume qui remonte a chaque session devient du bruit, et un
bruit finit ignore. Une fois lu, il est renomme — l'artefact reste sur le
disque, il ne se represente plus.

Recence : au-dela de 12 heures, un resume decrit un autre travail. Il est laisse
sur le disque sans etre remonte, plutot que de rouvrir un fil deja clos.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import find_repo_root, pass_through, read_hook_input  # noqa: E402
from session_state import state_dir  # noqa: E402

NOM = "handoff-latest.md"
FRAICHEUR_H = 12


def brief_en_attente(dossier: Path, maintenant: float | None = None) -> Path | None:
    """Le resume a remonter, ou None s'il n'y en a pas de frais."""
    chemin = Path(dossier) / NOM
    try:
        age_h = ((maintenant or time.time()) - chemin.stat().st_mtime) / 3600
    except OSError:
        return None
    return chemin if age_h <= FRAICHEUR_H else None


def marquer_lu(chemin: Path) -> None:
    """Un resume remonte une fois. Il reste sur le disque, sous un autre nom."""
    try:
        chemin.rename(chemin.with_suffix(".md.lu"))
    except OSError as e:
        # Trace, jamais avale : un resume qui se represente a chaque session
        # devient du bruit, et on veut savoir pourquoi le cas echeant.
        logging.debug("resume de reprise non marque lu (%s) : %s", chemin, e)


def message(contenu: str) -> str:
    return (
        "[REPRISE] Un resume de reprise attend. Lis-le AVANT toute action, et "
        "commence par ses fils ouverts.\n\n" + contenu.strip()[:4000]
    )


def main() -> None:
    read_hook_input()
    chemin = brief_en_attente(state_dir(find_repo_root()))
    if not chemin:
        pass_through()
        return
    try:
        contenu = chemin.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logging.debug("resume de reprise illisible (%s) : %s", chemin, e)
        pass_through()
        return
    marquer_lu(chemin)
    print(message(contenu), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
