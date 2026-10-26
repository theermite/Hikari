---
title: "Annexe — Interface, bibliothèque de pièces et dignité"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Interface, bibliothèque de pièces et dignité

> **Quand la lire** : avant d'écrire ou de modifier une interface, un texte affiché, une traduction.
> **Pourquoi** : Une interface refaite à la main au lieu de la pièce existante, ou un texte qui manipule, coûte plus que la pièce elle-même.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Dignity.md#2 -->
**The principle**: "Respect the intelligence of the one who does not know yet."
Shinkofa treats the user as a person to respect, never as a subject to convert. The
fundamental differentiator — posture, not tech.

<!-- source: Dignity.md#3 -->
**The 3 axioms**:
- **A. The user is never the product** — every datum requested serves THE USER, not
  analytics. If a datum does not change THEIR experience → do not ask for it. State
  what the datum changes for them.
- **B. Ignorance is not stupidity** — explain with precision and depth, never with
  condescension. Dual test: an HPI does not feel taken for a fool AND a novice
  understands without being overwhelmed (both true).
- **C. Consent is informed, not manipulated** — why you ask, what it changes, a real
  choice (no degraded fake choice). Zero dark patterns, FOMO, urgency counters.

<!-- source: Dignity.md#4 -->
**The 7 moments of truth** (where dignity is won/lost): welcome, explanation, error,
limit/paywall, sale, AI conversation, departure, notifications. Detail of each → Shinzo.

<!-- source: Dignity.md#5 -->
**Conformity tests (BLOCKING)** on every interface / copy / CTA / error / notif / flow:

| Test | Threshold |
|------|-----------|
| Intelligence (novice understands AND expert not insulted) | both = yes |
| Transparency (every datum has its user impact visible) | 100% of fields |
| Real choice (refuse/defer without wall or punitive degradation) | every non-blocking field |
| Dark patterns (fake urgency, guilt-trip, FOMO, fake strikethrough price, hard unsubscribe) | 0 occurrence |
| Tone (errors factual and solution-oriented ; notifs with user value) | 100% |
| Sale (tiers presented by what they offer, not what is missing) | yes |
| AI (proposes without prescribing, admits limits, does not push upsell) | yes |
| Departure (deletion in 2 clicks, export offered, zero guilt-trip) | yes |

<!-- source: Quality.md#13 -->
## Performance (BLOCKING sur intention, ✋ tenu par la discipline)

<!-- source: Quality.md#14 -->
**Aucun garde-fou ne mesure ces chiffres** (mesuré 2026-09-05). Ils se prouvent en
lançant la mesure et en citant sa sortie dans le rapport, jamais en les affirmant.

LCP <2.0s · INP <100ms · CLS <0.05. Lazy loading · bundle splitting (no JS >200KB gzip)
· HTTP/3 + Early Hints · `uuidv7()` for PostgreSQL IDs.

<!-- source: Quality.md#15 -->
## Accessibility (BLOCKING sur intention, ⚠️ averti seulement)

`deploy/axe-violations.py` avertit avant une mise en ligne ; il ne refuse pas.
La preuve reste la sortie de l'outil citée dans le rapport.

0 axe-core violation · contrast ≥4.5:1 (text) · everything interactive keyboard-
accessible · alt on images · visible focus · prefers-reduced-motion respected.
ND-friendly: predictability, low cognitive load (1 action/screen), sensory control,
clear typography (≥16px, 1.5 line-height, ≤75ch), forgiving interactions (undo,
auto-save), zero timer, minimal distractions, customization.

<!-- source: Quality.md#28 -->
## Lego Library — Build Once, Reuse Forever (BLOCKING)

<!-- source: Quality.md#30 -->
**For UI**: check the `@shinkofa/ui` inventory. If it exists → import.
If not → code it in `Shinkofa-Shared/packages/ui/` first (tests + story), then import. All
text via `@shinkofa/i18n` (FR/EN/ES, FR source). All shared types via `@shinkofa/types`.
Coding a duplicate = BLOCKING. i18n workflow → Shinzo.

<!-- source: Quality.md#32 -->
**The inventory is generated, never written by hand (BLOCKING — 2026-08-30)**: it lives in
`hooks/lego/ui-inventory.json`, produced by `scripts/generate-ui-inventory.py` from the
library's own exports, and read by the guard. Regenerate it after any `@shinkofa/ui`
release ; `--check` fails when it is stale. **Never state a component count in prose** —
read the file. Why: three numbers disagreed on the same day (this rule said 79, the
package blurb said 83, the code exported 149), so two thirds of the library were invisible
to whoever consulted the rule and the guard could not warn about what it had never heard
of. Measured that day: **146 files across the workspace redefine a component the library
already ships** — ThemeProvider 12 times, Skeleton and Input 8 times each, and three repos
carry 83% of it. An inventory copied by hand ages and lies.
**A10 — continuous feeding**: as soon as a reusable element is created/spotted — visual
or not — extract it (via `/extract-lego` for UI ; to the matching shared repo otherwise)
BEFORE reusing it.

<!-- source: Quality.md#33 -->
**Morphic module — the named second library (BLOCKING, hook-enforced)**: any UI that
offers the user a comfort choice — theme, motion, contrast, density, font size or family,
colorblind mode, reading guide, WAI symbols — is drawn by
`MorphicButton` from `@theermite/morphic-adapter/ui`, **or it is not drawn**.
**Mockups included, with no exception.** A static mockup has no build step, so it loads
the published package from a CDN or links its stylesheet (`@theermite/morphic-adapter/ui.css`);
Android uses `com.theermite.morphic`.
**Why**: on 2026-08-30 an audit found 4 repos drawing a hand-rolled panel. The measured
cost was not the duplication — it was that Jay reported a decorative "Contraste" button as
a module bug, and it got debugged against the wrong artefact. One repo's CDC claimed the
real engine was "réutilisé tel quel" while the code reimplemented nine axes by hand.
**Why the earlier guard missed it**: it detected a duplicate by NAME, and a hand-rolled
panel is never named like the original — that is exactly why it got rebuilt. It also read
`.tsx/.jsx` only, so every HTML mockup escaped. The new guard detects the axis
VOCABULARY and reads markup of every kind.
**Proof**: `hooks/lego/morphic-decoy-check.py` — 3+ distinct axes with no module
reference blocks the write ; 2 axes warns and names the suspect. **A mention is not a
proof of use**: a comment quoting `MorphicButton` does not count, only the exact package
specifier or a rendered element does (a decoy names the real module precisely to look
real — observed on a real artefact the same day).
**Without hook**: before drawing any comfort setting, state which module draws it and
where it is imported from. A panel you cannot trace to the package is a decoy.

<!-- source: Quality.md#34 -->
## Morphic Adaptation (BLOCKING on public platforms)

Structural adaptation to the holistic profile (not cosmetic). Layers: sensory
(theme/contrast/motion/font/density), cognitive (info density, progressive disclosure),
temporal (Ki), content (language/tone).
**Design for the Reference Profile First**: default = rich/spatial/dense (Jay's
HPI/multipotentialite/highly-sensitive brain). The morphic engine REDUCES/calms for the
profiles that need it — it does not impose the reduced state on everyone. "Rich by
default, the morphic handles the rest." Guard-rails: ergonomic never decorative ;
spatiality ≠ animation (motion opt-in, prefers-reduced-motion) ; density yes, chaos no.
