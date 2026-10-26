---
title: "Annexe — Le socle minimal d'un projet"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Le socle minimal d'un projet

> **Quand la lire** : au début de tout projet ou plateforme : cahier des charges, plan, maquette, échafaudage.
> **Pourquoi** : Une plateforme démarrée sans cette liste oublie le retour en haut de page, les thèmes, l'affichage adaptatif. Chaque ligne de la liste se PRINTE dans le cahier des charges (§ 3bis) avec un état.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Quality.md#12 -->
## 5 Human Quality Gates (BLOCKING on public platforms)

Cognitive Load (≤5 decision points / task) · Sensory Comfort (prefers-reduced-motion
100%) · Error Resilience (auto-save forms >3 fields) · Adaptation (preferences persisted
between sessions) · Dignity (0 datum without UX impact + 0 dark pattern + 0 condescending
tone). Detail → Dignity.md.

<!-- source: Quality.md#37 -->
## Universal Project Checklist

Every project from day 1: dark/light/high-contrast themes · prefers-reduced-motion ·
mobile-first 375px+ responsive · trilingual FR/EN/ES · reveal password · back-to-top ·
error boundaries · loading skeletons · touch ≥44×44px · Feedback Widget · GlitchTip wired
· morphic (theme+motion+font) · adaptive onboarding (sensory choice BEFORE identity).
