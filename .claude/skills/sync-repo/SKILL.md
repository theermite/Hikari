---
name: sync-repo
description: Sync project methodology from MNK-GoRin. Fetch, diff, show changes, apply, commit, push.
model: sonnet
---

# /sync-repo — Sync Methodology from MNK-GoRin

Synchronize this project's `.claude/` with the latest MNK-GoRin methodology.

## Steps

1. **FETCH**: Pull latest MNK-GoRin repo (or check local copy).
2. **DIFF**: Compare MNK templates vs this project's `.claude/` files.
3. **SHOW**: Display changes to Jay. Explain what changed and why.
4. **APPLY**: Apply approved updates. Preserve project-specific customizations.
5. **COMMIT**: `chore: sync MNK methodology vX.Y.Z`
6. **PUSH**: Immediate.

## What Syncs

- `.claude/rules/*.md` — always (full update)
- `.claude/skills/` — always (all skills in `.claude/skills/`)
- Ring 0 hooks in `settings.json` — always
- Ring 1 hooks — adapted to project stack
- Shared agent updates — if agent was already in this project

## What Does NOT Sync (preserved)

- `.claude/CLAUDE.md` — project-specific identity
- Project-specific agents — only what's already attributed
- `docs/` — project's own documentation
- Infrastructure details — project-specific ports, domains, Docker

## Rules

- Never overwrite project-specific customizations without showing the diff first.
- If conflict detected, ask Jay which version to keep.

See `mnk/09-Skills.md` for full details.
