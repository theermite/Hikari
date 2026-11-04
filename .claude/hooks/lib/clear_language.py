"""Ce que Takumi dit à Jay se comprend sans avoir vu le code (reproche de Jay, 2026-11-01).

Un seul contrôle, de FORME de vocabulaire, jamais de justesse : le jargon que Jay n'a pas ne s'accumule pas
(trois termes internes distincts, ou un numéro de commit). Depuis la décision de Jay du 2026-11-04, la structure
de la réponse est libre : plus de titres imposés, plus de seuil de longueur. Ce que Jay attend est rappelé en
début de séance par lifecycle/clear-format-inject.py (REMINDER).

Les termes que Jay emploie lui-même (commit, test, garde-fou, relecture, propagation, dépôt, branche) ne sont
PAS dans la liste.
"""

from __future__ import annotations

import re

MIN_WORDS = 40          # en dessous, une réponse courte n'est pas contrôlée
JARGON_THRESHOLD = 3    # termes internes distincts

# terme interne -> mot de tous les jours
PLAIN = {
    "hook": "vérification automatique",
    "receveur": "projet qui reçoit",
    "empreinte": "numéro de version",
    "marqueur": "ligne de contrôle",
    "dispense": "exception autorisée",
    "mutation": "essai qui casse exprès le code pour voir si les contrôles le voient",
    "worktree": "copie de travail",
    "fast-forward": "rassembler le travail",
    "yaml": "fichier de données",
    "json": "fichier de données",
    "regex": "motif de recherche",
    "heredoc": "texte passé en bloc",
    "stderr": "message d'erreur",
    "payload": "contenu envoyé",
    "diff": "différences",
    "rebase": "réorganiser l'historique",
    "stash": "mettre de côté",
    "lint": "contrôle de style",
    "fixture": "jeu d'essai",
    "pytest": "les contrôles automatiques",
    "refactor": "réorganiser le code",
    "endpoint": "adresse du service",
    "parser": "lecteur",
    "numéro de commit": "ne pas citer : dire ce que le travail fait",
}
_TERM = {
    "hook": r"hooks?", "receveur": r"receveurs?", "empreinte": r"empreintes?", "marqueur": r"marqueurs?",
    "dispense": r"dispenses?", "mutation": r"mutations?", "worktree": r"worktrees?", "fast-forward": r"fast-forward",
    "yaml": r"yaml", "json": r"json", "regex": r"regex(?:es)?", "heredoc": r"heredocs?", "stderr": r"stderr",
    "payload": r"payloads?", "diff": r"diffs?", "rebase": r"rebas\w+", "stash": r"stash\w*", "lint": r"lint(?:er|s)?",
    "fixture": r"fixtures?", "pytest": r"pytest", "refactor": r"refactor\w*", "endpoint": r"endpoints?",
    "parser": r"pars(?:er|eur)s?",
}
_TERMS = {name: re.compile(rf"(?i)\b(?:{pattern})\b") for name, pattern in _TERM.items()}
_HASH = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`\n]*`")


def prose(text: str) -> str:
    """Le texte sans blocs de code ni code en ligne : le jargon y est permis (noms, messages d'erreur)."""
    return _INLINE.sub(" ", _FENCE.sub(" ", text))


def jargon_found(text: str) -> list[str]:
    body = prose(text)
    found = [name for name, pattern in _TERMS.items() if pattern.search(body)]
    return found + (["numéro de commit"] if _HASH.search(body) else [])


def _vocabulary_detail(found: list[str]) -> str:
    return "mots à remplacer : " + " ; ".join(f"« {name} » → {PLAIN[name]}" for name in found)


def problems(text: str) -> list[tuple[str, str]]:
    """[(« vocabulaire », détail)] ou [] : seul le jargon accumulé et les numéros de commit sont refusés."""
    if len(text.split()) < MIN_WORDS:
        return []
    jargon = jargon_found(text)
    if len(jargon) >= JARGON_THRESHOLD or "numéro de commit" in jargon:
        return [("vocabulaire", _vocabulary_detail(jargon))]
    return []
