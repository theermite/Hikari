#!/usr/bin/env python3
"""UTF-8 French accent check — PostToolUse Write|Edit.

Bonus hook (Paquet 2): detect French content written without proper
accents (UTF-8 regression). Heuristic dictionary of common unaccented
forms that should have been accented.

Scope: Markdown files (.md, .mdx) only — French content lives in docs,
session reports, Notes-Jay. Code files are excluded (English convention).

Detection:
  - Scan added/modified text for unaccented French words
  - If >= 3 distinct violations -> WARN
  - List the violations so Takumi can fix them

This is a non-blocking nudge — accent regression is a chronic small
issue ('UTF-8 saute encore parfois'), not a critical failure.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import get_file_path, pass_through, read_hook_input, warn  # type: ignore

# Markdown extensions only — French content scope
FRENCH_EXTENSIONS = {".md", ".mdx"}

# Common French words frequently written without accents.
# Format: unaccented_form -> correct_form (case-insensitive match).
COMMON_VIOLATIONS = {
    "deja": "déjà",
    "etape": "étape",
    "etapes": "étapes",
    "methode": "méthode",
    "methodes": "méthodes",
    "methodologie": "méthodologie",
    "verifie": "vérifié",
    "verifier": "vérifier",
    "verification": "vérification",
    "execute": "exécuté",
    "executer": "exécuter",
    "execution": "exécution",
    "creer": "créer",
    "cree": "créé",
    "creation": "création",
    "completer": "compléter",
    "qualite": "qualité",
    "systeme": "système",
    "systemes": "systèmes",
    "probleme": "problème",
    "problemes": "problèmes",
    "fonctionnalite": "fonctionnalité",
    "fonctionnalites": "fonctionnalités",
    "securite": "sécurité",
    "necessaire": "nécessaire",
    "donnee": "donnée",
    "donnees": "données",
    "developpement": "développement",
    "developper": "développer",
    "developpe": "développé",
    "decision": "décision",
    "decisions": "décisions",
    "preference": "préférence",
    "preferences": "préférences",
    "experience": "expérience",
    "specifique": "spécifique",
    "regle": "règle",
    "regles": "règles",
    "premiere": "première",
    "derniere": "dernière",
    "apres": "après",
    "tres": "très",
    "geree": "gérée",
    "gerer": "gérer",
    "generale": "générale",
    "operationnel": "opérationnel",
    "operationnelle": "opérationnelle",
    "reference": "référence",
    "references": "références",
    "evite": "évite",
    "eviter": "éviter",
    "ecrit": "écrit",
    "ecrite": "écrite",
    "echec": "échec",
    "etat": "état",
    "etats": "états",
    "ideale": "idéale",
    "controle": "contrôle",
    "controler": "contrôler",
    "modele": "modèle",
    "modeles": "modèles",
    "categorie": "catégorie",
    "interet": "intérêt",
    "interets": "intérêts",
}

# Pre-compile regex: word boundary around each unaccented form.
_pattern = r"\b(" + "|".join(re.escape(w) for w in COMMON_VIOLATIONS.keys()) + r")\b"
VIOLATION_RE = re.compile(_pattern, re.IGNORECASE)

# Threshold: report only if >= N distinct violations to reduce noise
VIOLATION_THRESHOLD = 3

# Skip if file is in these scopes (not user-edited French content)
SKIP_PATH_PARTS = (
    "/node_modules/",
    "\\node_modules\\",
    "/dist/",
    "\\dist\\",
    "/build/",
    "\\build\\",
    "/.next/",
    "\\.next\\",
    "/coverage/",
    "\\coverage\\",
)


def in_french_scope(file_path: str) -> bool:
    if not file_path:
        return False
    p = Path(file_path)
    if p.suffix.lower() not in FRENCH_EXTENSIONS:
        return False
    norm = file_path.replace("\\", "/").lower()
    return not any(part.replace("\\", "/").lower() in norm for part in SKIP_PATH_PARTS)


def get_written_text(data: dict) -> str:
    """Extract content from a Write or Edit tool call."""
    tool_input = data.get("tool_input") or {}
    if "content" in tool_input:
        return tool_input.get("content") or ""
    if "new_string" in tool_input:
        return tool_input.get("new_string") or ""
    return ""


def find_violations(text: str) -> dict[str, int]:
    """Return {unaccented_form_lower: count}."""
    if not text:
        return {}
    counts: dict[str, int] = {}
    for match in VIOLATION_RE.finditer(text):
        key = match.group(1).lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    _, data = read_hook_input()
    file_path = get_file_path(data)
    if not in_french_scope(file_path):
        pass_through()

    text = get_written_text(data)
    if not text:
        pass_through()

    violations = find_violations(text)
    if len(violations) < VIOLATION_THRESHOLD:
        pass_through()

    sorted_v = sorted(violations.items(), key=lambda kv: (-kv[1], kv[0]))
    lines = [
        f"  - '{word}' ({count}x) -> '{COMMON_VIOLATIONS[word]}'"
        for word, count in sorted_v[:10]
    ]
    listing = "\n".join(lines)

    warn(
        f"WARNING: UTF-8 / French accents — {len(violations)} distinct unaccented "
        f"French word(s) detected in {os.path.basename(file_path)} "
        f"(threshold: {VIOLATION_THRESHOLD}). "
        "ACTION: Replace with proper accented forms — non-negotiable per "
        "feedback_french-accents memory. Common fixes:\n"
        f"{listing}\n"
        "If intentional (English section, code block, citation), continue. "
        "See memory feedback_french-accents.md."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
