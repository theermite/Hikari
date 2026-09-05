---
name: dev
description: Feature development with gates. Research, CDC check, non-tech PREPARE, TDG, code, non-tech VALIDATE, Shinzo sync. Updates PET per brick.
model: opus
---

# /dev — Develop a Feature

Execute these steps IN ORDER. No skipping. Atomic commits throughout.

> **Architecture documents** : `docs/CDC.md` = intention (figée), `docs/PET.md` = exécution (vivante, mise à jour à chaque brick). Plus de `Blueprint.md` projet.

## Steps

1. **RESEARCH**: **3-Layer check**: Before coding, verify this feature serves L3 (Shinkofa vision) and L2 (visibility). Consult SKB for domain alignment. Search SKB + web. Verify stack is current. Check CDC + PET alignment. Classify the feature's risk level (Critical/Sensitive/Standard/Tooling) per `mnk/06-Quality.md` Risk Classification — this determines coverage requirements for TDG. **Simplified FMEA** (Gate 1 enrichment): identify 3 most probable failure modes for the feature. **CRITICAL**: Verify ALL technology versions via web (npm/pypi). Training data is months stale. Never assume a version exists or doesn't exist without web confirmation. **Output the [VEILLE] marker** per `rules/Workflows.md` Veille/SKB Evidence Protocol.

   > 🧭 **Expert convoque** : veille + savoir — versions verifiees en source, base consultee avant le web
2. **CDC CHECK + PET BRICK**: Gate 2 — `docs/CDC.md` exists and the feature is in §3 (Features) of CDC, Shinzo project notes consulted (step 3 session-start), SKB searched. **Add a brick entry in `docs/PET.md` §6 (Roadmap)** with an ID (B-XXX), CDC ref (F-XXX), and coverage target (from CDC §7). **Impact analysis** (Gate 2 enrichment): what breaks if this feature goes wrong? What other modules depend on this? — documented in PET §7 (Détail par brick).
3. **NON-TECH PREPARE**: UX, Brand, Accessibility agents review BEFORE code starts. Decisions documented.
4. **TDG**: Write tests FIRST. Tests must fail (red) before writing implementation. Coverage target depends on risk classification: Critical 95% + MC/DC, Sensitive 90%, Standard 80%, Tooling 60%. If feature touches a critical path: apply Anti-Circular Testing Protocol Layer 1 (PBT + mutation testing). **Bidirectional traceability** (Gate 3 enrichment): each requirement has a test, each test traces to a requirement. **Defensive assertions** (Gate 4 enrichment): >= 2 per critical function. See `mnk/06-Quality.md`.

   > 🧭 **Expert convoque** : audit des tests — un test sans assertion donne une fausse confiance
5. **CODE**: Implement. Atomic commits every logical unit. Backup tag every 3-4 commits. Compiler strictness = first poka-yoke: ensure `strict: true` (TS) or `mypy --strict` (Python). Errors at compile time > errors at runtime.
6. **LINT**: Zero lint errors (Biome/Ruff). No exceptions.
7. **SECURITY**: Scan. Verify CSP doesn't block features. Test auth flows. **Automated PII detection** (Gate 7 enrichment): verify outputs do not leak personal data.

   > 🧭 **Expert convoque** : securite — il pense en attaquant, il prouve en auditeur
8. **I18N**: FR/EN/ES translations from start.

   > 🧭 **Expert convoque** : traduction — FR source, EN et ES de premiere classe
9. **VISIBILITY**: SEO meta, structured data, GEO-friendly content (if public-facing).
10. **TESTS**: All tests pass (unit + integration + e2e + anti-regression). Verify **5 test reliability metrics**: empty tests (0), trivial tests (<10%), mock:assert ratio (<3:1), type coverage (100% new code), line coverage per risk level. **MC/DC** for complex conditions on critical paths.

   > 🧭 **Expert convoque** : audit des tests — les 5 metriques de fiabilite, pas seulement le vert
11. **NON-TECH VALIDATE**: UX, Accessibility, Brand review the result. On public-facing features: verify 5 Human Quality Gates (Cognitive Load ≤ 5 decision points, Sensory Comfort = `prefers-reduced-motion` 100%, Error Resilience = auto-save on forms > 3 fields, Adaptation = preference persistence, Dignity = 0 dark patterns / condescension / data without visible UX impact). Verify **Feedback Widget** is present and functional (BLOCKING on public platforms). See `mnk/15-Human-Quality.md`.
12. **DOCS**: Update `docs/PET.md` for this brick — fill §7 sub-section (tests post + preuves + erreurs rencontrées + commit SHA + statut 🟢 Done in §6 Roadmap). Update `docs/CDC.md` ONLY if the intention itself changed (new feature, scope change) — and note it in CDC §Historique de l'intention. Document any **deviations** from Universal Project Checklist with justification (CDC §13 if permanent, PET §13 if execution-only).
13. **SHINZO SYNC**: Update decisions, notes, bugs, next steps in `[SHINZO]/02-Projets/[project].md`. `[SHINZO]` = `D:/30-Dev-Projects/Shinzo` (local) · `~/Shinzo` (VPS). Commit + push Shinzo after writing.

## Convocation par la matiere (BLOCKING)

Avant d ecrire dans un fichier, regarder ce qu il EST. La matiere designe son expert —
aucune commande ne peut le prevoir, seul le fichier touche le sait.

| Ce que tu touches | Expert convoque |
|---|---|
| `.ex` · `.exs` · `mix.exs` | Elixir / Phoenix |
| `.rs` · `Cargo.toml` | Rust |
| `.tsx` · `.jsx` · composants d interface | facade |
| routes et controleurs serveur, schemas d API | serveur |
| migrations, schemas, requetes SQL / Ecto | base de donnees |
| `Dockerfile` · `compose` · `nginx` · config VPS | infrastructure |
| ecrans mobiles, PWA, manifeste | mobile |
| manifestes de dependances et verrous | dependances |
| `.github/workflows/*.yml` | integration continue |
| Stripe, routes de paiement, webhooks de paiement | paiement (chemin Critical) |
| `tauri.conf.json` · Electron · empaquetage bureau | application de bureau |
| OBS · WebRTC · encodage · overlays | diffusion video |
| pipelines RAG · Ollama · embeddings | intelligence artificielle et RAG |

**Convoquer n est pas obligatoire a chaque fichier** — une correction d une ligne dans un
fichier Elixir n appelle pas l expert Elixir. Le declencheur est la DECISION : nouvelle
structure, choix d architecture, code sur un chemin Critical, ou blocage de plus de deux
tentatives. Dans ces cas, ne pas convoquer est un defaut, pas une economie.

**Sans convocation** : ecrire pourquoi dans le rapport, une ligne. « Aucun expert convoque —
correction triviale » est une reponse valable. Le silence, non.
Tableau complet et raison d etre : `docs/Routage-Experts.md`.

## Rules

- Gate 2 + Gate 3 must pass.
- Pre-existing errors: fix them, don't ignore them.
- Commit = commit + push (non-negotiable).
- Quality gates are BLOCKING — zero derogation.
- For critical paths: recommend a dedicated Test Auditor session (Anti-Circular Layer 2). Propose to Jay, do not auto-launch.

See `mnk/05-Workflows.md` WF-04 and `mnk/09-Skills.md` for full details.
