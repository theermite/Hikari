#!/usr/bin/env python3
"""Journal des invocations d'agents — PostToolUse Agent|Task.

Plan d'action point 1, brique 1.1 (`docs/Plan-Action-Methodologie-2026-09.md`).

POURQUOI. L'audit du 2026-09-03 a mesuré « 2 agents sur 56 apparaissent dans 112
rapports de session » et a dû écrire, honnêtement, que ce chiffre est un
PLANCHER : il vient d'une recherche de texte dans les comptes rendus, faute de
tout journal d'invocation. On ne pilote pas ce qu'on ne mesure pas, et on ne
peut pas prouver qu'un système nerveux fonctionne sans compter les influx.

CE QU'IL FAIT. Une ligne JSON par délégation, en ajout seul, dans
`.claude/state/agent-invocations.jsonl` (dossier ignoré par git : la matière
brute reste locale, seul l'agrégat entre dans un rapport de session).

CE QU'IL NE FAIT PAS. Il ne bloque jamais, il n'avertit jamais, il ne modifie
aucune sortie. Un instrument de mesure qui peut faire échouer la chose mesurée
n'est plus un instrument, c'est une panne. Une erreur interne est donc rattrapée
— mais JOURNALISÉE sur stderr, jamais avalée en silence (`Quality.md`,
« les erreurs sont des données »). Un journal muet qui n'écrit rien serait
indiscernable d'un journal qui mesure zéro : c'est précisément le faux négatif
que ce hook existe pour supprimer.

SANS HOOK (autre harnais). Émettre soi-même, en fin de session, la ligne
`[AGENTS] <n> invocations · <liste des agents>` dans le rapport — la mesure
reste falsifiable, elle perd seulement son automatisme.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root, pass_through, read_hook_input  # type: ignore

JOURNAL_NAME = "agent-invocations.jsonl"

# Le harnais a nommé cet outil `Task` puis `Agent`. Accepter les deux : un
# journal qui rate le nom du jour mesure zéro et se lit comme « personne
# n'a délégué » — exactement le faux négatif qu'on veut supprimer.
AGENT_TOOL_NAMES = {"agent", "task"}

# Le vrai porteur, mesuré le 2026-09-05 : `PostToolUse` sur l'outil n'a rien
# écrit sur deux délégations réelles, dans deux sessions dont une démarrée après
# l'ajout du hook. Le harnais expose des événements dédiés au cycle de vie des
# sous-agents ; l'outil, lui, ne passe pas par PostToolUse.
SUBAGENT_EVENTS = {"subagentstart", "subagentstop"}

# Le nom du champ portant l'agent n'est pas documenté pour ces événements.
# Chercher sous plusieurs clés coûte trois lignes ; se tromper de clé mesure
# zéro et se lit comme « personne n'a délégué ».
AGENT_NAME_KEYS = ("subagent_type", "agent_type", "agent_name", "agent", "name")

# Clés de structure, jamais un nom d'agent — exclues du diagnostic de forme.
STRUCTURAL_KEYS = {"hook_event_name", "session_id", "tool_name", "tool_input",
                   "tool_response", "cwd", "transcript_path", "permission_mode"}


def _debug(stage: str, error: BaseException) -> None:
    """Trace le repli sur stderr. DEBUG : ce chemin est un repli attendu, pas
    un chemin critique — mais il reste lisible, jamais silencieux."""
    print(f"[DEBUG][agent-invocation-journal] {stage}: {type(error).__name__}: {error}",
          file=sys.stderr)


def _text(value: object, fallback: str = "") -> str:
    """Coerce en texte propre, sans jamais lever."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    return str(value).strip() or fallback


def _concerns_us(data: dict) -> str | None:
    """Rend le nom de l'événement à journaliser, ou None."""
    event = _text(data.get("hook_event_name")).lower()
    if event in SUBAGENT_EVENTS:
        return _text(data.get("hook_event_name"))
    if _text(data.get("tool_name")).lower() in AGENT_TOOL_NAMES:
        return "PostToolUse"
    return None


