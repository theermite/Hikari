"""Un garde-fou de procédure n'arrête plus le travail: il avertit (décision de Jay, 2026-11-22).

`avertit(resultat)` prouve les DEUX moitiés: le geste passe (code 0) et l'avertissement est bien dit
(« AVERTISSEMENT » sur la sortie d'erreur, et jamais « BLOCKED »). Un test qui ne vérifierait que le code 0
passerait aussi pour un garde-fou devenu muet.
"""

from __future__ import annotations


def _texte(valeur) -> str:
    return valeur.decode("utf-8", "replace") if isinstance(valeur, bytes) else str(valeur or "")


def avertit(resultat) -> bool:
    assert resultat.returncode == 0, f"un refus de procédure bloque encore: {_texte(resultat.stderr)!r}"
    err = _texte(resultat.stderr)
    assert "AVERTISSEMENT" in err, f"le garde-fou est devenu muet au lieu d'avertir: {err!r}"
    assert "BLOCKED" not in err
    return True
