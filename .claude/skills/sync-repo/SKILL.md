---
name: sync-repo
description: Sync project methodology from MNK-GoRin. Fetch, diff, show changes, apply, commit, push.
model: sonnet
---

# /sync-repo — Sync Methodology from MNK-GoRin

Synchronise `.claude/` for THIS project by running the canonical propagation
script. **Never re-implement the steps by hand.**

**Why (2026-09-06)**: this skill used to describe the propagation in prose. It
was therefore a SECOND implementation of the same operation — and it never
learned the retirement of sleeping agents, which the script had learned. That
is the exact defect that left 6 repos out of 32 carrying 24-26 stale agents.
Jay's decision: one implementation, no second recipe. A route that copies the
gestures will drift from the route that owns them.

**Before the push step**: read `.claude/rules-ondemand/Independent-Review.md` in
full — propagating to other repos is one of its trigger classes. THREE markers,
in order: `[REVIEW-BRIEF]` (four lines, before launching the reviewer), then
`[REVIEW] par <relecteur> le <date> sur <empreinte> — verdict: PASS|FAIL`, where
`<empreinte>` is the commit actually read. Or `[REVIEW-SKIP] motif: <enum>`. The
gate refuses at each step, so the order is not decoration — emitting it wrong
cost three round trips on 2026-09-07. It is not auto-loaded at session start;
this is where it applies.

**If this sync touches a rule file's own text or format** (not just copying it
unchanged): read `.claude/rules-ondemand/Rule-Format.md` first — it is the
standard every rule follows (6 fields, falsifiable proof never a checkbox).

## Steps

1. **LOCATE** — find the Kata repo. It is a sibling of the current project
   (`../Kata`). Absent → STOP and tell Jay; never fall back to copying files
   by hand.
2. **SHOW** — run the script in its default mode (no `--apply`, which writes
   nothing) for THIS project only, and report what it says it would change:

       python ../Kata/scripts/propagate-methodology.py <ProjectName>

   `<ProjectName>` = this repo's directory name, and it is **mandatory here**.
   Without it the script refuses (exit 2) rather than targeting the whole
   workshop — never reach for `--all-projects` to get past that refusal, it
   syncs, commits and pushes every repo. Unknown project → it is not in the
   propagation list: STOP and tell Jay, do not improvise.
3. **APPLY** — after Jay's approval word, the same command with `--apply`. The
   script does the copy, the retirement, the commit and the push itself.
4. **PROVE THE ARRIVAL** — the run's own report is not the proof. Ask the
   receiver:

       python ../Kata/scripts/check-receivers-park.py --check <ProjectName>

   Non-zero exit has TWO possible causes, and they call for different actions —
   read the output, never assume: a retired agent is still tracked here (rerun
   the sync), OR the receiver could not be looked at at all (check the path
   first). Report either one; never hide it behind a green summary.
5. **REPORT** — what changed, in plain language: which rules moved, which
   experts were retired, and the arrival check's result.

## What the script syncs

`.claude/rules/` · `.claude/rules-ondemand/` · `.claude/agents/` ·
`.claude/hooks/` · `.claude/skills/` · the canonical hook wiring in
`settings.json` · the MANDATORY FIRST READ clause of `.claude/CLAUDE.md`.

Sleeping agents (those Kata declares archived) are **removed** here, by name.
An agent this project owns, unknown to Kata, is never touched.

## What is preserved

`.claude/CLAUDE.md` project identity (only the FIRST READ clause is refreshed) ·
non-hook keys of `settings.json` · custom hooks · `docs/` · infrastructure
details (ports, domains, Docker).

## Rules

- **One implementation, always.** If the script cannot do what is needed, fix
  the script in Kata — never do it by hand here. A manual gesture is a route
  nobody will maintain.
- The default mode writes nothing: always show it to Jay before `--apply`.
- Conflict or refusal from the script: read its `recovery` line, apply it,
  retry once, then escalate. Never a silent workaround.

See `mnk/09-Skills.md` for context.
