"""Un garde-fou de procédure n'arrête plus le travail: il avertit (décision de Jay, 2026-11-22).

`avertit(resultat)` prouve les DEUX moitiés: le geste passe (code 0) et l'avertissement est bien dit
(« AVERTISSEMENT » sur la sortie d'erreur, et jamais « BLOCKED »). Un test qui ne vérifierait que le code 0
passerait aussi pour un garde-fou devenu muet.
"""

from __future__ import annotations


def _texte(valeur) -> str:
    return valeur.decode("utf-8", "replace") if isinstance(valeur, bytes) else str(valeur or "")


def dit_au_modele(resultat) -> bool:
    """L'avertissement ATTEINT le modèle: un `additionalContext` valide sur la sortie standard.

    La sortie d'erreur n'est lue que par un journal (2026-10-30: ~29 avertissements muets). Un `emit_context` devenu
    muet passerait `avertit` seul (relecture du 2026-11-24)."""
    import json

    for ligne in _texte(resultat.stdout).splitlines():
        try:
            contexte = json.loads(ligne)["hookSpecificOutput"]["additionalContext"]
        except (ValueError, KeyError, TypeError):
            continue
        if "AVERTISSEMENT" in contexte:
            return True
    raise AssertionError(f"l'avertissement n'atteint pas le modèle (rien d'utile en sortie standard): {_texte(resultat.stdout)!r}")


def avertit(resultat) -> bool:
    assert resultat.returncode == 0, f"un refus de procédure bloque encore: {_texte(resultat.stderr)!r}"
    err = _texte(resultat.stderr)
    assert "AVERTISSEMENT" in err, f"le garde-fou est devenu muet au lieu d'avertir: {err!r}"
    assert "BLOCKED" not in err
    return True


def lu_comme_un_refus(resultat):
    """Un garde de FIN DE MESSAGE ne refuse plus (Jay 2026-11-24): il laisse un rappel pour le tour suivant, signalé par
    la marque `RAPPEL (tour suivant…)` sur la sortie d'erreur, et sort 0. Pour que les tests de DÉTECTION gardent leur
    sens (« signalé » = ancien code 2, « non signalé » = code 0), le résultat rend 2 exactement quand la marque est là."""
    if resultat.returncode == 0 and "RAPPEL (tour suivant" in _texte(resultat.stderr):
        resultat.returncode = 2
    return resultat
