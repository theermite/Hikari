#!/usr/bin/env python3
"""Convocation par la matière — PreToolUse Write|Edit. SUGGÈRE, ne bloque jamais.

Plan d'action point 1 · `docs/Routage-Experts.md`, famille MATIÈRE.

POURQUOI CE HOOK EXISTE. Le texte d'une commande ne peut pas prévoir quel fichier
sera touché. Aucune étape de `/dev` ne dira jamais, au bon moment, « ce fichier est
de l'Elixir, convoque l'expert Elixir » — seul le fichier le sait, à l'instant où on
l'écrit. La famille GESTE est portée par les commandes ; la famille MATIÈRE n'avait
aucun porteur. C'est celui-ci.

CE QU'IL NE FAIT PAS. Il ne bloque pas, il n'interrompt pas, il ne refuse rien.
Mesure du 2026-08-30 : un garde-fou fait de mots génériques (« thème », « animation »)
bloquait une fiche produit e-commerce banale, et la leçon écrite ce jour-là est nette —
**un garde-fou qui gêne le travail légitime finit débranché, et emporte la détection
réelle avec lui.** Celui-ci se contente de rappeler qui existe.

UNE FOIS PAR EXPERT ET PAR SESSION. Une suggestion à chaque fichier deviendrait du
bruit, et le bruit se filtre mentalement en trois minutes.

SANS HOOK (autre harnais). Lire le tableau MATIÈRE de `docs/Routage-Experts.md` avant
d'écrire, et déclarer dans le rapport quel expert a été convoqué — ou pourquoi aucun.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root, pass_through, read_hook_input  # type: ignore

ETAT = "matter-expert-suggested.json"

# La matière prime sur l'extension : un webhook Stripe en TypeScript appelle le
# paiement, pas la façade. L'ordre de cette liste EST la priorité.
MATIERE: list[tuple[str, str]] = [
    (r"(^|/)(stripe|payment|paiement|checkout|billing)(/|_|-|\.)", "paiement (chemin Critical)"),
    (r"(^|/)\.github/workflows/.*\.ya?ml$", "integration continue"),
    (r"(^|/)(Dockerfile|docker-compose\.ya?ml|compose\.ya?ml)$|(^|/)nginx/", "infrastructure"),
    (r"(^|/)(package\.json|pnpm-lock\.ya?ml|package-lock\.json|uv\.lock|"
     r"pyproject\.toml|requirements\.txt|mix\.lock|Cargo\.lock)$", "dependances"),
    (r"\.(ex|exs)$|(^|/)mix\.exs$", "Elixir / Phoenix"),
    (r"\.rs$|(^|/)Cargo\.toml$", "Rust"),
    (r"(^|/)tauri\.conf\.json$|(^|/)electron/", "application de bureau"),
    (r"(^|/)(obs|streaming|overlays?)/|\.(obsscene)$", "diffusion video"),
    (r"(^|/)(rag|embeddings?|ollama)(/|_|-|\.)", "intelligence artificielle et RAG"),
    (r"(^|/)(migrations?|schema)/|\.sql$", "base de donnees"),
    (r"\.(tsx|jsx)$", "facade"),
]

# Un test n'est pas une décision d'architecture : l'expert n'a rien à y faire.
EXCLUS = re.compile(r"(^|/)(tests?|__tests__|spec)/|_test\.|\.test\.|\.spec\.", re.I)


def expert_pour(chemin: str) -> str | None:
    """Rend l'expert que cette matière désigne, ou None — ne rien dire est la
    bonne réponse la plupart du temps."""
    if not chemin:
        return None
    normalise = str(chemin).replace("\\", "/")
    if EXCLUS.search(normalise):
        return None
    for motif, expert in MATIERE:
        if re.search(motif, normalise, re.I):
            return expert
    return None


def _chemin_etat() -> Path:
    return find_repo_root() / ".claude" / "state" / ETAT


def doit_suggerer(expert: str, chemin_etat: Path | None = None) -> bool:
    """Vrai une seule fois par expert. Un état illisible ne fait jamais taire le
    hook — mieux vaut une suggestion de trop qu'un silence par panne."""
    chemin = Path(chemin_etat) if chemin_etat else _chemin_etat()
    deja: list[str] = []
    try:
        deja = json.loads(chemin.read_text(encoding="utf-8"))
        if not isinstance(deja, list):
            deja = []
    except (OSError, ValueError, json.JSONDecodeError):
        deja = []
    if expert in deja:
        return False
    deja.append(expert)
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(deja, ensure_ascii=False), encoding="utf-8", newline="\n")
    except OSError as error:
        print(f"[DEBUG][matter-expert-suggest] etat non ecrit: {error}", file=sys.stderr)
    return True


def build_decision(data: dict, deja_suggere=None) -> dict | None:
    """Rend l'avertissement, ou None. Ne lève jamais."""
    if not isinstance(data, dict):
        return None
    entree = data.get("tool_input")
    if not isinstance(entree, dict):
        return None
    expert = expert_pour(str(entree.get("file_path") or ""))
    if expert is None:
        return None
    verifie = deja_suggere or doit_suggerer
    if not verifie(expert):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"[ROUTAGE] Cette matiere designe un expert : **{expert}**. "
                f"Le convoquer n'est pas obligatoire a chaque fichier — le declencheur "
                f"est la DECISION (nouvelle structure, choix d'architecture, chemin "
                f"Critical, blocage repete). Sinon, ecrire une ligne dans le rapport : "
                f"« aucun expert convoque — <raison> ». Tableau : docs/Routage-Experts.md"
            ),
        }
    }


def main() -> None:
    try:
        _, data = read_hook_input()
        decision = build_decision(data)
        if decision is not None:
            print(json.dumps(decision, ensure_ascii=False))
            return
    except Exception as error:  # noqa: BLE001 — une suggestion ne casse jamais une ecriture
        print(f"[DEBUG][matter-expert-suggest] {type(error).__name__}: {error}", file=sys.stderr)
    pass_through()


if __name__ == "__main__":
    main()
