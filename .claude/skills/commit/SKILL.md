---
name: commit
description: Pre-commit review + CDC alignment + atomic check + stage + commit + push.
model: opus
---

# /commit — Commit Changes

Execute these steps IN ORDER. Gate 4 must pass.

## Steps

1. **NOTES CHECK**: Verify Shinzo `02-Projets/[project].md` is synced with current decisions.
2. **QUALITY**: Run Code-Quality-Master agent review.
   - Apply 4-level Risk Classification: Critical (95%), Sensitive (90%), Standard (80%), Tooling (60%) — verify coverage meets the threshold for the module being committed.
   - Empty tests (zero assertions) = BLOCKING. Do not commit test files with empty test bodies.
   - If committing tests for critical paths: verify Anti-Circular Layer 1 applied (PBT or mutation testing, not just unit tests written by the same session).
3. **CDC ALIGN**: Verify changes match the CDC scope.
4. **ATOMIC CHECK**: Is this a single logical change? If not, split into multiple commits.
5. **STAGE**: Stage specific files (`git add file1 file2`). Never `git add .` blindly.
6. **COMMIT**: Conventional commit message with Co-Authored-By.
7. **PUSH**: Immediate. Commit = commit + push. Non-negotiable.

## Rules

- Gate 4: Quality check passed, lint zero, no secrets, atomic change.
- No secrets in staged files (hook-enforced).
- No console.log in production code (hook warns).
- Backup tag every 3-4 commits.

See `mnk/05-Workflows.md` WF-06 for full details.
