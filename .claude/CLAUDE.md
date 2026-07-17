# CLAUDE.md — Hikari (光)

> Le cockpit stream open-source. Une seule app à la place d'OBS + Streamer.bot + deck + Aitum.

<!-- MNK-MANDATORY-FIRST-READ -->
## MANDATORY FIRST READ (BLOCKING — load order critical)

1. `.claude/rules/Interpretation-Protocol.md` — how to read every other rule (literal interpretation layer, required from Opus 4.7 onward)
2. `.claude/rules/Confidentiality.md` — absolute blocking rule on user personal data (overrides every other rule)
3. `.claude/rules/Monozukuri.md` — philosophie chapeau : qualite intrinseque, 6 comportements operationnels, source de la rigueur

No exception. No shortcut.
<!-- /MNK-MANDATORY-FIRST-READ -->

## Project

| Field | Value |
|-------|-------|
| Name | Hikari (光 — lumière) |
| Type | Desktop streaming cockpit, open-source, free |
| Status | **Conception done + audited. No production code yet.** |
| Repo | `theermite/Hikari` — public, **GPL-3.0** (embedded `libobs` forces it) |
| Docs | `docs/` — CDC v1.3.0 · PET v1.4.0 · mockup · `refs-concurrence/` · `legacy-ancien-repo/`. Moved here from `Takumi/` on 2026-07-17 (Jay). ⚠️ `docs/Veille-Technique.md` is **stale** — 3 of its core claims were false, see `docs/README.md`. |
| Project note | `Shinzo/02-Projets/Hikari-Stream.md` — sync at session start and end |

## ⛔ BLOCKING — no production code before B0.0

The engine spike (B0.0, 1 day) comes first. It **measures**, it no longer decides
(PET v1.4.0): a shipped counter-example (`league_record`, Rust + Tauri + OBS engine,
in production since March 2022) proved the stack works. The one open unknown: nobody
has crossed **Rust + OBS engine + live broadcast** — league_record records only.

B0.0 measures the **overhead against bare OBS**, never the machine. One machine is one
point, never a curve; the product must run on anyone's hardware. Hardware floor =
OBS's published floor + our measured overhead (ADR-014).

## Founding decisions (detail → project note + PET)

| Subject | Decision |
|---------|----------|
| Engine in a **separate process** (ADR-013) | Never inside the app. This IS fault isolation made real — the founding reason for Tauri. |
| Engine bridge | `libobs-wrapper` **9.0.4+32.0.2**. Real risk = a single maintainer, not immaturity. |
| **Version source of truth** (ADR-010) | The **registry API** (crates.io, npm) — **never docs.rs**, which froze on 3.0.3 (6 majors stale) and put a false number in a validated CDC. |
| **Automations = data** (ADR-008) | Never executed code. F-023 is Critical (95% coverage). |
| **Trigger = an attribute** (ADR-012) | Button / chat / event / timer = one mechanism. |
| **Engine exposes an interface** (ADR-011) | Local deck and remote deck are two clients. Zero duplicated logic. |
| Fallback | `obs-studio-node` — npm dead since 2020, go through the Streamlabs repo. GPL-2.0 → a fallback forces re-deciding the repo licence. |
| Accounts / model | No Hikari account · free + discreet donation · zero viewer monetization |

## The metric that judges this project

> **"How many ideas did the user abandon because the tool made them too expensive?"
> Target: zero.**

Jay (23 years of design) **gave up** camera effects in Streamer.bot — N sub-actions plus
OBS prep, two tools, multiplied work. Complexity does not cost time: **it destroys creative
intent**. Hikari owns both sides, so what costs an assembly elsewhere becomes one gesture.

Corollary: **F-001 (single install) and F-002 (welcome) are pillars, not comfort.**

## Stack

Tauri 2.x + Rust (frame) · `libobs` embedded, separate process (engine) · React 19 +
Tailwind 4 (interface) · `dockview-react` for the panel cockpit — never a home-made dock
engine (the legacy repo had 6720 lines of never-wired dock).

## Identity

TAKUMI (匠) — Jay's senior technical partner. Full definition: `.claude/rules/Identity.md`
+ `Honesty.md`.
