---
name: rebuild-decision
description: Evaluate Rebuild vs Fix for a struggling module. Metrics, criteria, cost comparison, documented decision.
model: opus
---

# /rebuild-decision — Rebuild vs Fix Evaluation

Formalized decision framework for when a module has accumulated too many correction sessions without lasting resolution.

## Step 1: Collect Metrics

1. Current audit score (run `/audit` if not recent)
2. **Risk Classification** of the module (Critical/Sensitive/Standard/Tooling per `rules/Quality.md`) — this determines coverage thresholds and fix rigor
3. Number of correction sessions on this module (check `docs/Sessions/`)
4. Age of codebase and last major refactor
5. Current test coverage (overall + critical paths, against Risk Classification thresholds)
6. Technical debt estimate (circular deps, lint warnings, complexity)

## Step 2: Apply Trigger Criteria

A rebuild evaluation is triggered when ANY of:
- 3+ sessions fixing the same module without lasting resolution
- Audit score < 60
- Coverage < 50% on critical paths
- CVEs not resolvable by dependency update
- Exponential technical debt (each fix introduces new fragility)
- Module architecture contradicts current conventions

## Step 3: Evaluate Rebuild Cost

1. How much does the Lego Library (`@shinkofa/ui`, `@shinkofa/types`, `@shinkofa/i18n`) already cover?
2. Features to re-implement from scratch
3. Data migrations required
4. Integration points with other modules
5. Estimated sessions for clean rebuild

## Step 4: Evaluate Fix Cost

1. Number of remaining blockers
2. Estimated sessions for incremental fixes
3. Cost of bringing module to QE V2 conformity (enriched gates, test reliability metrics, risk-appropriate coverage)
4. Regression risk per fix
5. Probability of lasting resolution

## Step 5: Compare and Recommend

Present side-by-side:

| Factor | Rebuild | Fix |
|--------|---------|-----|
| Estimated sessions | | |
| Lego Library coverage | | |
| Regression risk | | |
| Long-term maintainability | | |
| Data migration complexity | | |

Recommend one option with reasoning. Reference historical evidence: Kakusei (4 days rebuild), Michi V1→V2 (<1 week, 4x features), Hibiki (1 week audit, bugs persisted).

## Step 6: Document Decision

Write decision in `docs/PET.md` §12 (Décisions architecturales — ADR-light) as a new ADR entry:
- ADR-XXX title
- Date and rationale
- Metrics at time of decision (from Step 1)
- Options envisagées (Rebuild / Fix)
- Décision retenue
- Conséquences (timeline, risques, review checkpoint)

If the rebuild changes the project's **intention** itself (scope, stack, public, features) → also update `docs/CDC.md` and log the change in CDC §Historique de l'intention. A pure technical rewrite at iso-scope stays PET-only.

## Output

- Decision: **REBUILD** or **FIX** with documented rationale
- Action plan (next steps)
- New ADR entry in `docs/PET.md` §12 (and CDC update if intention changed)

## Rules

- This skill proposes — Jay decides. Never auto-execute a rebuild.
- The goal is to build correctly NOW so rebuild is never needed again.
- Kill fast = REJECTED. Never kill the WHY. Adapt the HOW.
- See `rules/Quality.md` "Rebuild Over Fix" for full criteria.
