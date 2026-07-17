---
name: audit
description: Project audit. Blueprint scoring (>=95%), veille, quality, security, performance, accessibility, visibility, docs, plan.
model: opus
---

# /audit — Audit a Project

Modes: `--audit` (diagnostic only), default (audit + plan), `--fix` (audit + auto-apply simple fixes), `--visibility` (magnetic visibility audit).

## Steps

1. **BLUEPRINT SCORE**: Check items / applicable items from matching Blueprints. Minimum 95%.
2. **3-LAYER ALIGNMENT**: Does this project serve L3 (Shinkofa vision — individuality, adaptation, invisible quality)? Is L2 (presentation/visibility) addressed? Is L1 (next action) clear? Consult SKB MasterPlan for alignment.
3. **VEILLE**: State-of-art freshness (< 14 days). Verify dependency versions via npm/pypi/web. **CRITICAL**: Also verify that quality standards (WCAG, OWASP, CWV criteria), best practices, and architecture patterns referenced in this audit are current — training data is months stale.
4. **QUALITY**: All BLOCKING gates from `rules/Quality.md` verified. Verify current testing framework recommendations via web. Audit Quality Pyramid V2 compliance: are L0-L2 (technical) gates met? For public platforms: are L3-L5 (human) gates addressed? Verify Anti-Circular Testing: on critical paths, is PBT used? Is mutation testing configured? Are there `__holdout__/` tests? Check Risk Classification: are modules classified (Critical/Sensitive/Standard/Tooling)? Is coverage aligned with classification? Check 5 Test Reliability Metrics: empty tests (0), trivial tests (<10%), mock:assert ratio (<3:1), type coverage (100% new code). **Enriched gates check**: verify FMEA exists for Critical modules (Gate 1), bidirectional traceability present (Gate 3), defensive assertions >= 2 per critical function (Gate 4). See `mnk/06-Quality.md`.
5. **SECURITY**: OWASP scan, dependencies, secrets, headers. CSP tested against features. Verify current OWASP Top 10 list via web (it changes). Security IS quality (D6) — verify security is treated as integral to quality, not a separate process. **PII detection** (Gate 7 enrichment): verify automated PII scanning is configured on API responses, logs, and error messages.
6. **PERFORMANCE**: Core Web Vitals targets. Verify current Google thresholds via web (they evolve).
7. **ACCESSIBILITY**: axe-core, WCAG compliance. Verify current WCAG version and criteria via web.
8. **HUMAN QUALITY** (public platforms only): Verify 5 Human Quality Gates: Cognitive Load (≤ 5 decision points per common task), Sensory Comfort (`prefers-reduced-motion` 100%), Error Resilience (auto-save on forms > 3 fields), Adaptation (preference persistence), Dignity (0 dark patterns / condescension / data without visible UX impact — see `rules/Dignity.md`). Verify **Feedback Widget** is present, functional, 2 clicks max (D25 — BLOCKING on public platforms). Reference: `mnk/15-Human-Quality.md`.
9. **VISIBILITY**: SEO meta, structured data, GEO signals (if public-facing).
10. **DOCS CHECK**: Blueprint, CDC, PET match current reality. Verify **deviations** from Universal Project Checklist are documented with justification. **QE V2 retroactive** (per `rules/QE-V2-Retroactive.md`): cross-check artefacts against QE V2 standards — signal gaps for pre-4.0.0 projects.
11. **PLAN**: Generate structured execution plan for fixes with priorities.

## Visibility Audit Mode (`--visibility`)

When invoked with `--visibility`, run an extended visibility-specific audit:

| Check | What to verify |
|-------|---------------|
| **Big 5 Content** | Does the platform answer: pricing/costs, problems/downsides, comparisons, reviews, best-of? (They Ask You Answer method) |
| **SEO Foundation** | Meta tags, sitemap.xml, robots.txt, semantic HTML, internal linking, page speed |
| **GEO (AI Optimization)** | Structured data (Schema.org JSON-LD), E-E-A-T signals, citability formatting, entity clarity |
| **Email Capture** | Lead magnet present? Signup form on key pages? Automated nurture sequence? |
| **UX/Presentation** | Does the presentation sell the product? First impression, hero section, clear value proposition, CTA |
| **Projector Alignment** | Does the platform attract by invitation? No aggressive popups, no dark patterns, quality speaks for itself |
| **Content Freshness** | Last update date? Content < 3 months old? Active blog/articles? |
| **Cross-Platform** | Links to all active platforms? Solo.to linked? Social proof visible? |
| **Auto-Pipeline** | Is content auto-distributed to LinkedIn/Discord/Telegram/Dev.to/etc.? Video pipeline active? |
| **Mobile** | Mobile-first? Touch-friendly? Fast on 3G? |

Output: scored checklist + prioritized action plan for magnetic visibility improvements.

## Finding ID System

Every finding gets a **domain prefix + sequential number** for commit-level traceability:

| Prefix | Domain | Example |
|--------|--------|---------|
| S | Stability (threading, resource leaks, shutdown, error handling) | S1, S2... |
| X | Security (network, crypto, input validation, secrets) | X1, X2... |
| A | Architecture (modularity, God Objects, circular imports, coupling) | A1, A2... |
| T | Tests (coverage gaps, empty tests, mock quality, flaky tests) | T1, T2... |
| L | Low severity (cleanup, best practices, cosmetic) | L1, L2... |
| P | Performance (CWV, bundle size, DB queries, caching) | P1, P2... |
| V | Visibility (SEO, GEO, structured data, content gaps) | V1, V2... |

**Usage**:
- Audit output lists findings as `[S3] Race condition in WebSocket handler`
- Commits reference finding ID: `fix(ws): add connection lock (S3)`
- Remediation plan maps sprints to finding groups
- Searchable in git history: `git log --grep="S3"`

## Remediation Order

Findings are prioritized by **logical dependency + user impact**, not audit weights:

```
1. STABILITY first  — can't fix anything if the app crashes
2. SECURITY second  — can't trust results if data is compromised
3. ARCHITECTURE     — can't maintain code if structure is broken
4. TESTS            — can't verify fixes without reliable tests
5. PERFORMANCE      — optimize only what's stable and secure
6. QUALITY/LOW      — cleanup after foundations are solid
```

**Why this order?**
- Dependency chain: can't write reliable tests if threading is broken
- Risk mitigation: a crash destroys user trust faster than tech debt
- Psychology: fixing CRITICAL bugs builds confidence; fixing lint feels like busywork

## Rules

- Gate 7: Every finding verified via external source.
- Score < 95% → correction plan required. No audit accepted below 95%.
- Consult SKB BEFORE web research for patterns and known issues.
- Visibility audit: verify current SEO/GEO best practices via web before scoring.
- Every finding MUST have a Finding ID. No untracked findings.
- Remediation plan MUST follow the dependency order above. Justify any deviation.

See `mnk/05-Workflows.md` WF-09 for full details.