def _find_agent_name(data: dict) -> str:
    """Cherche le nom de l'agent au premier niveau puis dans `tool_input`."""
    nested = data.get("tool_input")
    sources = [data, nested] if isinstance(nested, dict) else [data]
    for source in sources:
        for key in AGENT_NAME_KEYS:
            found = _text(source.get(key))
            if found:
                return found
    return "inconnu"


def _unknown_keys(data: dict) -> list[str]:
    """Les CLÉS non reconnues, jamais leurs valeurs — elles peuvent porter des
    données. Sert à apprendre la forme réelle de l'événement (`Confidentiality`)."""
    return sorted(k for k in data
                  if k not in STRUCTURAL_KEYS and k not in AGENT_NAME_KEYS
                  and k != "description")


def build_entry(data: dict) -> dict | None:
    """Construit la ligne de journal, ou None si l'événement ne nous concerne pas.

    Ne lève jamais : une entrée malformée vaut None, pas une exception.
    """
    if not isinstance(data, dict):
        return None

    event = _concerns_us(data)
    if event is None:
        return None

    nested = data.get("tool_input")
    nested = nested if isinstance(nested, dict) else {}
    response = data.get("tool_response")
    is_error = bool(response.get("is_error")) if isinstance(response, dict) else False

    # Une délégation dont le type n'est pas déclaré reste une délégation.
    # La compter « inconnu » dit la vérité ; la jeter fabrique un faux zéro.
    agent = _find_agent_name(data)

    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "agent": agent,
        "description": _text(data.get("description")) or _text(nested.get("description")),
        "session_id": _text(data.get("session_id"), "inconnue"),
        "ok": not is_error,
    }
    if agent == "inconnu":
        entry["unknown_keys"] = _unknown_keys(data)
    return entry


def journal_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / ".claude" / "state" / JOURNAL_NAME


def append_entry(entry: dict, path: Path) -> bool:
    """Ajoute une ligne. Rend False et journalise si l'écriture échoue."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        _debug("ecriture du journal", error)
        return False
    return True


def _empty_stats() -> dict:
    return {
        "invocations": 0,
        "sessions": 0,
        "agents": {},
        "failures": 0,
        "corrupt_lines": 0,
    }


def _read_journal_text(path: Path) -> str | None:
    """Rend le texte brut, ou None si le journal est illisible."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        # Attendu avant la première délégation — zéro est la bonne réponse.
        return None
    except (OSError, UnicodeDecodeError) as error:
        _debug("lecture du journal", error)
        return None


def _accumulate(stats: dict, sessions: set[str], line: str) -> None:
    """Range une ligne dans les compteurs. Une ligne cassée est comptée à part,
    jamais fatale — sinon un octet abîmé effacerait toute la mesure."""
    try:
        item = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        stats["corrupt_lines"] += 1
        return
    if not isinstance(item, dict):
        stats["corrupt_lines"] += 1
        return
    stats["invocations"] += 1
    agent = _text(item.get("agent"), "inconnu")
    stats["agents"][agent] = stats["agents"].get(agent, 0) + 1
    sessions.add(_text(item.get("session_id"), "inconnue"))
    if item.get("ok") is False:
        stats["failures"] += 1


def read_stats(path: Path) -> dict:
    """Relit le journal et rend le chiffre qui manquait à l'audit.

    Un journal absent vaut zéro, jamais une erreur : avant la première
    délégation, « aucune » est la bonne réponse.
    """
    stats = _empty_stats()
    raw = _read_journal_text(path)
    if raw is None:
        return stats

    sessions: set[str] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            _accumulate(stats, sessions, stripped)

    stats["sessions"] = len(sessions)
    return stats


def main() -> None:
    try:
        _, data = read_hook_input()
        entry = build_entry(data)
        if entry is not None:
            append_entry(entry, journal_path())
    except Exception as error:  # noqa: BLE001 — un journal ne casse jamais son porteur
        _debug("traitement de l'evenement", error)
    pass_through()


if __name__ == "__main__":
    main()
