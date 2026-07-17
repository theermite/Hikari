# Autonomous-Session — A run that codes alone

**Proof state**: 🟠 partial — real grounding (one run shipped to production 2026-07-16), but a sample of one.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Autonomous-Session.md`
> (decision taxonomy, credential guard-rail, escalation channel, journal format, headless
> mechanics). Origin: conception 2026-07-14 + first production run 2026-07-16.

**Level**: BLOCKING.

**Rule**: An autonomous session proves its ground before starting, hands its output to a
different context for review, and leaves every irreversible act to Jay.

| # | Gate | What it means |
|---|------|---------------|
| 1 | **Pre-flight proves** | Run ONE real project command (`mix test`, `pnpm test` — never `echo`) AND read the PET. Start only when the command exits 0 and the PET names exactly one unambiguous next brick. |
| 2 | **Independent review before merge** | The context that wrote the code never reviews it. A fresh context reads the diff and reports what it found. |
| 3 | **Nothing irreversible** | Work on a branch. Leave `main`, deploys, force-push and every outward write (send, publish, pay) to Jay. |

**Why**:
- **Gate 1** — both failures happened on 2026-07-16. A systemd sandbox killed every Bash
  call (`EROFS`), and an ambiguous PET stalled a run. Each was detectable in 30 seconds,
  before spending the run.
- **Gate 2** — on the first autonomous delivery, an independent review found 2 real
  defects: an unformatted test (the run's own lint gate) and a transcription language
  hardcoded to `"fr"`. A run optimises the brick as written; it cannot judge the need
  behind it. Anti-circular Layer 2, applied (see `Quality.md`).
- **Gate 3** — the run's job is to produce a reviewable branch, never to decide what ships.

**Trigger**: any session asked to run more than one brick without per-brick validation —
a `/autonome` bot run, or a local session told "do phase X of project Y".

**Proof**: an append-only run journal `docs/Sessions/run-<YYYY-MM-DD-HHMM>.md`, one line
per brick — brick · delivered · verification (the real command AND its exit code) · commit
SHA · decision. Header carries the global verdict: bricks done, where it stopped, why.
Plus the reviewer's verdict before any merge. A command output or a SHA, never a
checkbox: "tests OK" proves nothing, "`mix test` → 5424 tests, 0 failures" does.

**Without hook**: emit the journal yourself and quote the pre-flight result verbatim in
the report. Jay stays the last external verifier — the only hard guarantee
(`Quality.md` A9, Jidoka Portability Bridge).

**Stop protocol** (from the conception, unchanged):

| Trigger | Action |
|---------|--------|
| 1st failure (test, lint, types, coverage, review) | **Informed retry**: veille FIRST (real cause, current method), then fix. Never a blind retry — a stale dataset causes many failures, and a veille clears them without disturbing Jay. |
| 2nd blocking failure, same brick | STOP · trace · notify ("context reset recommended") |
| No commit produced · budget exhausted · external dependency absent | Immediate stop, no retry — nothing to diagnose |

**Trust model**: never believe the agent's textual "it works". Truth comes from sources
independent of the agent — re-executed commands (exit codes), git state (does a commit
exist?), coverage numbers, and a different model on Critical modules.

**BLOCKING recap**: pre-flight proven · independent review before merge · nothing
irreversible.
