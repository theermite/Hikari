#!/usr/bin/env python3
"""Modèle d'interaction sous les yeux — PreToolUse Write|Edit. À la première modification d'un fichier d'interface par séance.

Note de Jay (2026-08-30) : la qualité du modèle d'interaction (simple, agréable, évident à utiliser) est ce qui compte le plus
pour lui ; « une application qui ne donne pas envie d'y retourner est un échec ». La section existe dans les CDC (comptée par
le garde hebdomadaire) mais rien ne la mettait sous les yeux de Takumi au moment d'écrire un écran. Ici : la section du CDC
est rendue (tronquée), ou son absence est dite en une ligne. Rappel seulement, jamais de blocage, une fois par séance.

Le contenu de la section est le goût de Jay : le hook la cite, il ne la remplit jamais, et ne propose rien à sa place.
Limites écrites : « fichier d'interface » = extension (.tsx .jsx .vue .svelte .css .scss .html) hors tests ; une interface
écrite autrement (LiveView, Kotlin) n'est pas vue ; seul le premier CDC qui porte la section est cité. Hors dépôt : rien.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from cdc_modele_interaction import SECTION_MAX, fichiers_cdc, section_du_depot  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input  # noqa: E402
from expert_trace import give_once, in_repository  # noqa: E402

SEEN = "interaction-model-seen.json"
_INTERFACE = re.compile(r"\.(tsx|jsx|vue|svelte|css|scss|html)$", re.IGNORECASE)
_TEST = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.|\.test\.|\.spec\.", re.IGNORECASE)


def _message(root: Path) -> str | None:
    section = section_du_depot(root)
    if section:
        cut = section if len(section) <= SECTION_MAX else section[:SECTION_MAX].rsplit(" ", 1)[0] + " …"
        return (
            "[INTERACTION] Tu écris un écran. La qualité du modèle d'interaction pèse autant que le reste (Jay : c'est ce "
            "qui compte le plus pour lui). Ce que le CDC de ce projet en dit — vérifie ton écran contre :\n" + cut
        )
    if fichiers_cdc(root):
        return ("[INTERACTION] Ce projet a un CDC mais pas de section « Modèle d'interaction » : ton, états vides, erreurs, "
                "parcours. Propose un brouillon à Jay avant de figer l'écran ; ne le remplis pas seul (c'est son goût).")
    return None


def main() -> None:
    try:
        _, data = read_hook_input()
        path = str(((data.get("tool_input") if isinstance(data, dict) else None) or {}).get("file_path") or "")
        normal = path.replace("\\", "/")
        root = find_repo_root(Path((data.get("cwd") if isinstance(data, dict) else None) or Path.cwd()))
        if _INTERFACE.search(normal) and not _TEST.search(normal) and in_repository(root):
            message = _message(root)
            session = str(data.get("session_id") or "no-session")
            if message and give_once(root, SEEN, session, [("interaction", "interface")]):
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": message}},
                                 ensure_ascii=False))
    except Exception as error:  # noqa: BLE001 — a reminder never breaks a write
        print(f"[DEBUG][interaction-model-reminder] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
