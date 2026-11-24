"""Rappels de fin de message: un garde de Stop ne refuse plus, il laisse un rappel pour le tour suivant.

Jay 2026-11-24 (capture): le refus d'un Stop arrive APRÈS l'affichage de la réponse; la réécrire la lui montre deux fois.
Le garde appelle `rappel(nom, message)` (dans `common`) au lieu de `block`; `lifecycle/rappel-inject.py` dit le rappel
au prochain message de Jay, une seule fois. Même mécanisme que `simple-language-inject.py`. Bibliothèque standard seule.
"""

from __future__ import annotations

from pathlib import Path

from session_state import read_state, write_state

# Liste fermée: un nom hors liste est une faute de frappe, pas un nouveau rappel (il ne serait jamais dit).
NOMS = ("permission", "handoff", "online-claim", "recap", "announce", "memoire", "francais", "langues", "decisions", "plan")
PREFIXE = "rappel-"


def garder(nom: str, message: str, session_id: str | None = None, repo_root: Path | None = None) -> None:
    if nom not in NOMS:
        raise ValueError(f"rappel inconnu: {nom!r} (connus: {', '.join(NOMS)})")
    write_state(PREFIXE + nom, {"pending": True, "message": message}, session_id=session_id or None, repo_root=repo_root)


def a_dire(session_id: str | None = None, repo_root: Path | None = None) -> list[str]:
    """Les rappels en attente de cette séance, et les marque dits (une seule fois chacun)."""
    messages = []
    for nom in NOMS:
        etat = read_state(PREFIXE + nom, session_id=session_id or None, repo_root=repo_root)
        if etat.get("pending"):
            messages.append(str(etat.get("message") or ""))
            write_state(PREFIXE + nom, {"pending": False}, session_id=session_id or None, repo_root=repo_root)
    return [m for m in messages if m]
