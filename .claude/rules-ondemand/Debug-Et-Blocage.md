---
title: "Annexe — Débogage, blocage et arrêt sur défaut"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Débogage, blocage et arrêt sur défaut

> **Quand la lire** : en enquêtant sur un bug, ou après tout refus d'un garde-fou.
> **Pourquoi** : Journaux d'abord ; après un blocage, lire la cause, adapter, réessayer une fois, sinon remonter.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Quality.md#36 -->
## Jidoka without hooks — Portability Bridge (BLOCKING — A9)

When hooks are unavailable (another harness), apply Jidoka (stop on defect) and Poka-yoke
by understanding: emit the falsifiable markers yourself ([VEILLE], [ROBUSTNESS]) and run
the checklists. The AI IS its own Jidoka. An external verifier (human, 2nd model) remains
the only hard guarantee.

<!-- source: Workflows.md#21 -->
## Debug Escalation (3 levels)

L1: LOGS FIRST — on a GlitchTip-wired app, check GlitchTip FIRST (centralized prod
errors), then local logs → commits → error. L2: SKB + web (8 languages). L3: STOP,
detailed report, back to Jay.

<!-- source: Workflows.md#22 -->
## Post-Block Recovery (BLOCKING)

After any block (hook, rule, tool refusal): (1) read the full message → (2) exact cause →
(3) adapt → (4) retry once → (5) else escalate (cause + alternative + question). Never
passive, never silently degraded. Violation = -20.

<!-- source: Workflows.md#23 -->
**A marker the guard did not see (2026-09-28)**: the session journal drops Takumi's text
whenever his thinking is saved in two pieces (391/391 measured, 2026-09-26) — never his tool
calls. When a guard misses a marker he did emit (reformulation, `[VEILLE]`, `[REVIEW-BRIEF]`,
`[ROBUSTNESS]`, `[EN-SUSPENS]`…), write the same text to `<repo>/.claude/state/said-<n>.md`:
every guard reads that channel (`lib/transcript_reader.iter_spoken_text`). A reviewer's own
verdict is read from its hand-back, never from Takumi's retelling.

<!-- source: Workflows.md#24 -->
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
