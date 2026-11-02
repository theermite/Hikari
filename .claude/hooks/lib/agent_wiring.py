"""Câblage des experts : quel expert un commit exige, et a-t-il été lancé ?

Lit `.claude/rules-ondemand/agents-wiring.json` (le registre) et le journal des lancements d'agents du dépôt
(`.claude/state/agent-invocations.jsonl`, événement SubagentStart). Rien ici ne lit une commande : tout vient de
git et du journal, pour qu'aucune forme de commande ne puisse passer à côté (leçon du garde du README, 2026-10-30).
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / "rules-ondemand" / "agents-wiring.json"
JOURNAL = Path(".claude") / "state" / "agent-invocations.jsonl"
MAX_COMMITS = 50   # a repository with no remote holds everything: look at the recent ones only


def load_registry(path: Path | None = None) -> dict:
    return json.loads((path or REGISTRY).read_text(encoding="utf-8"))


def agent_key(name: str) -> str:
    """« Payment Master » = payment-master = paymentmaster."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def experts_for(files: list[str], diff: str = "", registry: dict | None = None) -> set[str]:
    """The experts the blocking triggers require for these changed files (and the lines this commit added)."""
    reg = registry or load_registry()
    skip = re.compile(reg["exclusion_par_defaut"], re.IGNORECASE)
    wanted: set[str] = set()
    for trigger in reg["declencheurs"]:
        if trigger.get("mode") != "bloquant":
            continue
        path = re.compile(trigger["chemin"], re.IGNORECASE)
        hit = any(path.search(f) and not skip.search(f) for f in (p.replace("\\", "/") for p in files))
        if hit and trigger.get("diff"):
            hit = bool(re.search(trigger["diff"], diff, re.MULTILINE))
        if hit:
            wanted.add(trigger["agent"])
    return wanted


def reminders_for(path: str, registry: dict | None = None) -> list[tuple[str, str]]:
    """(agent, trigger id) of the reminder triggers one file path matches; tests and documents never remind."""
    reg = registry or load_registry()
    normal = str(path).replace("\\", "/")
    if re.search(reg["exclusion_par_defaut"], normal, re.IGNORECASE):
        return []
    return [(t["agent"], t["id"]) for t in reg["declencheurs"]
            if t.get("mode") == "rappel" and re.search(t["chemin"], normal, re.IGNORECASE)]


def _git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def unpushed_commits(root: Path) -> list[tuple[str, int]]:
    """(sha, author time: amend and rebase keep it, the committer time they reset) of the commits no remote holds yet, newest first."""
    out = _git(root, "log", f"-n{MAX_COMMITS}", "--format=%H %at", "HEAD", "--not", "--remotes")
    pairs = []
    for line in (out or "").splitlines():
        sha, _, when = line.partition(" ")
        if sha and when.isdigit():
            pairs.append((sha, int(when)))
    return pairs


def commit_files(root: Path, sha: str) -> list[str]:
    out = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha)
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def commit_diff(root: Path, sha: str) -> str:
    return _git(root, "show", "--format=", "--unified=0", sha) or ""


def launches(root: Path) -> dict[str, list[datetime]]:
    """Launch times per agent key, read from the repository's journal. Unreadable lines are skipped."""
    found: dict[str, list[datetime]] = {}
    try:
        lines = (root / JOURNAL).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return found
    for line in lines:
        try:
            event = json.loads(line)
            if event.get("event") != "SubagentStart":
                continue
            found.setdefault(agent_key(event.get("agent") or ""), []).append(datetime.fromisoformat(event["at"]))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return found


def missing_experts(root: Path, commit_time: int, wanted: set[str], registry: dict | None = None) -> list[str]:
    """The experts in `wanted` with no launch since a little before the commit was made."""
    reg = registry or load_registry()
    since = datetime.fromtimestamp(commit_time).astimezone() - timedelta(minutes=reg["fenetre_avant_commit_minutes"])
    seen = launches(root)
    return sorted(a for a in wanted if not any(t >= since for t in seen.get(agent_key(a), [])))
