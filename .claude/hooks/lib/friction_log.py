"""Journal de frictions: une ligne par refus de garde-fou, plus les notes que Takumi y ajoute à la main.

Jay, 2026-11-09: un garde-fou qui refuse à tort doit laisser une trace qu'il retrouve en revenant dans Kata.
Le journal par séance (`hook-blocks-stats`) ne garde que des totaux. Celui-ci garde, par refus: quel
garde-fou, quel outil, quelle cible, quel motif.

Vie privée: il vit dans le dossier personnel (`~/.claude/state/frictions.jsonl`), jamais dans un dépôt.
Il ne reçoit jamais le texte d'une commande (un secret peut s'y trouver): seulement le nom de l'outil et,
pour une commande, son premier mot. Écrire ne casse jamais un garde-fou (échec silencieux).

Arrêt: `FRICTION_LOG_OFF=1` (les tests). Autre emplacement: `FRICTION_LOG=<chemin>`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

COMMANDES_CONNUES = frozenset(
    "git gh npm pnpm npx yarn node python python3 pip uv pytest ruff mix elixir cargo go make docker ssh scp rsync curl "
    "wget rm cp mv mkdir cat ls cd echo sed awk grep find bash sh cmd powershell pwsh tail head wc sort touch chmod "
    "tar unzip systemctl nginx".split())
MAX_MOTIF = 240
MAX_CIBLE = 200


def journal_path() -> Path:
    return Path(os.environ.get("FRICTION_LOG") or Path.home() / ".claude" / "state" / "frictions.jsonl")


def append(evenement: dict, chemin: Path | None = None) -> None:
    """Ajoute une ligne; ne lève jamais (un journal ne doit pas empêcher un refus)."""
    if chemin is None and os.environ.get("FRICTION_LOG_OFF"):
        return  # l'arrêt ne vaut que pour le journal par défaut: un chemin explicite est un choix
    ligne = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **evenement}
    if "motif" in ligne:
        ligne["motif"] = str(ligne["motif"])[:MAX_MOTIF]
    if "cible" in ligne:
        ligne["cible"] = str(ligne["cible"])[:MAX_CIBLE]
    try:
        cible = Path(chemin) if chemin else journal_path()
        cible.parent.mkdir(parents=True, exist_ok=True)
        with cible.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except OSError:
        return


def note(texte: str, projet: str = "", chemin: Path | None = None) -> None:
    """La note de Takumi quand il juge un refus injustifié: marquée `manuel`, lue par Jay dans Kata."""
    append({"manuel": True, "projet": projet, "motif": texte}, chemin=chemin)


def refus(message: str, donnees: dict, garde: str) -> None:
    """Le refus d'un garde-fou. La cible est un chemin, ou le premier mot d'une commande — jamais la commande."""
    donnees = donnees if isinstance(donnees, dict) else {}
    outil = donnees.get("tool_name", "")
    append({"garde": garde, "outil": outil, "cible": _cible(outil, donnees.get("tool_input")),
            "motif": message.removeprefix("BLOCKED:").strip(), "session": donnees.get("session_id", "")})


def _cible(outil: str, entree: object) -> str:
    entree = entree if isinstance(entree, dict) else {}
    if entree.get("file_path"):
        return str(entree["file_path"])
    if outil != "Bash":
        return ""
    mots = str(entree.get("command", "")).split()
    # Le premier mot peut être un secret (`TOKEN=x git push`, `sk-…`, `https://u:p@h`): une forme ne le distingue pas
    # d'un nom de commande (relecture 2026-11-09, deux passages). On ne garde donc qu'une liste fermée de commandes.
    return mots[0] if mots and mots[0] in COMMANDES_CONNUES else "autre"


def lire(chemin: Path | None = None) -> list[dict]:
    try:
        lignes = (Path(chemin) if chemin else journal_path()).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    sortie = []
    for ligne in lignes:
        try:
            sortie.append(json.loads(ligne))
        except ValueError:
            continue
    return sortie


def _lignes_refus(refus_auto: list[dict], top: int) -> list[str]:
    exemples = {}
    for e in refus_auto:
        exemples.setdefault(e.get("garde", "?"), e)
    return [f"- {n} × {garde} — {exemples[garde].get('motif', '')[:90]}"
            for garde, n in Counter(e.get("garde", "?") for e in refus_auto).most_common(top)]


def resume(evenements: list[dict], top: int = 4) -> str:
    """Le résumé court: total, garde-fous les plus fréquents, notes à la main."""
    refus_auto = [e for e in evenements if not e.get("manuel")]
    notes = [e for e in evenements if e.get("manuel")]
    tete = f"Frictions: {len(evenements)} nouvelle(s) ligne(s) ({len(refus_auto)} refus, {len(notes)} note(s) à la main)."
    lignes_notes = [f"- note ({e.get('projet') or '?'}): {e.get('motif', '')[:160]}" for e in notes[-top:]]
    return "\n".join([tete, *_lignes_refus(refus_auto, top), *lignes_notes])


def _main(argv: list[str]) -> int:
    """`python .claude/hooks/lib/friction_log.py "texte"`: Takumi note un refus injustifié, sans quitter son travail."""
    texte = " ".join(argv).strip()
    if not texte:
        print("usage: friction_log.py <note>", file=sys.stderr)
        return 2
    note(texte, projet=Path.cwd().name)
    print("noté dans le journal de frictions")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
