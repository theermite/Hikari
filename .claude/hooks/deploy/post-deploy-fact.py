#!/usr/bin/env python3
"""Post-deploy fact — PostToolUse Bash. Le fait « mise en ligne non contrôlée » arrive avant que Takumi écrive la phrase suivante.

Jay 2026-11-24 (audit réactif/anticipatif, conversion n°3). `quality/online-claim-check.py` (Stop) attrape « c'est en ligne » APRÈS que Jay
l'a lu. Le fait existe plus tôt : dès que la commande de mise en ligne s'est exécutée. Ce hook le dépose dans le contexte juste après le
résultat de la commande. Même lecture des commandes que `smoke-test-required.py` (`lib/deploy_reader.is_gated`) : une note ou un message de
commit qui CITE « docker compose up » n'est pas une mise en ligne. Il ne juge pas le résultat de la commande. Le garde de fin de message
reste le filet. Toute erreur : sortie 0 muette.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import format_warn, get_command, pass_through, read_hook_input, warn  # noqa: E402
from deploy_reader import is_gated  # noqa: E402


def main() -> None:
    _, data = read_hook_input()
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        pass_through()
    commande = get_command(data)
    if commande and is_gated(commande, publishes=False):
        warn(format_warn(
            reason="MISE EN LIGNE NON CONTRÔLÉE : la commande de mise en ligne vient de s'exécuter, aucun contrôle ne l'a suivie",
            action="ne dis pas « c'est en ligne » avant d'avoir lancé `web_check` (serveur web shinkofa-web) sur l'adresse publique et un "
                   "parcours critique (sans ce serveur : `curl -fsS -o /dev/null -w \"%{http_code}\" <url>`) et cité la sortie. "
                   "« En ligne » veut dire joignable ET fonctionnel.",
            reference=".claude/rules-ondemand/Mise-En-Service.md",
        ))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail open, never break a tool result
        print(f"[post-deploy-fact] passing through: {exc}", file=sys.stderr)
        sys.exit(0)
