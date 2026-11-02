"""Ce que Takumi dit à Jay se comprend sans avoir vu le code (reproche de Jay, 2026-11-01).

Trois contrôles de FORME, jamais de justesse :
- une question à Jay s'ouvre sur son contexte en mots simples, son effet, et ce qu'elle apporte ou non ;
- un long compte rendu s'ouvre sur « L'essentiel » et « Pour toi » ;
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
_BULLET = r"^[\s#*_>•\-\U0001F300-\U0001FAFF☀-➿️]*"
_ESSENTIEL = re.compile(rf"(?im){_BULLET}l['’]essentiel\b")
_POUR_TOI = re.compile(rf"(?im){_BULLET}pour toi\b")
_GAINS = re.compile(rf"(?im){_BULLET}gains?\b")

TEMPLATE = (
    "## 🟦 L'essentiel :\n<ce qui s'est passé, en mots de tous les jours, comme si Jay n'avait rien vu du code>\n\n"
    "## 🟧 Pour toi :\n<l'effet concret, et ce que tu dois faire s'il y a quelque chose>\n\n"
    "## 🟩 Gains et limites :\n<ce que ça apporte, et ce qui reste non réglé ou non vérifié>\n\n"
    "## 🟪 Ta question :\n<la question en une phrase, avec ce que chaque réponse change ; sans question : « La suite »>\n"
    "Chaque intitulé est un titre de niveau 2 (##) avec sa pastille de couleur devant, suivi d'un saut de ligne : "
    "le texte est en dessous, trois lignes au plus par bloc."
)
FORMAT_DETAIL = (
    "chaque intitulé est un titre de niveau 2 seul sur sa ligne, avec sa pastille de couleur devant "
    "(## 🟦 L'essentiel :, 🟧 Pour toi, 🟩 Gains et limites, 🟪 Ta question ou La suite), le texte en dessous"
)
# un intitulé conforme : « ## », le titre, un deux-points facultatif, rien d'autre sur la ligne
_H2_LINE = re.compile(r"^##\s+[^\n:]*:?\s*$")
# un rôle, une couleur, toujours la même (Jay 2026-11-01) : le titre doit porter la pastille de son rôle
_DOT = {"essentiel": "🟦", "pour toi": "🟧", "gains": "🟩"}


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


def _titles_not_h2(text: str) -> bool:
    """Un intitulé (L'essentiel, Pour toi, Gains et limites) qui n'est pas un titre de niveau 2 seul sur sa ligne."""
    for role, pattern in (("essentiel", _ESSENTIEL), ("pour toi", _POUR_TOI), ("gains", _GAINS)):
        found = pattern.search(text)  # le PREMIER seul : « Impact : … » plus bas est du contenu, pas un titre (7.8.0)
        if found is None:
            continue
        start = text.rfind("\n", 0, found.end()) + 1  # le motif peut avaler les lignes vides qui précèdent
        end = text.find("\n", found.end())
        line = text[start : end if end != -1 else len(text)]
        if not _H2_LINE.match(line) or _DOT[role] not in line:
            return True
    return False


def _form_problem(text: str, words: int) -> tuple[str, str] | None:
    """La forme : une question ouvre sur trois titres ; un long compte rendu sur deux ; chaque titre est un H2."""
    plain = bool(_ESSENTIEL.search(text) and _POUR_TOI.search(text))
    if has_question(text):
        if not (plain and _GAINS.search(text)):
            return ("question", "une question à Jay s'ouvre sur trois titres : L'essentiel, Pour toi, Gains et limites")
    elif not (words >= LONG_REPORT_WORDS):
        return None
    elif not plain:
        return ("rapport", "un long compte rendu s'ouvre sur L'essentiel et Pour toi")
    return ("format", FORMAT_DETAIL) if _titles_not_h2(text) else None


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
