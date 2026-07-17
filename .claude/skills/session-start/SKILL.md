---
name: session-start
description: Start a dev session. Environment detect, Shinzo sync, recap, CDC+PET check, pre-existing errors, plan.
model: opus
---

# /session-start — Begin Dev Session

Execute these steps IN ORDER. No skipping (unless LITE_MODE applies — see Step 0).

## Steps

0. **PROJECT TYPE DETECTION**: Check for the presence of AT LEAST ONE of these files at the repo root: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, `docker-compose.yml`, `pom.xml`, `build.gradle`. If **NONE** found → activate **LITE_MODE**. Display: `LITE_MODE: ON (non-code project)` or `LITE_MODE: OFF (code project detected: [filename])`. LITE_MODE skips steps 6, 7, 8, 9 (marked below). All other steps run normally.

1. **ENVIRONMENT**: Detect OS, machine (local/VPS), paths, shell. Display result.
2. **GIT SYNC**: Pull latest changes from remote to ensure local repo is up to date (methodology propagation, other machine commits).
   ```bash
   git pull --ff-only
   ```
   If fast-forward fails (diverged branches) → STOP. Display the divergence and escalate to Jay. Do not force-pull or merge automatically.
3. **SHINZO SYNC (MANDATORY — BLOCKING)**: Read from Shinzo `02-Projets/` (git local, via `Read` tool — no MCP required) — load these 4 files in parallel:
   - `[SHINZO_PATH]/02-Projets/_Cross-Project.md` — cross-project decisions, shared infra, blockers, Lego state
   - `[SHINZO_PATH]/02-Projets/_Index.md` — project inventory and tracks
   - `[SHINZO_PATH]/02-Projets/[current-project].md` — the project file matching the current repo (e.g., `Koshin.md` for Koshin repo)
   - `[SHINZO_PATH]/02-Projets/[current-project]-Notes-Jay.md` — Jay's async feedback channel (bugs, questions, features, observations). Process new items (no marker = unseen). Display count of unseen items.
   - **`[SHINZO_PATH]`** = sibling of workspace: `D:/30-Dev-Projects/Shinzo` (local) · `~/Shinzo` (VPS) · any clone.
   - **DO NOT load all project files.** Only load additional project files if explicitly needed.
   - **If Shinzo is not cloned locally: STOP. Clone it (`git clone git@github.com:theermite/Shinzo.git`) then re-start.**
4. **SKB (Eichi)**: Verify Shinzo `02-Projets/` was read (step 3). SKB = Eichi repo (separate git repo, accessible via filesystem or Obsidian MCP). Load relevant domains on demand.
5. **RECAP**: Read last 3 session reports from `docs/Sessions/` in project repo. Display summary: work done, decisions, pending items, errors. If working on MNK-GoRin and a platform `/concevoir` is on the agenda, also skim `docs/Migration-Brief-v6.md` (10-min synthesis of v6.0.0 state).
6. **CDC + PET CHECK + QE V2 CONFORMITY** *(SKIP in LITE_MODE)*: Verify `docs/CDC.md` (intention) and `docs/PET.md` (exécution) exist. If the project has `docs/critical-paths.md`, load it — risk classification affects all quality gates during the session. **QE V2 check** (per `rules/QE-V2-Retroactive.md`): verify CDC contains §7 Risk Classification (module → level table), §8 FMEA on Critical modules, and §9 Human Quality Gates checklist on public-facing projects (cognitive load, sensory comfort, error resilience, adaptation, dignity + Feedback Widget). Verify PET §6 Roadmap is populated. Flag any drift from implementation. If missing → signal to Jay, propose update. Do NOT auto-fix. *Note: `Blueprint.md` is no longer a project document — archetypes are reference-only in `mnk/10-Blueprints.md`.*
7. **PRE-EXISTING ERRORS** *(SKIP in LITE_MODE)*: Run test suite. If ANY test fails, flag as priority.
8. **VEILLE CHECK** *(SKIP in LITE_MODE)*: Verify stack versions via npm/pypi/web. Training data is ALWAYS months stale. One wrong version = cascading failures in code, tests, deploys.
9. **LEGO AUDIT** *(SKIP in LITE_MODE)*: If the project uses UI components, cross-reference project imports against `@shinkofa/ui` inventory in `rules/Quality.md` → "Shinkofa Lego Library" section. Flag any locally-defined components that should be imported from the library, and note any new library components available since last session.
10. **PLAN**: Present today's plan based on pending items + Jay's request. Wait for validation.
11. **PLAN MODE PAR BRIQUE** *(SKIP in LITE_MODE, or when no PET exists, or no unstarted brick)*: Once Jay validates the day's direction AND a PET exists with at least one unstarted brick, enter plan mode (EnterPlanMode) to plan the next brick(s) from PET §6 Roadmap. Present which bricks, files, tests, and order — related bricks may be planned together. Jay's approval of the plan (ExitPlanMode) IS the reformulation + approval for the implementation that follows; one atomic commit per brick. See `rules/Workflows.md` → "Plan Mode par brique".

## Rules

- **Context Awareness Protocol is active from session start.** Track exchange count and file reads. Alert at ~40 exchanges or ~15 file reads (~60% context). STOP at ~60 exchanges or compaction triggered (~80%). See `rules/Workflows.md`.
- **Shinzo sync is BLOCKING and non-negotiable** (step 3). A session without it is a process violation. If Shinzo is not cloned, escalate — never skip.
- **4 files, not 21** — load `_Cross-Project.md` + `_Index.md` + current project file + `Notes-Jay.md`. Additional files on demand only.
- **Notes-Jay processing** — at session start, identify unseen items (no status marker). At session end or when items are treated, update the Notes-Jay file in Shinzo with markers: `👀 Lu [date]` (seen), `🔧 En cours` (in progress), `✅ [date] — résumé` (done).
- Pre-existing test failures MUST be addressed (code projects only — N/A in LITE_MODE).
- If CDC or PET is missing on a code project, suggest running `/concevoir` first.
- Gate 0 must pass before ANY work begins.
- **5S (WARN, BLOCKING 2026-06-19)**: the 5 piliers Seiri/Seiton/Seiso/Seiketsu/Shitsuke (`rules/5S.md`) apply implicitly across the session — atelier propre means tests verts, lint zero, no orphan TODO at session end. No dedicated step; it manifests through the existing gates.
- If a hook, tool, or system rule blocks any of these steps: apply the Post-Block Recovery Protocol (`mnk/11-Post-Block-Recovery.md`). Never stay passive.

See `mnk/05-Workflows-Session.md` WF-01 for full details.
