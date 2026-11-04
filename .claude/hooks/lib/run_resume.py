#!/usr/bin/env python3
"""Resume a stopped autonomous run on Jay's order: the brief is COMPUTED, never written from memory.

Born 2026-11-04 (Jay: hot resume of a run is missing; chosen form = "reprise sur ton ordre"). A run stops (token
limit, cut, blocking checkpoint). Jay says "reprends": this tool reads the autonomy contract and the run journal
(`docs/Sessions/run-<date>.jsonl`) and says what is proven, what to redo, what comes next, or why not to resume.

Journal: `docs/Sessions/run-<date>.jsonl`, strict JSON lines written by `run_journal.py` (see its docstring): one
`brique` event per attempt, `arret` when the run stops, `point_valide` on Jay's word. READ CLOSED: any line that is
not a valid event stops the resume. The closed list of bricks is the contract's `scope` (brique, lot) or `briques`
(projet): no PET is parsed.

A brick is PROVEN only if its LAST attempt says livré=true, names the command and its output (text, not a dash), and
carries a SHA that git knows ("a command output or a SHA, never a checkbox"). The tool never launches anything: it
refuses to resume when the contract is void or does not lint, or when the budget is spent; it WAITS when a blocking
checkpoint (or a milestone naming no brick) is not validated, when a line of the journal is unreadable, or when a cost
is null or not a number (an unmeasured spend is never counted as zero: a warning stops nothing, so it is a stop).
Known limits: a SHA proves a commit exists, not that the brick's work is in it (a shared SHA is flagged);
`point_valide` is written in the journal, so it is only as honest as the run that writes it, and Jay must dictate it;
`tokens_max` and `duree_max_h` are not checked here, only the cost ceiling; a cost of 0 is a number and is accepted.

Usage:
    python .claude/hooks/lib/run_resume.py docs/Contrat-Autonomie.md docs/Sessions/run-2026-11-04-1500.jsonl \
        --cdc-version 0.6.0 --pet-version 0.9.0 [--repo .]

Exit codes: 0 resume (or nothing left) · 1 refused / waiting for Jay · 2 unreadable input.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract_lint as cl  # noqa: E402
from run_journal import Journal, JournalError, brick_id, parse_journal  # noqa: E402,F401

_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_YES = {"oui", "yes", "true", "✅"}
_PROOF_TEXT = re.compile(r"\w")  # a dash or an empty cell is not a command or an output


@dataclass(frozen=True)
class Context:
    """Where and against what the journal is judged (one object, not six loose parameters)."""
    repo: Path
    cdc_version: str | None = None
    pet_version: str | None = None


@dataclass
class Plan:
    status: str = "reprendre"  # reprendre | attendre | refuser | terminé
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    proven: list = field(default_factory=list)
    redo: list = field(default_factory=list)
    next_brick: str | None = None
    checkpoints: list = field(default_factory=list)  # blocking, waiting for Jay
    digest: list = field(default_factory=list)       # non-blocking, to tell Jay
    spent: float = 0.0
    ceiling: float | None = None
    unknown_costs: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)
    labels: dict = field(default_factory=dict)    # UPPER id -> id as the contract (or the journal) writes it
    redo_why: dict = field(default_factory=dict)  # UPPER id -> why the brick is redone


def _git_knows(repo: Path, sha: str) -> bool:
    if not _SHA.match(sha):
        return False
    try:
        done = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(repo), capture_output=True)
    except OSError:
        return False
    return done.returncode == 0


def _is_proof(row: dict, repo: Path) -> bool:
    return (not row["_malformed"] and row.get("livre", "").lower() in _YES
            and bool(_PROOF_TEXT.search(row.get("commande", ""))) and bool(_PROOF_TEXT.search(row.get("sortie", "")))
            and _git_knows(repo, row.get("sha", "").lower()))


def _spend(rows: list, plan: Plan) -> float:
    """Total of the readable costs. An absent, unreadable or malformed cost makes the spend UNKNOWN (plan.unknown_costs)."""
    total = 0.0
    for row in rows:
        cost = row["cout"]
        if cost is None:
            plan.unknown_costs.append(row["brique"] or "?")
        else:
            total += cost
    return total


def _acknowledged(front: dict) -> set:
    done = front.get("points_valides") or []
    return {str(x) for x in (done if isinstance(done, list) else [done])}


def _classify(contract: dict, journal: Journal, order: list, plan: Plan) -> None:
    """A checkpoint is triggered when its brick is proven OR when `apres` names no brick of the order (a milestone):
    what cannot be placed is waiting, never ignored."""
    done = _acknowledged(journal.front)
    for point in contract.get("checkpoints") or []:
        after = brick_id(str(point.get("apres", "")))
        if (after in plan.proven or after not in order) and str(point.get("id")) not in done:
            (plan.checkpoints if point.get("bloquant") else plan.digest).append(point)


def _budget(contract: dict, plan: Plan) -> None:
    budget = contract.get("budget") or {}
    ceiling = budget.get("cout_max_usd")
    plan.ceiling = ceiling
    if not isinstance(ceiling, (int, float)):
        return
    if plan.spent >= ceiling * budget.get("arret_pct", 100) / 100:
        plan.reasons.append(f"budget épuisé : {plan.spent:.2f} USD dépensés sur un plafond de {ceiling} USD")
    elif plan.spent >= ceiling * budget.get("alerte_pct", 80) / 100:
        plan.warnings.append(f"alerte budget : {plan.spent:.2f} USD sur {ceiling} USD")


def _order(contract: dict) -> list:
    """The closed list of bricks: `scope` (brique, lot) or `briques` (projet); the contract lint guarantees both."""
    ids = contract.get("briques") if contract.get("mode") == "projet" else contract.get("scope")
    return [brick_id(b) for b in ids] if isinstance(ids, list) else []


def _contract_labels(contract: dict) -> dict:
    ids = contract.get("briques") if contract.get("mode") == "projet" else contract.get("scope")
    return {brick_id(b): b.strip() for b in ids if isinstance(b, str)} if isinstance(ids, list) else {}


def _warn_shared_shas(rows: list, proven: list, plan: Plan) -> None:
    by_sha: dict = {}
    for row in rows:
        if row["brique"] in proven:
            by_sha.setdefault(row.get("sha", "").lower(), []).append(row["brique"])
    for sha, bricks in by_sha.items():
        if len(set(bricks)) > 1:
            plan.warnings.append(f"même SHA {sha[:7]} pour {', '.join(sorted(set(bricks)))} : vérifier que chaque brique a son commit")


def plan_resume(contract: dict, journal: Journal, ctx: Context) -> Plan:
    plan = Plan()
    errors = [v for v in cl.lint(contract, cdc_version=ctx.cdc_version, pet_version=ctx.pet_version)
              if v.severity == "error"]
    if errors:  # a malformed contract is refused here: nothing below may read its fields
        plan.reasons = [f"{v.code}: {v.message}" for v in errors]
        plan.status = "refuser"
        return plan
    last = {}
    for row in journal.rows:
        last[row["brique"]] = row
    plan.unreadable = [f"ligne {n} du journal illisible (JSON invalide, type inconnu, champ manquant ou d'un autre type)" for n in journal.orphans]
    plan.proven = [b for b, r in last.items() if _is_proof(r, ctx.repo)]
    plan.redo = [b for b in last if b not in plan.proven]
    plan.redo_why = {b: ("dernière tentative non livrée" if last[b]["livre"] != "oui"
                         else "preuve incomplète (commande, sortie ou SHA connu de git)") for b in plan.redo}
    plan.labels = {**{b: r["ecrit"] for b, r in last.items()}, **_contract_labels(contract)}
    plan.spent = _spend(journal.rows, plan)
    _budget(contract, plan)
    order = _order(contract)
    plan.warnings += [f"brique {b} prouvée mais hors du périmètre du contrat" for b in plan.proven
                      if order and b not in order]
    _warn_shared_shas(journal.rows, plan.proven, plan)
    plan.next_brick = next((b for b in order if b not in plan.proven), None)
    _classify(contract, journal, order, plan)
    return _decide(plan, bool(order))


def _decide(plan: Plan, has_order: bool) -> Plan:
    if plan.reasons:
        plan.status, plan.next_brick = "refuser", None
    elif plan.unknown_costs or plan.unreadable:
        plan.status, plan.next_brick = "attendre", None
        if plan.unknown_costs:
            plan.reasons.append("coût manquant ou illisible pour " + ", ".join(sorted({plan.labels.get(b, b) for b in plan.unknown_costs}))
                                + " : dépense inconnue, écris le coût de chaque tentative dans le journal (en USD)")
        plan.reasons += plan.unreadable
    elif plan.checkpoints:
        plan.status = "attendre"
    elif has_order and plan.next_brick is None:
        plan.status = "terminé"
    return plan


def render_brief(plan: Plan, journal: Journal) -> str:
    lines = [f"REPRISE DU RUN — {plan.status.upper()}", f"Arrêt noté : {journal.front.get('raison', 'non précisé')}"]
    name = lambda b: plan.labels.get(b, b)  # noqa: E731 - display only
    lines += [f"Prouvé : {name(b)} (SHA {journal_sha(journal, b)})" for b in plan.proven] or ["Prouvé : rien"]
    lines += [f"À refaire : {name(b)} ({plan.redo_why[b]})" for b in plan.redo]
    if plan.status == "reprendre":
        lines.append(f"Prochaine brique : {name(plan.next_brick)}")
    lines += [f"{'REFUS' if plan.status == 'refuser' else 'ARRÊT'} : {r}" for r in plan.reasons]
    lines += [f"En attente de Jay — point {p['id']} : {p.get('jay_verifie')}" for p in plan.checkpoints]
    lines += [f"À signaler (digest) — point {p['id']} : {p.get('jay_verifie')}" for p in plan.digest]
    lines += [f"Attention : {w}" for w in plan.warnings]
    if plan.ceiling:
        lines.append(f"Budget : {plan.spent:.2f} / {plan.ceiling} USD")
    return "\n".join(lines)


def journal_sha(journal: Journal, brick: str) -> str:
    rows = [r for r in journal.rows if r.get("brique") == brick]
    return (rows[-1].get("sha", "")[:7]) if rows else "?"


def _is_git_repo(path: Path) -> bool:
    try:
        return subprocess.run(["git", "rev-parse", "--git-dir"], cwd=str(path), capture_output=True).returncode == 0
    except OSError:
        return False


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute the resume brief of a stopped autonomous run.")
    parser.add_argument("contract")
    parser.add_argument("journal")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--cdc-version")
    parser.add_argument("--pet-version")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if cl.yaml is None:
        print("run-resume: PyYAML is missing. Install it: pip install pyyaml", file=sys.stderr)
        return 2
    if not _is_git_repo(Path(args.repo)):
        print(f"run-resume: --repo {args.repo!r} is not a git repository", file=sys.stderr)
        return 2
    try:
        contract = cl.load_frontmatter(Path(args.contract).read_text(encoding="utf-8-sig"))
        journal = parse_journal(Path(args.journal).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"run-resume: {exc}", file=sys.stderr)
        return 2
    plan = plan_resume(contract, journal, Context(Path(args.repo), args.cdc_version, args.pet_version))
    print(render_brief(plan, journal))
    return 0 if plan.status in ("reprendre", "terminé") else 1


if __name__ == "__main__":
    sys.exit(main())
