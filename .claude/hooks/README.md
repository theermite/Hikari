# Hooks — Code-Enforced Methodology

> Ring **Chi (地)** of the GORIN Stack — automatic triggers that enforce the methodology at tool-call boundaries.
> Exit codes: `0` = pass (silent), `1` = warn (stderr surfaced, non-blocking), `2` = block (refuses the tool call).
> Wired in `.claude/settings.json` under `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, `SessionEnd`.

## Layout

```
.claude/hooks/
├── deploy/        # Deploy-time gates (smoke, a11y, axe, Safari, maintenance pages)
├── guards/        # Hard guards on Write/Edit/Bash (file size, secrets, deploy preconditions)
├── lego/          # Shinkofa Lego Library compliance (UI inventory, i18n, shared types)
├── lifecycle/     # SessionStart/SessionEnd/PreCompact lifecycle
├── memory/        # Memory-system policing
├── quality/       # Quality protocol gates (TDG, reformulate, logs-first, UTF-8, simple-language, veille)
├── time-tracker/  # Time-estimation telemetry (capture + comparator + session stats)
├── lib/           # Shared helpers (`common.py`, `session_state.py`)
└── tests/         # pytest suite — run from this dir: `python -m pytest tests/`
```

## Phase D — Code-enforced methodology hooks (added 2026-05-29)

Five new hooks promoting the highest-impact methodology rules from documentation to executable guards.

### D1 — `guards/post-commit-push-check.py` (PostToolUse Bash, WARN)

**Trigger** — any Bash command ending with a successful `git commit`.
**Action** — checks if the current branch is ahead of upstream; if yes and the next command is not `git push`, emit WARN on stderr.
**Why** — "Fix = Deploy" rule (`rules/Workflows.md`). A commit that sits unpushed for hours defeats the rule.
**Recovery** — `git push` (or `git push -u origin <branch>` on a new branch).
**Tests** — `tests/test_d1_post_commit_push.py` (8 cases).

### D2 — `guards/pre-deploy-vault-check.py` (PreToolUse Bash, BLOCK)

**Trigger** — Bash command matching a deploy verb (`docker compose up`, `systemctl restart`, `deploy.sh`, `vercel --prod`, `fly deploy`, `kubectl apply`, `helm upgrade`, `ssh ... docker|systemctl`, etc.).
**Action** — parses `docs/architecture/env-vars.md` (formats: `VAR -> kv/path` or markdown table `| VAR | kv/path |`); for each entry runs `vault kv get <path>`; BLOCKs the deploy if any required secret is missing.
**Why** — every prod deploy with a missing env var = guaranteed runtime crash. Vault is our source of truth, the manifest is `env-vars.md`.
**Pass-through cases** — no `env-vars.md`, no `vault` CLI on PATH, no parseable entries.
**Recovery** — `vault kv put <path> <var>=<value>` then re-run deploy.
**Tests** — `tests/test_d2_vault_check.py` (8 cases).

### D3 — `guards/pre-deploy-registry-check.py` (PreToolUse Bash, BLOCK)

**Trigger** — same deploy regex set as D2.
**Action** — if `docs/registry/` exists, run `git status --porcelain docs/registry/`. Any modified/added/untracked entry = BLOCK.
**Why** — `/update-registry` regenerates the inventory of public classes/functions; deploying with a stale registry ships docs that lie. Hooks cannot invoke Claude skills directly, so we use `git status` as the observable proxy ("regenerated and not committed" ≡ "dirty").
**Pass-through cases** — no `docs/registry/` directory (project not opted in), registry clean.
**Recovery** — `/update-registry`, review diff, `git add docs/registry && git commit -m "chore(registry): sync"`, re-run deploy.
**Tests** — `tests/test_d3_registry_check.py` (6 cases, real git init in tmp).

### D4 — `guards/pre-session-end-readme-check.py` (UserPromptSubmit, WARN)

**Trigger** — UserPromptSubmit when the prompt matches `/session-end`.
**Action** — reads the time-tracker session state (`time-session-<sid>.json`) for `started_at`, computes the session-start SHA via `git log --since=<started_at>`, then diffs files + commit messages from that SHA to HEAD. Emits WARN if any of:

1. A new file under `.claude/commands/` or any `**/commands/<name>.{md,py,ex,exs,ts,js,sh}` (a new public command shipped).
2. A manifest changed (`package.json`, `pnpm-lock.yaml`, `pyproject.toml`, `mix.exs`, `Cargo.toml`, `requirements*.txt`, etc.) OR a `.env*`, `docker-compose*.yml`, `Dockerfile`.
3. A commit subject matches `^[a-z]+(\([^)]*\))?!:` (Conventional `feat!:`) OR body contains `BREAKING CHANGE:`.

…AND `README.md` was NOT among the changed files.

**Why** — most "README drift" incidents come from session-end pushes that ship a new feature without updating the entry point. WARN at `/session-end` is the cheapest reminder.
**Pass-through cases** — prompt is not `/session-end`, no session state, no changes since session start, README also touched.
**Recovery** — update `README.md` (new command line, manifest version bump, breaking-change note) and re-run `/session-end`.
**Tests** — `tests/test_d4_readme_check.py` (11 cases, git stub PATH override).

### D5 — `guards/write-guard.py` (PreToolUse Write|Edit, BLOCK)  *(extended)*

**Trigger** — every Write or Edit.
**New checks added in Phase D** (on top of existing file-size / encoding / secret patterns):
- Hardcoded user PII detection (emails, phone numbers, postal addresses) in source files (`.ts`, `.tsx`, `.py`, `.ex`, `.exs`, `.rs`, `.go`, `.json`, `.yaml`, `.md`).
- Falsy-default checks (e.g. `password = ""`, `token = "TODO"` in non-test code).
**Why** — `rules/Confidentiality.md` is BLOCKING; relying on human review is unsafe. Hook-enforced PII detection at write time stops the leak before commit.
**Recovery** — replace the literal with a placeholder constant + env-var reference, OR move to a fixture file under `tests/`.
**Tests** — `tests/test_d5_extended_secrets.py` (13 cases).

## Test suite

Run from `.claude/hooks/`:

```bash
python -m pytest tests/                  # all 46+ tests
python -m pytest tests/test_d4_readme_check.py -v
```

All hooks use:
- `lib/common.py` — `read_hook_input()`, `block()`, `pass_through()`, `format_block()`, `find_repo_root()`, `get_command()`.
- `lib/session_state.py` — session-id derivation and JSON state file helpers.

## Wiring

See `.claude/settings.json`. Hook entries are tolerant: each command does `if [ -f "$HOOK" ]; then python3 "$HOOK"; else exit 0; fi`, so a missing hook never breaks the tool call.

## Reference

- Brief: `Plan-Implementation-Phases-A-F` (Obsidian, Kobo project).
- Methodology rules enforced: `rules/Workflows.md` (Fix = Deploy, Post-Deploy Smoke Test, Marketing Automation Gate), `rules/Quality.md` (TDG, Test Reliability Metrics), `rules/Confidentiality.md`, `rules/Monozukuri.md`.
- Skill counterparts: `/update-registry`, `/session-end`, `/sync-repo`.
