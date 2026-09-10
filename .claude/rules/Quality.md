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

**Coverage Floors — et QUI les tient (mesuré 2026-09-05)**

Un seuil que rien n'exécute donne une fausse assurance, ce qui coûte plus cher
qu'une absence de seuil. La colonne de droite dit la vérité mesurée : 68
garde-fous branchés, 21 peuvent refuser une action, et **aucun ne mesure une
couverture de tests**.

| Scope | Min | Tenu par |
|-------|-----|----------|
| Global | 80% | ✋ personne — à vérifier et déclarer à la main |
| Critical paths | 95% | ✋ personne |
| New features | 90% | ✋ personne — « commit bloqué sinon » était faux, retiré |
| Lighthouse | 90 | ✋ personne |
| axe violations (AA) | 0 | ⚠️ `deploy/axe-violations.py` — avertit, ne refuse pas |
| Critical/High CVEs | 0 | ✋ personne |

**✋ = tenu par la discipline.** L'annoncer n'est pas y renoncer : c'est la
condition pour que le chiffre reste vrai. Sur un chemin Critical, le seuil se
vérifie en lançant la commande de couverture et en citant sa sortie dans le
rapport — jamais en cochant. Voir « Jidoka sans hook » plus bas.

**Ce qui EST tenu par du code** (extrait, mesuré le même jour) : fonction ≤ 30
lignes, complexité ≤ 10, fichier 300/500 lignes, test sans assertion, secret en
clair, marqueur de veille, relecture avant mise en ligne, `rm -rf` sur du
travail, contradiction technique après un verdict négatif.

**Poser les vraies portes** (couverture, failles, accessibilité) demande de
l'outillage dans chaque projet et une exécution côté serveur — chantier distinct,
point 4 du plan d'action.

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

## Performance (BLOCKING sur intention, ✋ tenu par la discipline)

**Aucun garde-fou ne mesure ces chiffres** (mesuré 2026-09-05). Ils se prouvent en
lançant la mesure et en citant sa sortie dans le rapport, jamais en les affirmant.

LCP <2.0s · INP <100ms · CLS <0.05. Lazy loading · bundle splitting (no JS >200KB gzip)
· HTTP/3 + Early Hints · `uuidv7()` for PostgreSQL IDs.

## Accessibility (BLOCKING sur intention, ⚠️ averti seulement)

`deploy/axe-violations.py` avertit avant une mise en ligne ; il ne refuse pas.
La preuve reste la sortie de l'outil citée dans le rapport.

0 axe-core violation · contrast ≥4.5:1 (text) · everything interactive keyboard-
accessible · alt on images · visible focus · prefers-reduced-motion respected.
ND-friendly: predictability, low cognitive load (1 action/screen), sensory control,
clear typography (≥16px, 1.5 line-height, ≤75ch), forgiving interactions (undo,
auto-save), zero timer, minimal distractions, customization.

## Maintainability (BLOCKING)

Readability > size. Function ≤30 lines (excl. tests) · cyclomatic complexity ≤10 (hard
block >10 — pre-commit hook AND CI: Radon/Biome/Credo, see `docs/Static-Analysis.md`) · file
WARNING 300 / BLOCKING 500 lines (source code ; exempt: .md, .json i18n, schemas,
configs) · ≤4 parameters per function (else an object — ✋ non tenu par du code).

## Observability (BLOCKING)

**Errors are data**: `try/except/pass` (Python) or empty `catch{}` (TS) = BLOCKING on
critical paths, WARNING elsewhere. Every caught exception logged at the right level
(WARNING critical path, DEBUG expected fallback, INFO user-triggered).
**The Knob Footgun**: an option with only one correct value = a constant, not a knob.
Expose a setting only when several values are legitimate.

## Measuring a thing, never a word about it (BLOCKING — measured 2026-09-07)

**Rule**: when a check selects what it will judge, select on the **structure that carries
the fact** — a named field, a parsed node, a line that OPENS the event — never on a word
being *present* somewhere in the text.

**Why**: text that *talks about* X is indistinguishable from X itself, and documentation is
precisely the text that reproduces the real form most faithfully. Measured in one day, three
times, on three different files: a blocks counter that counted its own comments and the code
it had just read (69 announced against 26 real) · a net that selected sessions on the word
`blockingError` and caught the review report *describing* the defect · a guard that read a
verdict's word without ever asking which code it covered.

**Trigger**: writing or fixing anything that COUNTS, DETECTS or GATES on text — a hook, a
meter, a report, a lint rule.

| Instead of | Select on |
|---|---|
| the word is in the raw line | the parsed field that holds it |
| a marker appears anywhere | the marker OPENS the line, from a closed list of real forms |
| a list of shapes to exclude | the list of shapes to accept — an exclusion list is open, always overtaken by the next form |
| a phrase asserting a state | an artefact that git or the filesystem can settle (a SHA, a path, an exit code) |

**And a closed list is only worth the breadth of what was looked at before closing it.** The
same day, a list closed on ONE measured channel missed a fifth real shape present in 55
session files. Confront the list to the field, and let the test fail on the form you did not
foresee — never on your own recollection of it.

**Proof**: the selection reads a field or an anchored pattern, and a test feeds it the real
text of the thing it must NOT count (documentation, a quoted example, a diff line).

**Without hook**: before shipping a counter or a detector, run it on real data and read the
top of its output line by line. A number without its source lines is a claim.

## Static Analysis (BLOCKING sur intention — ✋ 4 outils sur 21 installes, 0 automatise)

Mesure de l'audit, confirmee le 2026-09-05 : la liste ci-dessous decrit un ideal,
pas un etat. **Ce qui n'est pas installe ne garde rien.** Deux sorties possibles,
a trancher au point 4 du plan : installer, ou retirer de la liste. En attendant,
citer l'outil REELLEMENT lance et sa sortie — jamais la liste.

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

**The library is not visual-only (BLOCKING — Jay 2026-09-09)**: any reusable piece —
UI component, function, validation, confinement, security check, utility — is a Lego
piece. Before writing ANY of them: stand in front of the blank page, name what you are
about to build, and ask the toolbox first — "do I already have this piece?" Only build
what is missing. **Why**: the founding goal was that each new build needs less new code
over time, because more pieces already exist to assemble — an incident on 2026-09-08
showed the opposite happening, two security mechanisms already in production got rebuilt
from zero, both rebuilds shipped with defects the originals did not have.

**For UI**: check the `@shinkofa/ui` inventory. If it exists → import.
If not → code it in `Shinkofa-Shared/packages/ui/` first (tests + story), then import. All
text via `@shinkofa/i18n` (FR/EN/ES, FR source). All shared types via `@shinkofa/types`.
Coding a duplicate = BLOCKING. i18n workflow → Shinzo.

**For everything else (functions, validation, confinement, security, utilities)**: no
generated inventory exists — same limit as the coverage floors above, ✋ tenu par la
discipline. Before writing, search the current repo (and known shared repos:
`Shinkofa-Lego-Elixir`, `Shinkofa-Shared`) for an existing implementation of the same
problem. Coding a duplicate of existing reusable logic = BLOCKING, same as UI. See
Honesty.md "Three questions before writing" — this is now the first of them.

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

**Detail** (Quality Pyramid V2, the generated component inventory, verbatim vitest configs,
exhaustive critical-paths list, i18n examples, Responsive per breakpoint, Three Levels of
Automation, SQuBOK, sources) → Shinzo.
