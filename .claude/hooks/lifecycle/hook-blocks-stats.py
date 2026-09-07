#!/usr/bin/env python3
"""hook-blocks-stats.py — SessionEnd observability (A2: guardrail-fatigue meter).

Counts how often each hook BLOCKED or WARNED during the session, grouped by a
normalized signature (the short reason after "BLOCKED:" / "WARNING:"). Appends
one cumulative entry per session to <repo>/.claude/state/hook-blocks.jsonl.

Why this exists
---------------
The methodology has ~30 hooks. Some block legitimately, some create friction
(false positives). Today there is no measure of WHICH guardrail fires most.
This meter surfaces that signal so a chronically-blocking hook can be reviewed
(reclassified WARN, relaxed, or fixed) BEFORE the friction pushes Takumi or Jay
to bypass it. It reads the transcript in aggregate — zero change to the 30 hooks.

What it measures (and what it does NOT)
---------------------------------------
- Measures: FREQUENCY of blocks/warns per reason. A good proxy for friction.
- Does NOT yet distinguish a justified block from a false positive. That needs
  correlation with a later successful retry/skip — a v2 refinement.

Design choices
--------------
- Only NON-assistant transcript entries are scanned, so Takumi's own citations
  of "BLOCKED:" in prose are never counted (only real hook output is).
- Lines whose reason contains <...> placeholders are skipped (RECOVERY/templates).
- Pure observability: this hook NEVER blocks. It always exits 0, swallowing any
  I/O error (a meter must never break a session).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import find_repo_root  # noqa: E402
from friction import detect_overcome_blocks, signature  # noqa: E402
from transcript_reader import iter_entries  # noqa: E402

# Le marqueur arrive RAREMENT en debut de ligne. Le harnais le prefixe du nom de
# l'evenement et du chemin du garde-fou :
#   PreToolUse:Bash hook error: [bash ".../_run.sh" guards/bash-guard.py]: BLOCKED: ...
# Exiger `^` perdait donc les BLOCAGES en priorite — ceux qui comptent le plus.
# Mesure du 2026-09-07 sur une session reelle : 92 marqueurs presents, 30 comptes.
# Le marqueur ouvre la ligne, OU suit le prefixe du harnais (`]: ` / `hook error: `).
# Ce cadrage est ce qui separe un evenement d'un simple TEXTE qui parle de blocage :
# en elargissant naivement a « n'importe ou dans la ligne », le compteur s'est mis a
# compter le code source qu'on venait de LIRE — 69 blocages annonces au lieu de 26,
# mesure du 2026-09-07. Un compteur qui gonfle ment autant qu'un compteur muet.
MARKER_RE = re.compile(
    r"(?:^|\]:[ \t]|hook error:[ \t])(BLOCKED|WARNING):[ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)

# Une ligne qui n'est QU'un gabarit commence par un chevron : c'est une doc, pas
# un evenement. Un vrai blocage, lui, porte presque toujours un `<exemple>` dans
# son texte d'aide — l'ecarter pour ce motif jetait 12 occurrences reelles sur la
# seule session mesuree. On teste donc le DEBUT du motif, jamais sa presence.
GABARIT_RE = re.compile(r"^\s*<[^>]+>")

# Un vrai evenement OUVRE sa ligne. Liste FERMEE des cinq formes MESUREES :
# le harnais annonce l'evenement (`PreToolUse:` / `PostToolUse:`), le message
# arrive nu (`BLOCKED:` / `WARNING:`), ou la commande du garde-fou ouvre la ligne
# quand le prefixe est alle a la ligne precedente (`[bash "`, `[HOOK=`).
#
# POURQUOI UN CRITERE POSITIF, ET NON UNE LISTE DE CE QU'IL FAUT ECARTER.
# Premiere tentative du 2026-09-07 : ecarter les lignes commencant par un diese
# ou une citation. Relecture independante, mesure a l'appui — il restait 26 % de
# gonflement, car une ligne de code commence tout aussi bien par `msg = ` ou par
# le `+` d'un diff. Une liste d'exclusions est OUVERTE : la forme suivante la
# depasse toujours.
#
# ET UNE LISTE D'INCLUSIONS FERMEE TROP TOT MENT DANS L'AUTRE SENS. Deuxieme
# relecture, sur un modele different : la 5e forme (`[HOOK=`) existe dans 55
# fichiers de session, et le compteur perdait donc de vrais blocages
# PostToolUse. J'avais mesure UN seul canal (le resultat d'outil) avant de
# declarer la liste close. Une liste fermee ne vaut que par l'etendue de ce
# qu'on a regarde — d'ou le test qui relit de VRAIS transcripts et echoue sur
# toute forme non couverte (`test_hook_blocks_shapes.py`).
EVENEMENT_RE = re.compile(r'^(?:(?:Pre|Post)ToolUse:|BLOCKED:|WARNING:|\[bash "|\[HOOK=)')

STATE_REL = ".claude/state/hook-blocks.jsonl"


def read_input() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return {}


def entry_role(entry: object) -> str:
    """Best-effort role extraction (transcript shape varies: nested or flat)."""
    if not isinstance(entry, dict):
        return ""
    msg = entry.get("message")
    if isinstance(msg, dict):
        return msg.get("role") or ""
    return entry.get("role", "") or ""


def extract_text(node: object) -> str:
    """Collect every string in a nested transcript entry, joined by newlines."""
    chunks: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, str):
            chunks.append(n)
        elif isinstance(n, dict):
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return "\n".join(chunks)


def scan(transcript_path: str) -> tuple[dict[str, int], dict[str, int], int]:
    """Compte les blocages et avertissements, et DIT combien d'entrees il a lues.

    Le nombre d'entrees lues est la seule chose qui rende un zero croyable : sans
    lui, « aucun garde-fou n'a parle » et « le compteur n'a rien lu » s'ecrivent
    pareil. C'est ce qui a masque le defaut pendant trois mois.
    """
    blocks: dict[str, int] = {}
    warns: dict[str, int] = {}
    lues = 0
    for entry in iter_entries(transcript_path):
        lues += 1
        if entry_role(entry) == "assistant":
            continue  # Takumi quoting a message is not a real block
        for kind, sig in _evenements(extract_text(entry)):
            bucket = blocks if kind == "BLOCKED" else warns
            bucket[sig] = bucket.get(sig, 0) + 1
    return blocks, warns, lues


def _evenements(text: str) -> set[tuple[str, str]]:
    """Les evenements DISTINCTS d'une entree — un resultat d'outil, un evenement.

    Le meme texte apparait a deux endroits d'un resultat d'outil. Chaque blocage
    etait donc compte double (mesure du 2026-09-07, sur les trois entrees
    concernees). Un compteur juste a un facteur deux pres est un compteur qui
    ment. Deux motifs DIFFERENTS dans une meme entree comptent bien pour deux.
    """
    trouves: set[tuple[str, str]] = set()
    for ligne in text.splitlines():
        if not EVENEMENT_RE.match(ligne):
            continue  # du texte qui PARLE de blocage n'est pas un blocage
        for kind, reason in MARKER_RE.findall(ligne):
            if GABARIT_RE.match(reason):
                continue  # une ligne qui n'est QU'un gabarit, pas un evenement
            sig = signature(reason)
            if sig:
                trouves.add((kind, sig))
    return trouves


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_journal(session_id: str, blocks: dict, warns: dict, overcome: dict,
                    lues: int) -> None:
    entry = {"session_id": session_id, "ts": now_iso(),
             "blocks": blocks, "warns": warns, "overcome": overcome, "lues": lues}
    state_path = find_repo_root() / STATE_REL
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # observability must never break the session


def _emit_summary(blocks: dict, warns: dict, overcome: dict) -> None:
    total_b, total_w = sum(blocks.values()), sum(warns.values())
    top = (max(blocks.items(), key=lambda kv: kv[1], default=None)
           or max(warns.items(), key=lambda kv: kv[1], default=None))
    top_str = f" — top: {top[0]} (x{top[1]})" if top else ""
    print(f"hook-blocks: {total_b} block(s), {total_w} warn(s) this session{top_str}", file=sys.stderr)
    if overcome:
        cand = ", ".join(sorted(overcome))
        print(f"hook-friction: {sum(overcome.values())} block(s) overcome by retry "
              f"(possible parasite): {cand}. If any hindered you, note it under "
              f"'Hooks Friction' in MNK-GoRin-Notes-Jay.md.", file=sys.stderr)


def main() -> None:
    data = read_input()
    transcript_path = data.get("transcript_path") or os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = data.get("session_id") or os.environ.get("CLAUDE_SESSION_ID", "")
    if not transcript_path:
        sys.exit(0)
    blocks, warns, lues = scan(transcript_path)
    overcome = detect_overcome_blocks(transcript_path)
    # Une session calme laisse une trace, elle aussi. Sans elle, « rien ne s'est
    # passe » et « le compteur est casse » s'ecrivent pareil — et c'est ce qui a
    # laisse croire pendant trois mois que nos garde-fous se taisaient : 115
    # sessions ecrites dans ce depot, 5 lignes au journal.
    _append_journal(session_id, blocks, warns, overcome, lues)
    if blocks or warns:
        _emit_summary(blocks, warns, overcome)
    sys.exit(0)


if __name__ == "__main__":
    main()
