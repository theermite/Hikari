"""Ce que Takumi dit à Jay se comprend sans avoir vu le code (reproche de Jay, 2026-11-01).

Trois contrôles de FORME, jamais de justesse :
- une question à Jay s'ouvre sur son contexte en mots simples, son effet, et ce qu'elle apporte ou non ;
- un long compte rendu s'ouvre sur « En clair » et « Ce que ça change » ;
- le vocabulaire que Jay n'a pas (et les numéros de commit) ne s'accumule pas : trois termes distincts suffisent.

Mesure de départ (3 jours, 682 messages de plus de 40 mots) : 53 des 98 questions à Jay sont techniques, 73 messages
citent un numéro de commit. Les termes que Jay emploie lui-même (commit, test, garde-fou, relecture, propagation,
dépôt, branche) ne sont PAS dans la liste.
"""

from __future__ import annotations

import re

MIN_WORDS = 40          # en dessous, une réponse courte n'a pas besoin de gabarit
LONG_REPORT_WORDS = 150
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
_QUOTED = re.compile("«[^»]*»|“[^”]*”")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")
_BULLET = r"^[\s*_>•\-]*"
_EN_CLAIR = re.compile(rf"(?im){_BULLET}en clair\b")
_CHANGE = re.compile(rf"(?im){_BULLET}(?:ce que (?:ça|ca|cela) change|impact)\b")
_APPORTE = re.compile(rf"(?im){_BULLET}ce que (?:ça|ca|cela) apporte\b")

TEMPLATE = (
    "**En clair** : <ce qui s'est passé, en mots de tous les jours, comme si Jay n'avait rien vu du code>\n"
    "**Ce que ça change pour toi** : <l'effet concret>\n"
    "**Ce que ça apporte, ou non** : <le gain, et ce qui reste inchangé>\n"
    "puis la question, en une phrase, avec ce que chaque réponse change."
)


def prose(text: str) -> str:
    """Le texte sans blocs de code ni code en ligne : le jargon y est permis (noms, messages d'erreur)."""
    return _INLINE.sub(" ", _FENCE.sub(" ", text))


def has_question(text: str) -> bool:
    """Une phrase interrogative parmi les dernières, hors citation et hors code."""
    body = _QUOTED.sub(" ", prose(text))[-900:]
    sentences = [s.strip() for s in _SENTENCE.split(body) if s.strip()]
    return any(re.sub(r"[*_❓]", "", s).strip().endswith("?") for s in sentences[-6:])


def jargon_found(text: str) -> list[str]:
    body = prose(text)
    found = [name for name, pattern in _TERMS.items() if pattern.search(body)]
    return found + (["numéro de commit"] if _HASH.search(body) else [])


def _vocabulary_detail(found: list[str]) -> str:
    return "mots à remplacer : " + " ; ".join(f"« {name} » → {PLAIN[name]}" for name in found)


def _form_problem(text: str, words: int) -> tuple[str, str] | None:
    """La forme : une question ouvre sur trois lignes ; un long compte rendu ouvre sur deux."""
    plain = bool(_EN_CLAIR.search(text) and _CHANGE.search(text))
    if has_question(text):
        if plain and _APPORTE.search(text):
            return None
        return ("question", "une question à Jay s'ouvre sur trois lignes : En clair, Ce que ça change, Ce que ça apporte")
    if words >= LONG_REPORT_WORDS and not plain:
        return ("rapport", "un long compte rendu s'ouvre sur En clair et Ce que ça change")
    return None


def problems(text: str) -> list[tuple[str, str]]:
    """[(nature, détail)] : « question », « rapport », « vocabulaire »."""
    words = len(text.split())
    if words < MIN_WORDS:
        return []
    found = [form] if (form := _form_problem(text, words)) else []
    jargon = jargon_found(text)
    if len(jargon) >= JARGON_THRESHOLD or "numéro de commit" in jargon:
        found.append(("vocabulaire", _vocabulary_detail(jargon)))
    return found
