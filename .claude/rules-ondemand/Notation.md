---
title: "Annexe — Notation de séance et reproches de livraison"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Notation de séance et reproches de livraison

> **Quand la lire** : en écrivant le rapport de séance.
> **Pourquoi** : Un reproche de Jay sur la livraison est un défaut de séance, compté et cité, jamais un simple avis.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Workflows.md#26 -->
## Scoring V2

3 dimensions: Value 40% (deliverable/publishable/usable) · Reliability 30% (rework,
regressions) · Process 30% (gates respected). `Score = Value×0.4 + Reliability×0.3 +
Process×0.3`. Report the 3 separately + total.

<!-- source: Workflows.md#27 -->
**A delivery complaint counts as a defect (BLOCKING — measured 2026-09-06)**: when Jay says
the output is unreadable, too dense, too technical, or that there is too much of it, that is
a session defect — **−10 Value per occurrence**, listed in the report under
« Reproches de livraison » with his words verbatim.

<!-- source: Workflows.md#28 -->
**Why**: 5 complaints in 20 sessions, 3 of them AFTER the fix meant to close them. The
signal existed, was documented every time, and entered no score — so nothing changed. A
deliverable is done when it matches the user's expressed need; Jay is the user of every
report, reformulation and recap we write. Tech-green is not user-right.

<!-- source: Workflows.md#29 -->
**Proof**: the report's « Reproches de livraison » section — his sentence, the cause found,
and what was changed. Zero complaints = write « aucun ». An absent section is itself a miss.
