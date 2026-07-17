# QE-V2-Retroactive — QE V2 = automatic floor

**Proof state**: 🔵 modern — internal quality policy.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/QE-V2-Retroactive.md`

**Level**: BLOCKING — automatic floor, never an option to enable.

**Rule**: Apply QE V2 standards to EVERY artefact — new or existing, pre-4.0.0
included. No grandfather clause. Application is automatic: neither Jay nor Takumi
has to ask for it.

**Why**: a floor you have to ask for is not a floor. Quality is intrinsic
(Monozukuri), not added on demand.

**Triggers**:

| When | Action |
|------|--------|
| Session start (existing project) | Check CDC §7 Risk Classification + §9 Human Quality Gates, PET §6 Roadmap, anti-circular on critical paths, feedback widget. Missing → signal, propose update. **Do NOT auto-fix.** |
| Modifying existing code | In scope: defensive assertions (≥2/critical fn), 5 test metrics, PII detection, type coverage 100% new code. Fix within the same brick. |
| `/audit` | Cross-check QE V2 checklist (25 decisions), report prioritized by risk (Critical first). |

**Default**: signal gaps, propose, never auto-fix at session start. Jay decides
timing and priority.

**Full detail** (check tables column by column, project priority table) → Shinzo.
