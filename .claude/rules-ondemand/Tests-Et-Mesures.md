---
title: "Annexe — Tests, mesures et analyse statique"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Tests, mesures et analyse statique

> **Quand la lire** : avant d'écrire ou de modifier un test, un seuil, un réglage d'analyse ou un compteur.
> **Pourquoi** : Un compteur qui lit le mot au lieu de la structure rassure à tort ; un seuil que rien n'exécute donne une fausse assurance.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Quality.md#3 -->
## Test Strategy

3 levels: Unit (Vitest / pytest / ExUnit / cargo test, every commit) · Integration
(Playwright / pytest / ExUnit+Ecto.Sandbox, every PR) · E2E + anti-regression
(Playwright, pre-deploy).
Commands: TS `pnpm run test` · Python `pytest` · Elixir `mix test` · Rust `cargo test`.
"All tests pass" = run the real command, exit code 0.
Real DB for integration (no DB mock). Tests named `should_[action]_when_[condition]`.

<!-- source: Quality.md#8 -->
**Critical paths** = auth, authentication, authorization, sessions, oauth, jwt,
passwords, 2fa/mfa · payment, billing, subscription, stripe, invoices, refunds,
checkout · DB migrations · security, crypto, encryption · rgpd/gdpr, data
export/delete · payment/auth webhooks. + functions tagged `@critical` +
`docs/critical-paths.md`. NON-critical (floor 80%): UI, content, analytics, dev tools,
scripts, fixtures. Ambiguous → the most restrictive (95%).

<!-- source: Quality.md#9 -->
**5 reliability metrics (not 1)**: line coverage ≥80% (95% critical) · empty tests = 0
(BLOCKING) · trivial tests <10% · mock:assert ratio <3:1 · type coverage 100% new code
(tsc/mypy strict). Test without assert = empty = BLOCKING.

<!-- source: Quality.md#17 -->
## Observability (BLOCKING)

<!-- source: Quality.md#18 -->
**Errors are data**: `try/except/pass` (Python) or empty `catch{}` (TS) = BLOCKING on
critical paths, WARNING elsewhere. Every caught exception logged at the right level
(WARNING critical path, DEBUG expected fallback, INFO user-triggered).
**The Knob Footgun**: an option with only one correct value = a constant, not a knob.
Expose a setting only when several values are legitimate.

<!-- source: Quality.md#19 -->
## Measuring a thing, never a word about it (BLOCKING — measured 2026-09-07)

<!-- source: Quality.md#20 -->
**Rule**: when a check selects what it will judge, select on the **structure that carries
the fact** — a named field, a parsed node, a line that OPENS the event — never on a word
being *present* somewhere in the text.

<!-- source: Quality.md#21 -->
**Why**: text that *talks about* X is indistinguishable from X itself, and documentation is
precisely the text that reproduces the real form most faithfully. Measured in one day, three
times, on three different files: a blocks counter that counted its own comments and the code
it had just read (69 announced against 26 real) · a net that selected sessions on the word
`blockingError` and caught the review report *describing* the defect · a guard that read a
verdict's word without ever asking which code it covered.

<!-- source: Quality.md#22 -->
**Trigger**: writing or fixing anything that COUNTS, DETECTS or GATES on text — a hook, a
meter, a report, a lint rule.

| Instead of | Select on |
|---|---|
| the word is in the raw line | the parsed field that holds it |
| a marker appears anywhere | the marker OPENS the line, from a closed list of real forms |
| a list of shapes to exclude | the list of shapes to accept — an exclusion list is open, always overtaken by the next form |
| a phrase asserting a state | an artefact that git or the filesystem can settle (a SHA, a path, an exit code) |

<!-- source: Quality.md#23 -->
**And a closed list is only worth the breadth of what was looked at before closing it.** The
same day, a list closed on ONE measured channel missed a fifth real shape present in 55
session files. Confront the list to the field, and let the test fail on the form you did not
foresee — never on your own recollection of it.

<!-- source: Quality.md#24 -->
**Proof**: the selection reads a field or an anchored pattern, and a test feeds it the real
text of the thing it must NOT count (documentation, a quoted example, a diff line).

<!-- source: Quality.md#25 -->
**Without hook**: before shipping a counter or a detector, run it on real data and read the
top of its output line by line. A number without its source lines is a claim.

<!-- source: Quality.md#26 -->
## Static Analysis (BLOCKING sur intention — ✋ 4 outils sur 21 installes, 0 automatise)

Mesure de l'audit, confirmee le 2026-09-05 : la liste ci-dessous decrit un ideal,
pas un etat. **Ce qui n'est pas installe ne garde rien.** Deux sorties possibles,
a trancher au point 4 du plan : installer, ou retirer de la liste. En attendant,
citer l'outil REELLEMENT lance et sa sortie — jamais la liste.

One linter is never enough. Pre-commit (<5s): Ruff (Python), Biome (TS), ShellCheck
(Bash). CI: Pylint, Bandit, Vulture, Radon, mypy, Madge, Knip, Trivy, Semgrep, Gitleaks.
Zero tolerance: Ruff/Biome/tsc errors, Bandit HIGH, circular deps, HIGH/CRITICAL CVEs,
Gitleaks findings, Semgrep HIGH/CRITICAL.

<!-- source: Quality.md#27 -->
## Test Runtime Hygiene (BLOCKING)

Vitest: `pool: 'forks'`, `maxForks: 2`, `isolate: true`, `maxConcurrency: 5`, timeouts
10s (else VPS OOM). package.json scripts: `NODE_OPTIONS=--max-old-space-size=2048` via
cross-env (Windows). Agentic loop: kill any stale runner of the same project before
relaunching one ; kill at session end. Exact config → Shinzo.

<!-- source: Quality.md#35 -->
## Adopted principles (QE V2)

Rebuild over Fix (3+ sessions on the same module → evaluate rebuild) · Let It Crash
(isolate faults, never propagate) · Rigor over Speed · Documentation = pillar · Beyonce
Rule (if you care about a behavior, put a test on it) · Kill Fast = REJECTED · Security =
fundamental quality principle · Feedback Widget = architectural necessity (2 clicks, auto
context, 0 PII) · **Algorithm First** (everything that CAN be deterministic MUST be —
hooks, validation, sorting, formatting ; AI serves where judgment is required ; human
keeps vision + architecture).
