"""Trace des modeles d'une seance, lue dans son journal (jamais declaree par un relecteur).

Le journal porte le modele de chaque message de l'assistant. Le redacteur est donc celui de la seance
principale, et les relecteurs ceux des sous-agents (dossier `<journal>/subagents/`). Meilleur effort :
un journal illisible donne des modeles vides, jamais une erreur qui bloquerait une mise en service.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

TRACE_FILE = "modeles-relectures.jsonl"


def _models_of(path: Path) -> Counter:
    compte: Counter = Counter()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    message = (json.loads(line) or {}).get("message")
                except (ValueError, AttributeError):
                    continue
                if not isinstance(message, dict):
                    continue
                modele = message.get("model") if message.get("role") == "assistant" else None
                if isinstance(modele, str) and modele and not modele.startswith("<"):
                    compte[modele] += 1
    except OSError:
        pass
    return compte


def session_models(transcript_path) -> dict:
    """{"redacteur": {modele: messages}, "sous_agents": {modele: messages}}."""
    journal = Path(transcript_path)
    sous: Counter = Counter()
    dossier = journal.with_suffix("") / "subagents"
    try:
        for fichier in sorted(dossier.glob("*.jsonl")):
            sous.update(_models_of(fichier))
    except OSError:
        pass
    return {"redacteur": dict(_models_of(journal)), "sous_agents": dict(sous)}


def write_trace(repo_root, transcript_path, head: str, kind: str, date: str) -> None:
    """Ajoute une ligne a `.claude/state/modeles-relectures.jsonl`. Ne leve jamais."""
    try:
        modeles = session_models(transcript_path)
        redacteur = max(modeles["redacteur"], key=modeles["redacteur"].get, default="")
        ligne = {"date": date, "head": head, "kind": kind, "redacteur": redacteur,
                 "sous_agents": sorted(modeles["sous_agents"])}
        dossier = Path(repo_root) / ".claude" / "state"
        dossier.mkdir(parents=True, exist_ok=True)
        with open(dossier / TRACE_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except (OSError, ValueError):
        pass


_SKIP_LINE = re.compile(r"^\s*\[REVIEW-SKIP\]\s+motif\s*:\s*[a-z0-9-]+", re.IGNORECASE | re.MULTILINE)
_VERDICT = re.compile(r"\[REVIEW\][^\n]*?verdict\s*:\s*(PASS|FAIL)", re.IGNORECASE)


def kind_of_clearance(texts) -> str:
    """Ce qui a leve le garde (texte le plus recent d'abord) : « SKIP », « PASS », « FAIL » ou « ? »."""
    for text in texts:
        if _SKIP_LINE.search(text):
            return "SKIP"
        trouve = _VERDICT.search(text)
        if trouve:
            return trouve.group(1).upper()
    return "?"


def record_clearance(texts, transcript, head, find_root) -> None:
    """Appele par le garde quand il laisse passer. Ne leve jamais : une trace manquee ne bloque rien."""
    try:
        write_trace(find_root(), transcript, head=(head or "")[:7] or "?", kind=kind_of_clearance(texts),
                    date=time.strftime("%Y-%m-%d"))
    except Exception:  # noqa: BLE001 -- aucune trace ne doit faire echouer un garde-fou
        return
