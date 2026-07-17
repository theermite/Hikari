# Workflows — Behavioral Rules & Platform Standards

**Proof state**: 🟢 robust — 8 gates + veille = quality engineering.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Workflows.md`

## Automatic Quality Protocol (BLOCKING — all code, not just /dev)

The quality protocol applies automatically to every code write. Jay never has to ask.

**The 8 gates**:

| # | Gate | When |
|---|------|------|
| 1 | Context | Blueprint/CDC if they exist ; else propose a plan. Version veille BEFORE coding (marker mandatory). |
| 2 | Reformulate | Understood / will do / won't touch / files. Wait for validation on non-trivial. |
| 3 | TDG | Tests first (all stacks), red before the code. |
| 4 | Code | Implement. Atomic commits. Backup tag every 3-4 commits. |
| 5 | Lint | Zero error. |
| 6 | Tests | All green (real command). No "it should work". |
| 7 | Security | No secrets, injection, weak patterns. |
| 8 | Verify | Prove it works (passing test, browser on UI, smoke test on deploy). |

## Veille/SKB Evidence Protocol (BLOCKING — hook-enforced)

Before any Write/Edit on source code (`.ts/.tsx/.js/.py/.ex/.exs/.rs/.go`) or a deps
manifest, have emitted a marker:

```
[VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>
[SKB] consulte: <path1>, <path2>
[VEILLE-SKIP] motif: <enum>
```

SKIP enum (closed): `typo` · `internal-refactor-no-new-deps` · `hotfix-known-root-cause`
· `test-only` · `methodology-edit` · `generated-artifact`. Any other motif → BLOCK.
3 layers: A closed enum · B sensitive diff (manifest, new import, version pin) → ONLY
[VEILLE] accepted · C counter of 3 consecutive SKIPs → BLOCK. **The model's dataset is
presumed stale by default**: every version/API/CVE/best-practice is verified as of today,
never from internal knowledge.

## Behavioral Rules

- **Reformulate before coding (BLOCKING)** on non-trivial (>1 file, externally visible,
  irreversible). Trivial: one-line pre-announcement, no wait.
- **Deduce before asking**: git, logs, code first. Ask Jay only for what can't be found.
- **LOGS FIRST** on any bug. Then recent commits → error → location.
- **Verify before claiming**: stale dataset, check SKB + web. Proof, never assertion.
- **Double Regard (two truths)**: cross the **official truth** (docs, specs, versions)
  with the **field truth** (issues, forums, runtime, real usage). Veille covers the
  official side only — the field side is a distinct check, never skipped.
- **User conformity**: a deliverable is done when it matches the **user's expressed
  need**, not only when tests are green. Confront the result to what the user actually
  asked — tech-green ≠ user-right.
- **Consult SKB first** (all domains, before the web).
- **3 Layers filter**: L3 vision → L2 visibility → L1 action.
- **Anti-overengineering**: only what is requested or clearly necessary. Nuance: target =
  the VIABLE minimum over the long term (context+stability+security), not the bare
  minimum. Anticipated solidity on a stability/security axis is NOT overengineering.
- **ZERO rm -rf on work (BLOCKING)**: always `mv x x-backup` or ask Jay. Token
  `# RM-OK: <reason>` unlocks ONE rm authorized by Jay (never on a catastrophic target:
  root, home, project, .git ; logged).
- **Lego Library First (BLOCKING)**: check `@shinkofa/ui` before any UI ; text via i18n ;
  types via `@shinkofa/types`.
- **Sync Shinzo (BLOCKING)**: Read 4 files from `Shinzo/02-Projets/` via `Read` tool
  (_Cross-Project + _Index + current project + [project]-Notes-Jay). No MCP needed.
  Shinzo not cloned → STOP and clone (`git clone git@github.com:theermite/Shinzo.git`).
- **Notes-Jay processing (BLOCKING)**: count unseen items at start ; update the markers
  (👀 Lu / 🔧 En cours / ✅ date — résumé) when handled.
- **Docs: CDC/PET → the project repo (`docs/`) ; knowledge/vision/decisions/archi/infra/
  ecosystem/audits → Shinzo ; session reports → `docs/Sessions/`** (Jay decision 2026-06-27).
