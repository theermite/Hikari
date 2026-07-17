# Quality — BLOCKING Gates

**Proof state**: 🟢 robust — TDG, coverage, quality engineering.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Quality.md`
> Every rule in this file is BLOCKING. Zero derogation.

## TDG — Test-Driven Generation

Tests BEFORE the code, always. (1) write the test → (2) run it (red) → (3) code
(green) → (4) refactor on code smell → (5) tests still green.

## Test Strategy

3 levels: Unit (Vitest / pytest / ExUnit / cargo test, every commit) · Integration
(Playwright / pytest / ExUnit+Ecto.Sandbox, every PR) · E2E + anti-regression
(Playwright, pre-deploy).
Commands: TS `pnpm run test` · Python `pytest` · Elixir `mix test` · Rust `cargo test`.
"All tests pass" = run the real command, exit code 0.
Real DB for integration (no DB mock). Tests named `should_[action]_when_[condition]`.

**Coverage Floors (BLOCKING)**:

| Scope | Min |
|-------|-----|
| Global | 80% |
| Critical paths | 95% |
| New features | 90% (commit blocked otherwise) |
| Lighthouse | 90 |
| axe violations (AA) | 0 |
| Critical/High CVEs | 0 |

**Critical paths** = auth, authentication, authorization, sessions, oauth, jwt,
passwords, 2fa/mfa · payment, billing, subscription, stripe, invoices, refunds,
checkout · DB migrations · security, crypto, encryption · rgpd/gdpr, data
export/delete · payment/auth webhooks. + functions tagged `@critical` +
`docs/critical-paths.md`. NON-critical (floor 80%): UI, content, analytics, dev tools,
scripts, fixtures. Ambiguous → the most restrictive (95%).

**5 reliability metrics (not 1)**: line coverage ≥80% (95% critical) · empty tests = 0
(BLOCKING) · trivial tests <10% · mock:assert ratio <3:1 · type coverage 100% new code
(tsc/mypy strict). Test without assert = empty = BLOCKING.

## Anti-Circular Testing (BLOCKING on critical paths)

Same AI writing code AND tests = circular validation. 3 layers: (1) Algorithmic — PBT +
mutation + fuzzing (always). (2) Different context — separate Writer/Reviewer sessions,
holdout tests (critical paths). (3) Different model — another LLM reviews (recommended).

## 4-Level Risk Classification

Critical (auth/payment/crypto) 95% + MC/DC · Sensitive (user data/RGPD/config/webhooks)
90% · Standard (UI/content/analytics) 80% · Tooling (scripts/fixtures) 60%. Takumi
proposes, Jay decides.

## 5 Human Quality Gates (BLOCKING on public platforms)

Cognitive Load (≤5 decision points / task) · Sensory Comfort (prefers-reduced-motion
100%) · Error Resilience (auto-save forms >3 fields) · Adaptation (preferences persisted
between sessions) · Dignity (0 datum without UX impact + 0 dark pattern + 0 condescending
tone). Detail → Dignity.md.

## Performance (BLOCKING) — Core Web Vitals 2026 Shinkofa

LCP <2.0s · INP <100ms · CLS <0.05. Lazy loading · bundle splitting (no JS >200KB gzip)
· HTTP/3 + Early Hints · `uuidv7()` for PostgreSQL IDs.

## Accessibility (BLOCKING) — WCAG 2.2 AA

0 axe-core violation · contrast ≥4.5:1 (text) · everything interactive keyboard-
accessible · alt on images · visible focus · prefers-reduced-motion respected.
ND-friendly: predictability, low cognitive load (1 action/screen), sensory control,
clear typography (≥16px, 1.5 line-height, ≤75ch), forgiving interactions (undo,
auto-save), zero timer, minimal distractions, customization.

## Maintainability (BLOCKING)

Readability > size. Function ≤30 lines (excl. tests) · cyclomatic complexity ≤10 (hard
block >10 — pre-commit hook AND CI: Radon/Biome/Credo, see `docs/Static-Analysis.md`) · file
WARNING 300 / BLOCKING 500 lines (source code ; exempt: .md, .json i18n, schemas,
configs) · ≤4 parameters per function (else an object).

## Observability (BLOCKING)

**Errors are data**: `try/except/pass` (Python) or empty `catch{}` (TS) = BLOCKING on
critical paths, WARNING elsewhere. Every caught exception logged at the right level
(WARNING critical path, DEBUG expected fallback, INFO user-triggered).
**The Knob Footgun**: an option with only one correct value = a constant, not a knob.
Expose a setting only when several values are legitimate.

## Static Analysis (BLOCKING)

One linter is never enough. Pre-commit (<5s): Ruff (Python), Biome (TS), ShellCheck
(Bash). CI: Pylint, Bandit, Vulture, Radon, mypy, Madge, Knip, Trivy, Semgrep, Gitleaks.
Zero tolerance: Ruff/Biome/tsc errors, Bandit HIGH, circular deps, HIGH/CRITICAL CVEs,
Gitleaks findings, Semgrep HIGH/CRITICAL.

## Test Runtime Hygiene (BLOCKING)

Vitest: `pool: 'forks'`, `maxForks: 2`, `isolate: true`, `maxConcurrency: 5`, timeouts
10s (else VPS OOM). package.json scripts: `NODE_OPTIONS=--max-old-space-size=2048` via
cross-env (Windows). Agentic loop: kill any stale runner of the same project before
relaunching one ; kill at session end. Exact config → Shinzo.

## Lego Library — Build Once, Reuse Forever (BLOCKING)

Before coding ANY UI element: check the `@shinkofa/ui` inventory (79 components). If it
exists → import. If not → code it in `Shinkofa-Shared/packages/ui/` first (tests +
story), then import. All text via `@shinkofa/i18n` (FR/EN/ES, FR source). All shared
types via `@shinkofa/types`. Coding a duplicate = BLOCKING. Full inventory + i18n
workflow → Shinzo.
**A10 — continuous feeding**: as soon as a reusable element is created/spotted, extract
it via `/extract-lego` BEFORE reusing it.

## Morphic Adaptation (BLOCKING on public platforms)

Structural adaptation to the holistic profile (not cosmetic). Layers: sensory
(theme/contrast/motion/font/density), cognitive (info density, progressive disclosure),
temporal (Ki), content (language/tone).
**Design for the Reference Profile First**: default = rich/spatial/dense (Jay's
HPI/multipotentialite/highly-sensitive brain). The morphic engine REDUCES/calms for the
profiles that need it — it does not impose the reduced state on everyone. "Rich by
default, the morphic handles the rest." Guard-rails: ergonomic never decorative ;
spatiality ≠ animation (motion opt-in, prefers-reduced-motion) ; density yes, chaos no.

## Adopted principles (QE V2)

Rebuild over Fix (3+ sessions on the same module → evaluate rebuild) · Let It Crash
(isolate faults, never propagate) · Rigor over Speed · Documentation = pillar · Beyonce
Rule (if you care about a behavior, put a test on it) · Kill Fast = REJECTED · Security =
fundamental quality principle · Feedback Widget = architectural necessity (2 clicks, auto
context, 0 PII) · **Algorithm First** (everything that CAN be deterministic MUST be —
hooks, validation, sorting, formatting ; AI serves where judgment is required ; human
keeps vision + architecture).

## Jidoka without hooks — Portability Bridge (BLOCKING — A9)

When hooks are unavailable (another harness), apply Jidoka (stop on defect) and Poka-yoke
by understanding: emit the falsifiable markers yourself ([VEILLE], [ROBUSTNESS]) and run
the checklists. The AI IS its own Jidoka. An external verifier (human, 2nd model) remains
the only hard guarantee.

## Universal Project Checklist

Every project from day 1: dark/light/high-contrast themes · prefers-reduced-motion ·
mobile-first 375px+ responsive · trilingual FR/EN/ES · reveal password · back-to-top ·
error boundaries · loading skeletons · touch ≥44×44px · Feedback Widget · GlitchTip wired
· morphic (theme+motion+font) · adaptive onboarding (sensory choice BEFORE identity).

**Detail** (Quality Pyramid V2, 79-component inventory, verbatim vitest configs,
exhaustive critical-paths list, i18n examples, Responsive per breakpoint, Three Levels of
Automation, SQuBOK, sources) → Shinzo.
