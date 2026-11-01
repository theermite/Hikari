#!/usr/bin/env python3
"""Le serveur web d'abord — PreToolUse WebSearch|WebFetch. Rappelle, ne bloque jamais.

Jay (2026-10-31) : « si on utilise en priorité le MCP Shinkofa Web, les recherches ne nous coûtent rien ».
Règle 06-Capacites § 1 : `web_search` et `web_read` du serveur web (moteur du VPS, aucun modèle appelé, aucun
frais par requête) passent AVANT `WebSearch` et `WebFetch`, qui ne servent qu'en repli déclaré.

Se déclenche quand l'outil intégré est appelé ET que le serveur `shinkofa-web` est déclaré dans la
configuration MCP. Une fois par séance et par outil : un rappel répété devient du bruit qu'on n'écoute plus.

Limite écrite : « déclaré » n'est pas « joignable ». Le serveur peut être éteint ou hors de portée (séance dans
le nuage) ; le rappel dit alors quoi faire : se replier, et dire pourquoi. Échoue ouvert.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import capacites  # type: ignore  # noqa: E402
from common import find_repo_root, pass_through, read_hook_input, warn  # type: ignore  # noqa: E402
from session_state import mark_once  # type: ignore  # noqa: E402

SERVEUR = "shinkofa-web"
REMPLACANT = {"WebSearch": "web_search", "WebFetch": "web_read"}


def message(outil: str) -> str:
    return (f"Le serveur web est déclaré : utilise d'abord `{REMPLACANT[outil]}` (outil `mcp__shinkofa-web__"
            f"{REMPLACANT[outil]}`, chargé avec ToolSearch s'il est différé) — aucun modèle appelé, aucun frais par "
            f"requête. `{outil}` ne sert qu'en repli : serveur éteint ou injoignable, séance dans le nuage, "
            f"résultat vide. Dans ce cas, dis pourquoi (règle 06-Capacites § 1).")


def main() -> None:
    _, data = read_hook_input()
    outil = data.get("tool_name") if isinstance(data, dict) else None
    if outil not in REMPLACANT:
        pass_through()
    racine = find_repo_root(Path(data["cwd"])) if data.get("cwd") else find_repo_root()
    if SERVEUR not in capacites.serveurs_mcp(Path.home(), racine):
        pass_through()
    if mark_once("serveur-web-d-abord", outil, data.get("session_id"), racine):
        warn(message(outil))
    pass_through()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — échoue ouvert, ne casse jamais un appel d'outil
        print(f"[serveur-web-d-abord] passe sans rappel : {exc}", file=sys.stderr)
        sys.exit(0)
