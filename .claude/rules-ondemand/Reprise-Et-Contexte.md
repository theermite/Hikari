---
title: "Annexe — Contexte, reprise et fils ouverts"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Contexte, reprise et fils ouverts

> **Quand la lire** : en écrivant le rapport de séance, à la compaction, ou quand la jauge de contexte parle.
> **Pourquoi** : Ce qui n'a pas été écrit comme fil ouvert n'est pas sauvé : la reprise ne retrouve que ce qui est marqué.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Workflows.md#9 -->
## Context Engineering

Max 4 concurrent sub-agents (announce "sub-agent N of max 4" ; beyond, queue). Context
reset: after 2 failed corrections on the same symptom → announce "Context reset
recommended" and stop the fixes until Jay decides.

<!-- source: Workflows.md#10 -->
**Context size is READ, never estimated (BLOCKING — Jay 2026-09-06)**: the gauge
(`hooks/lifecycle/context-gauge.py`) reads the real occupied tokens each turn and speaks
once per threshold — **600 000** enters the zone where quality can degrade, **700 000**
advises the warm resume (write the `[EN-SUSPENS]` threads, `/clear`, continue on the
brief). Never block: it is a gauge, not a gate.

<!-- source: Workflows.md#11 -->
**Why the old proxy went**: « ~40 exchanges or ~15 file reads (~60 %) » measures nothing —
an exchange costs 200 tokens or 40 000, a read 3 lines or 3 000 — and it was calibrated on
a 200 000 window while sessions run on 1 000 000. Measured that day: it ordered a stop at
**479 000 of 1 000 000**. A gate that fires wrongly gets unplugged, and takes the real
detection with it.

<!-- source: Workflows.md#12 -->
**A warm resume beats closing and reopening**: session-end runs the suite, the report, the
sync and the scoring ; session-start re-reads four project files and three reports. The
resume costs a generated brief and a few targeted reads.

<!-- source: Workflows.md#13 -->
## What must survive a resume (BLOCKING — Jay 2026-09-06)

<!-- source: Workflows.md#14 -->
**Rule**: the moment a thread is left OPEN, write it as `[EN-SUSPENS] <the thread, one
line>`. When it is settled, write `[RESOLU] <the same line>`. The handoff brief collects
both from the session and lists the survivors FIRST.

<!-- source: Workflows.md#15 -->
**What counts as open**: an objection raised and not yet answered · a hypothesis stated
without measuring it · a lead worth following, parked for later · a decision waiting on
Jay · a defect seen off-topic and not yet traced.

<!-- source: Workflows.md#16 -->
**Why**: a warm resume (write the brief, `/clear`, continue) costs far less than closing
and reopening a session. What it loses is what nobody wrote down — the thread of a hunch,
an objection left hanging. Jay's instruction: put it IN the brief instead of accepting the
loss.

<!-- source: Workflows.md#17 -->
**The brief is generated, never written from memory** — a summary typed from recollection
ages and lies (three contradictory figures for one inventory, same day, 2026-08-30). So
the marker is the only thing that carries: what is not marked is not saved.

<!-- source: Workflows.md#18 -->
**Proof**: `.claude/state/handoff-<session>.md` opens on « Fils ouverts / objections en
suspens », listing them or saying « aucun ». `hooks/lib/brief_builder.py`, 8 tests.

<!-- source: Workflows.md#19 -->
**Without hook**: end the session's last message with the open threads, verbatim.

<!-- source: Workflows.md#20 -->
## Post-Compact Continuity (BLOCKING — behavioral)

After auto-compact, do NOT propose /session-end or write a report unless Jay explicitly
asks. Treat the resumption as a continuation, not a wrap-up. If unclear → ask "What's next?".
