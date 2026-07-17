---
name: session-end
description: End dev session. Full test suite, session report, Shinzo sync, docs update, scoring, save report.
model: opus
---

# /session-end — Close Dev Session

Execute these steps IN ORDER. Gate 8 must pass.

## Steps

0. **PROJECT TYPE DETECTION**: Check for the presence of AT LEAST ONE of these files at the repo root: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, `docker-compose.yml`, `pom.xml`, `build.gradle`. If **NONE** found → activate **LITE_MODE**. LITE_MODE affects steps 1 and 6 (marked below).

1. **TESTS** *(SKIP in LITE_MODE — note "N/A — non-code project" in report)*: Run full test suite. Record pass/fail counts.
2. **REPORT**: Generate session report containing:
   - Work done (features completed, bugs fixed)
   - Tests: passed / failed / new tests written (or "N/A — non-code project" in LITE_MODE)
   - Errors encountered → **root cause (5 whys)** → correction applied
   - Decisions made
   - **Leçon(s)** — the transferable lesson(s) from this session (复盘 grammar: Objectif → Processus → Résultat → Analyse 5-pourquoi → Leçon)
   - Pending items for next session
   - Context Awareness status: was the 60% threshold reached? Was a handoff brief written? Note any context degradation detected.
   - Objective metrics: include unpushed commits, TODO/FIXME added, veille markers — read `.claude/state/last-session-metrics.md` (auto-written by `session-end-metrics.py` hook) or compute via `git log origin/main..HEAD` + `git diff origin/main..HEAD`.
3. **SHINZO SYNC**: Update only the files touched by this session — not all project files:
   - `[SHINZO]/02-Projets/[current-project].md` — always (merge decisions, bugs, next steps)
   - `[SHINZO]/02-Projets/_Cross-Project.md` — only if decisions impact multiple projects
   - `[SHINZO]/02-Projets/Contenu.md` — only if visibility candidates identified (step 8)
   - **`[SHINZO]`** = `D:/30-Dev-Projects/Shinzo` (local) · `~/Shinzo` (VPS).
   - **DO NOT read or write all project files.** Only touch files where you have changes to write.
   - **After writing**: commit + push Shinzo (or the memory hook does it automatically on Write/Edit).
4. **TRIM CHECK**: Verify each updated `[SHINZO]/02-Projets/[project].md` stays under **~5 KB / ~150 lines**. If over, apply the 4 trimming rules (see `mnk/05-Workflows-Session.md` "Obsidian Project File Hygiene") before saving:
   1. Session reports → max 1-liner in project file (`| date | scope | score |`). Full detail stays in `docs/Sessions/`.
   2. Superseded decisions → remove from file. Git history preserves them. Keep only ACTIVE decisions.
   3. Resolved bugs → remove or keep as 1-liner max (`- ~~Bug X~~ done date`).
   4. Out-of-scope sections → move to the correct project file.
5. **DOCS UPDATE**: Ensure CDC and PET reflect current state. Update if changed. (Blueprint is archived to `mnk/10-Blueprints.md` since v5.0.0 — no per-project Blueprint document.)
6. **PENDING**: List remaining items explicitly.
7. **SCORING V2**: Score three dimensions independently, then compute weighted total:
   - **Value (40%)**: Did the session produce something deployable, publishable, or usable?
   - **Reliability (30%)**: How clean was execution? Rework count, regressions, corrections needed.
   - **Process (30%)**: Were methodology gates respected? (Shinzo sync, TDG, atomic commits, reformulation)
   - **Formula**: `Score = (Value × 0.4) + (Reliability × 0.3) + (Process × 0.3)`. Verify with arithmetic: e.g., V=85, R=80, P=90 → (85×0.4)+(80×0.3)+(90×0.3) = 34+24+27 = **85** (not an average).
   - In LITE_MODE, do NOT penalize absence of tests in Process dimension.
   - Human Quality Gates compliance: if public-facing features were built, note whether the 5 gates were verified (Cognitive Load, Sensory Comfort, Error Resilience, Adaptation, Dignity).
8. **VISIBILITY CHECK**: Evaluate if this session produced something shareable. For each candidate, append a ready-to-publish entry to `[SHINZO]/02-Projets/Contenu.md` under the "Idées / candidates" section (one bullet per idea with title + format + status). Options: mini-repo (reusable standalone solution), article (educational, common problem solved), PR/contribution (fix or improvement to an existing open-source project). If nothing qualifies, document "nothing shareable this session" in the report.
9. **SAVE**: Store report in `docs/Sessions/Session-YYYY-MM-DD-NNN.md`.

## Rules

- **Targeted writes, not bulk updates** — only write to project files where this session produced changes. No reading/updating files you didn't touch.
- Gate 8: Shinzo synced (+ committed/pushed), report written, docs updated, visibility check done.
- Session report serves as comparison point for next session.
- Next `/session-start` reads these reports.
- Never end a session with uncommitted work (atomic commit check).
- If a hook, tool, or system rule blocks any of these steps: apply the Post-Block Recovery Protocol (`mnk/11-Post-Block-Recovery.md`). Never stay passive.

See `mnk/05-Workflows-Session.md` WF-10 for full details.
