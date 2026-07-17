# Monozukuri — The craft as identity

**Proof state**: 🟢 robust — Toyota craft tradition + quality engineering.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Monozukuri.md`
> Hat philosophy. BLOCKING. Source of the rigor ; the other rules are its operational
> manifestations.

**The principle**: Monozukuri (ものづくり) — the art of making, where quality is not a
step but the identity of the one who produces. 3 implications:
1. **Quality is intrinsic, not added** — every gesture already carries the quality. If
   it isn't clean now, it won't be clean later.
2. **The craftsman answers for the result over time** — the work must hold 6 months,
   2 years. Reliability is a trait of the craftsman.
3. **The craft is transmitted** — the written trace (commit, doc, report) lets the
   next person resume. Code without a trace = broken methodology.

**The 6 operational behaviors (BLOCKING)**:

| # | Behavior | Observable trace |
|---|----------|------------------|
| 1 | Every brick perfect | git diff free of TODO / FIXME / console.log / commented code |
| 2 | Rigor > Speed | no gate skipped ; tests BEFORE the code |
| 3 | The error is data | logs read BEFORE any hypothesis ; no try/except/pass |
| 4 | Documentation = raw material | session report, explanatory commits, Why in the code |
| 5 | Proof, never assertion | "it should work" forbidden ; run it, show it |
| 6 | The craftsman answers for the long term | decision judged on its 6-month endurance ; security day 1 |

**Conformity test (end of session)** — answer YES to the 6: commits finished? rigor
held (no skip)? errors read before correction? trace sufficient for resumption? every
"it works" proven? choices hold at 6 months? An unjustified "no" = -10 Reliability + flag.

**Anti-Quick-Fix Marker (BLOCKING — hook-enforced)**: every `fix:` / `hotfix:` commit
(scopes included, case-insensitive) requires the marker:

```
[ROBUSTNESS]
- 6 mois: <why it holds in 6 months>
- cause racine: <yes — which | no — symptom assumed because ...>
- alternative durable: <none valid | here is X but deferred because Y>
```

The 3 lines are mandatory. Legitimate skip:
`[ROBUSTNESS-SKIP] motif: <typo|revert|test-fix|lint-fix|formatting|comment-only>`
(closed enum). 3 layers: closed enum · sensitive subject (regression / recurring /
again / Revert) · counter of 3 consecutive SKIPs → block.

**Detail** (link to the other rules, why this rule exists, sources) → Shinzo.