- **Atomic commits** · **Fix pre-existing errors** (red tests at start = to fix) · **Write
  session reports** (after each session).

## Plan Mode per brick (BLOCKING when a PET exists)

If a PET has unstarted bricks, implementation goes through native plan mode. The approved
plan = the reformulation + the authorization. One atomic commit per brick (never a giant
commit for N bricks). The plan authorizes scope, never quality (TDG/veille/tests/lint/
security apply).

## Context Engineering

Max 4 concurrent sub-agents (announce "sub-agent N of max 4" ; beyond, queue). Context
reset: after 2 failed corrections on the same symptom → announce "Context reset
recommended" and stop the fixes until Jay decides.

## Post-Compact Continuity (BLOCKING — behavioral)

After auto-compact, do NOT propose /session-end or write a report unless Jay explicitly
asks. Treat the resumption as a continuation, not a wrap-up. If unclear → ask "What's next?".

## Debug Escalation (3 levels)

L1: LOGS FIRST — on a GlitchTip-wired app, check GlitchTip FIRST (centralized prod
errors), then local logs → commits → error. L2: SKB + web (8 languages). L3: STOP,
detailed report, back to Jay.

## Post-Block Recovery (BLOCKING)

After any block (hook, rule, tool refusal): (1) read the full message → (2) exact cause →
(3) adapt → (4) retry once → (5) else escalate (cause + alternative + question). Never
passive, never silently degraded. Violation = -20.

## Jidoka — process-defect gates (discipline-enforced, no hook)

Machine defects (secret, veille, complexity, rm, quick-fix) are held by Ring 0 hooks.
**Process defects have no reliable hook** — they are held by discipline (Jidoka without
hooks: the AI is its own Jidoka). Stop to RESOLVE, not to block:

| Trigger | Action |
|---------|--------|
| A test is red | Stop → fix before moving on. Red tests at session start = to fix. |
| A pre-existing error is SEEN (even off-topic) | Never ignored. Trace + diagnose it, then decide: fix now or note to fix ASAP. |
| 2 failed corrections on the same symptom | Announce "Context reset recommended", stop the fixes until Jay decides. |

Honesty: these depend on discipline (~text-level reliability), not a gate. An external
verifier (Jay, a 2nd model) remains the only hard guarantee (Jidoka Portability Bridge,
`Quality.md` A9).

## Post-Deploy Smoke Test (BLOCKING on live apps)

Within 5 min: auth (protected endpoint without token → 401/403, with → 200) · API
connections (health-check each downstream) · GlitchTip (test error surfaces + zero
post-deploy spike) · critical paths · reverse proxy (no 502/504) · stale storage
regression · session-lifetime regression (cookie Max-Age / refresh TTL) · end-to-end
inter-service connectivity. Anti-pattern: a `/health` returning 200 proves nothing about
downstreams — probe the critical path end-to-end (N/N reachable). Failure → immediate
rollback/hotfix. **Fix = Deploy**: a fix is done only when deployed AND verified.

## Scoring V2

3 dimensions: Value 40% (deliverable/publishable/usable) · Reliability 30% (rework,
regressions) · Process 30% (gates respected). `Score = Value×0.4 + Reliability×0.3 +
Process×0.3`. Report the 3 separately + total.

## Documentation & Tracking (BLOCKING — A8)

Keep docs up to date DURING the work: Shinzo project notes, README, tracking (CDC/PET/reports),
infra/archi state. Stale docs break transmission (Monozukuri #4).

## Agents — Orchestration (A10)

Delegate to the agent whose craft it is ; have them confer on a cross-cutting topic (2+
domains) ; aim for their max expertise. The reply cites which agent(s) contributed. Max 4
concurrent.

**Detail** (developed protocols, PR Upstream Gate, Marketing Automation Gate, Deploy
Layout Convention, Nginx Maintenance Pages, Cross-Browser, Pre-RAG Audit, Code Registry,
Platform Minimums, Non-Tech Agents BEFORE/AFTER, origins/history) → Shinzo.
