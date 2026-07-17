---
name: debug
description: Bug investigation. LOGS FIRST. L1 local, L2 SKB+web 8 languages, L3 report to Jay.
model: opus
---

# /debug — Investigate and Fix a Bug

LOGS FIRST. Always. No exceptions. No hypothesizing before reading logs.

## Level 1: Local

1. Read logs / error output.
2. Check recent commits (`git log --oneline -10`).
3. Follow: error message → most likely location. No circular searching.
4. Isolate the cause. Check the module's **risk classification** (Critical/Sensitive/Standard/Tooling) — this determines fix rigor.
5. Fix, write test, verify. **The 8 automatic quality gates apply to the fix** (see `rules/Workflows.md`):
   - Critical path fix: defensive assertions (>= 2), PII detection on outputs, anti-circular Layer 1 (PBT if validation logic)
   - All fixes: test must cover the exact failure mode, zero lint errors, security scan if auth/data touched

## Level 2: Expanded (if L1 fails)

1. Search SKB (Shinkofa Knowledge Base) for known patterns.
2. Web research in 8 languages (EN, FR, ZH, JA, KO, DE, RU, ES).
3. Try fix, verify with tests.

## Level 3: Escalation to Jay (if L2 fails)

1. **STOP.** Do not keep trying.
2. Generate detailed report: what failed, what was tried, what was searched, what sources were consulted.
3. Present options to Jay for brainstorming.
4. Jay decides direction.

## Rules

- Context Reset: After 2 failed corrections on same issue → `/clear` or new conversation.
- Gate 7 applies: every diagnostic verified via external source, not assumption.
- Never present uncertainty as fact. If unsure, say so.

See `mnk/05-Workflows.md` WF-05 for full details.
