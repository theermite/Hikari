#!/usr/bin/env python3
"""Validate an autonomy contract (`docs/Contrat-Autonomie.md`) before a run starts.

Born 2026-10-17 (Jay: "if it can be code, make it code"). The contract authorises
a long autonomous run, so its validity is decided by this linter, never by an
agent reading it. The run does not start on any error.

Python is the arbiter: Dogu ports these rules to Elixir and replays
`.claude/hooks/tests/test_contract_lint.py` as its conformance suite. A rule added
here without a test there does not exist.

Usage:
    python .claude/hooks/lib/contract_lint.py docs/Contrat-Autonomie.md \
        --cdc-version 0.6.0 --pet-version 0.9.0 --history costs.json [--remaining 12]

Exit codes: 0 valid (warnings allowed) · 1 at least one error · 2 unreadable input.
`--history` is a JSON list of per-brick costs in USD taken from previous run
journals. With no history the estimate is reported as unavailable: a made-up
number would be worse than none.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # reported as a clean exit 2 by main(), never a traceback
    yaml = None

DELETE = object()  # sentinel for tests: remove a key from a contract

MODES = ("brique", "lot", "projet")
DEPLOY_POLICIES = ("jamais", "staging", "prod-apres-checkpoint")
VERIFICATIONS = ("script_navigateur", "commande", "geste_jay")
ESTIMATE_MARGIN = 1.5  # starting point, not yet measured: recalibrate on real runs


class ContractFormatError(ValueError):
    """The file has no readable YAML front matter."""


@dataclass(frozen=True)
class Violation:
    code: str
    severity: str  # "error" | "warning"
    message: str


@dataclass(frozen=True)
class Context:
    cdc_version: str | None = None
    pet_version: str | None = None
    cost_history: list = field(default_factory=list)
    remaining_bricks: int | None = None


def _error(code: str, message: str) -> Violation:
    return Violation(code, "error", message)


def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _positive(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:  # an integer too large for a float
        return False


def check_closed_brick_list(data: dict) -> list[Violation]:
    """Mode projet: the bricks are a CLOSED list written in the contract (from the PET roadmap), never guessed later."""
    if data.get("mode") != "projet":
        return []
    ids = data.get("briques")
    ok = (isinstance(ids, list) and ids and all(isinstance(b, str) and b.strip() for b in ids)
          and len({b.strip().upper() for b in ids}) == len(ids))
    return [] if ok else [_error("briques_invalid", "mode projet needs `briques`: a non-empty list of distinct brick ids")]


def check_mode_and_scope(data: dict) -> list[Violation]:
    mode, scope = data.get("mode"), data.get("scope")
    if mode not in MODES:
        return [_error("mode_invalid", f"mode must be one of {MODES}, got {mode!r}")]
    named = isinstance(scope, list) and all(isinstance(b, str) and b.strip() for b in scope) \
        and len({b.strip().upper() for b in scope}) == len(scope)
    ok = {
        "brique": named and len(scope) == 1,
        "lot": named and len(scope) >= 2,
        "projet": scope == "all",
    }[mode]
    if ok:
        return []
    return [_error("scope_mismatch", f"scope {scope!r} does not fit mode {mode!r}")]


def check_budget(data: dict) -> list[Violation]:
    budget = data.get("budget")
    if not isinstance(budget, dict):
        return [_error("budget_missing", "a measured budget is mandatory")]
    ceilings = ("cout_max_usd", "tokens_max", "duree_max_h")
    if not all(_positive(budget.get(key)) for key in ceilings):
        return [_error("budget_invalid", "cost, tokens and duration ceilings must be positive numbers")]
    alert, stop = budget.get("alerte_pct"), budget.get("arret_pct")
    if not (_positive(alert) and _positive(stop) and alert < stop <= 100):
        return [_error("budget_invalid", "need 0 < alerte_pct < arret_pct <= 100")]
    return []


def _checkpoint_problem(item, seen: set) -> str | None:
    if not isinstance(item, dict):
        return "a checkpoint must be a mapping"
    if _blank(item.get("id")) or item["id"] in seen:
        return "checkpoint id missing or duplicated"
    seen.add(item["id"])
    if _blank(item.get("apres")) or _blank(item.get("jay_verifie")):
        return f"checkpoint {item['id']} must say after what and what Jay checks"
    if not isinstance(item.get("bloquant"), bool):
        return f"checkpoint {item['id']} needs bloquant: true|false"
    return None


def check_checkpoints(data: dict) -> list[Violation]:
    items = data.get("checkpoints")
    if items is not None and not isinstance(items, list):
        return [_error("checkpoint_invalid", "checkpoints must be a list of mappings")]
    items = items or []
    seen: set = set()
    problems = [p for p in (_checkpoint_problem(i, seen) for i in items) if p]
    if problems:
        return [_error("checkpoint_invalid", problems[0])]
    blocking = [i for i in items if i["bloquant"]]
    if data.get("mode") == "projet" and not blocking:
        return [_error("checkpoint_blocking_missing", "mode projet needs a blocking checkpoint")]
    return []


def check_deploy(data: dict) -> list[Violation]:
    policy = data.get("deploy")
    if policy not in DEPLOY_POLICIES:
        return [_error("deploy_invalid", f"deploy must be one of {DEPLOY_POLICIES}, got {policy!r}")]
    if policy == "jamais":
        return []
    items = data.get("checkpoints") if isinstance(data.get("checkpoints"), list) else []
    gate = [i for i in items if isinstance(i, dict) and i.get("bloquant") is True
            and i.get("avant_mise_en_ligne") is True]
    if gate:
        return []
    return [_error("deploy_checkpoint_missing",
                   "going live needs a blocking checkpoint flagged avant_mise_en_ligne")]


def _deliverable_problem(item) -> str | None:
    if not isinstance(item, dict) or _blank(item.get("id")) or _blank(item.get("preuve")):
        return "each deliverable needs an id and a proof"
    if item.get("verification") not in VERIFICATIONS:
        return f"verification must be one of {VERIFICATIONS}"
    if item["verification"] == "commande" and _blank(item.get("commande")):
        return f"deliverable {item['id']} is verified by a command: name it"
    return None


def check_deliverable(data: dict) -> list[Violation]:
    items = data.get("livrable")
    if not isinstance(items, list) or not items:
        return [_error("livrable_missing", "a deliverable Jay can verify live is mandatory")]
    problems = [p for p in (_deliverable_problem(i) for i in items) if p]
    return [_error("livrable_invalid", problems[0])] if problems else []


def check_versions(data: dict, ctx: Context) -> list[Violation]:
    found = []
    for key, expected in (("cdc_version", ctx.cdc_version), ("pet_version", ctx.pet_version)):
        if _blank(str(data.get(key) or "")):
            found.append(_error("version_missing", f"{key} is mandatory"))
        elif expected is not None and str(data[key]) != str(expected):
            found.append(_error("contract_void", f"{key} is {data[key]} but the project is at {expected}"))
    return found


def _brick_count(data: dict, ctx: Context) -> int | None:
    if isinstance(data.get("scope"), list):
        return len(data["scope"])
    if ctx.remaining_bricks is not None:
        return ctx.remaining_bricks
    listed = data.get("briques")
    return len(listed) if isinstance(listed, list) and listed else None


def check_estimate(data: dict, ctx: Context) -> list[Violation]:
    count = _brick_count(data, ctx)
    if not ctx.cost_history or not count:
        return [Violation("estimate_unavailable", "warning",
                          "no cost history or brick count: ask Jay to confirm the ceiling")]
    estimate = statistics.median(ctx.cost_history) * count * ESTIMATE_MARGIN
    ceiling = data["budget"]["cout_max_usd"]
    if estimate > ceiling:
        return [_error("estimate_above_ceiling",
                       f"estimate {estimate:.2f} USD exceeds the ceiling {ceiling} USD")]
    return []


def lint(data: dict, **context) -> list[Violation]:
    ctx = Context(**context)
    found = check_mode_and_scope(data) + check_closed_brick_list(data) + check_budget(data) + check_checkpoints(data)
    found += check_deploy(data) + check_deliverable(data) + check_versions(data, ctx)
    estimable = not any(v.code in ("mode_invalid", "scope_mismatch", "budget_missing", "budget_invalid")
                        for v in found)
    return found + (check_estimate(data, ctx) if estimable else [])


class _UniqueKeyLoader(yaml.SafeLoader if yaml else object):
    """SafeLoader that refuses a repeated key: the last one must never win silently."""

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(k, deep=True) for k, _ in node.value]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {sorted(map(str, dup))[0]!r}",
                                                    node.start_mark)
        return super().construct_mapping(node, deep)


def load_frontmatter(text: str) -> dict:
    """Read the YAML header with safe_load only: a contract is data, never code."""
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        raise ContractFormatError("the contract must open with a YAML front matter")
    header = text[4:].split("\n---", 1)[0]
    try:
        data = yaml.load(header, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ContractFormatError(f"unreadable front matter: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractFormatError("the front matter must be a mapping")
    return data


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint an autonomy contract before a run.")
    parser.add_argument("contract")
    parser.add_argument("--cdc-version")
    parser.add_argument("--pet-version")
    parser.add_argument("--history", help="JSON list of per-brick costs in USD")
    parser.add_argument("--remaining", type=int, help="bricks left in the PET (mode projet)")
    return parser.parse_args(argv)


def _valid_history(history) -> bool:
    return isinstance(history, list) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0 for x in history)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if yaml is None:
        print("contract-lint: PyYAML is missing. Install it: pip install pyyaml", file=sys.stderr)
        return 2
    try:
        data = load_frontmatter(Path(args.contract).read_text(encoding="utf-8"))
        history = json.loads(Path(args.history).read_text(encoding="utf-8")) if args.history else []
    except (OSError, ValueError) as exc:
        print(f"contract-lint: {exc}", file=sys.stderr)
        return 2
    if not _valid_history(history):
        print("contract-lint: --history must be a JSON list of positive costs in USD", file=sys.stderr)
        return 2
    found = lint(data, cdc_version=args.cdc_version, pet_version=args.pet_version,
                 cost_history=history, remaining_bricks=args.remaining)
    for v in found:
        print(f"{v.severity.upper():7} {v.code}: {v.message}")
    return 1 if any(v.severity == "error" for v in found) else 0


if __name__ == "__main__":
    sys.exit(main())
