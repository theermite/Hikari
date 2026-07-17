---
name: deploy
description: Production deployment. Zero-error tolerance. CDC check, veille, security, build, backup, deploy, health, smoke tests, log.
model: opus
---

# /deploy — Deploy to Production

Execute these steps IN ORDER. Zero-error tolerance. Every step must PASS with evidence before proceeding to the next. Fix = Deploy.

## Pre-Flight (BLOCKING — before ANY step)

Before starting, verify:

```bash
# 1. Git is clean (no uncommitted changes)
git status --porcelain
# Must output NOTHING. If output → commit or stash first.

# 2. On correct branch (main or release branch)
git branch --show-current
# Must be main, release/*, or hotfix/*

# 3. All tests pass
# (project-specific: npm test, pytest, etc.)

# 4. Docker daemon is running
docker info > /dev/null 2>&1 && echo "OK" || echo "DOCKER NOT RUNNING"

# 5. Registry drift check (infra-affecting deploys: containers, ports, domains, nginx)
python ~/apps/Shinkofa-Infra/registry/scripts/check-drift.py
# Exit 0 = registry matches VPS. Exit 1 = drift → resolve (update registry/ YAML) BEFORE deploy.
# Skip ONLY for pure code deploys that touch no container/port/domain.
```

If ANY pre-flight fails → STOP. Do not proceed. Fix the issue first.

## Steps

1. **CDC CHECK**: Deployment matches CDC scope. Read `docs/CDC.md` and verify the feature/fix being deployed is within scope.

2. **VEILLE**: Verify no breaking changes in dependencies. **CRITICAL**: Before building, verify dependency versions are real and current via web. A phantom version in package.json = failed build = failed deploy. If deploying RAG-powered features: verify `/pre-rag-audit` result is < 30 days old (check `docs/Pre-RAG-Audit-*.md`). If absent or stale → run `/pre-rag-audit` first.

3. **SECURITY**: Full scan. Verify CSP/headers don't break features. No critical/high CVEs.
   ```bash
   # Python
   pip-audit || echo "FAIL"
   # Node
   npm audit --audit-level=high || echo "FAIL"
   ```

4. **BUILD** (BLOCKING — must succeed with zero errors):
   ```bash
   # Docker build with no cache after any fix
   docker compose build --no-cache <service>
   # Exit code MUST be 0. Any warning about deprecated features → document but proceed.
   # Any error → STOP.
   ```

5. **BACKUP** (BLOCKING — no backup = no deploy):
   ```bash
   # Database backup
   docker exec <pg-container> pg_dump -U postgres --no-owner --no-acl <db> | gzip > ~/backups/<project>-$(date +%Y%m%d-%H%M%S).sql.gz
   # Verify backup
   ls -la ~/backups/<project>-*.sql.gz | tail -1
   # File must exist and be > 0 bytes
   ```

6. **DEPLOY**:
   ```bash
   # Stop old container, start new one
   docker compose up -d <service>
   # Wait for container to be healthy
   docker compose ps <service>
   # Status must show "healthy" or "running"
   # Check logs for startup errors
   docker compose logs --tail=50 <service> | grep -i "error\|fatal\|exception"
   # Must output NOTHING critical
   ```

7. **HEALTH CHECK** (BLOCKING):
   ```bash
   # Verify endpoints respond
   curl -sf http://localhost:<port>/health && echo "OK" || echo "HEALTH FAIL"
   # For each critical endpoint:
   curl -sf -o /dev/null -w "%{http_code}" http://localhost:<port>/api/v1/<endpoint>
   # Must return 200/201/204
   ```

8. **SMOKE TESTS** (BLOCKING):
   - Critical user paths verified (login, core features, payment if applicable)
   - On public platforms: verify Human Quality Gates post-deploy (Cognitive Load, Sensory Comfort, Error Resilience, Adaptation, Dignity)
   - Feedback Widget visible and functional (D25)
   ```bash
   # Check for new errors in last 2 minutes of logs
   docker compose logs --since=2m <service> | grep -ci "error\|exception"
   # Must be 0 or only expected/handled errors
   ```

9. **DEPLOY LOG**: Record deployment in session report and `[SHINZO]/02-Projets/[project].md`. Commit + push Shinzo.

## Rollback Protocol

If ANY post-deploy check fails (steps 7-8):

```bash
# 1. Immediate rollback
docker compose stop <service>
# 2. Restore previous image
docker compose up -d <service>  # (previous image if tagged)
# OR restore from backup:
# gunzip < ~/backups/<project>-<timestamp>.sql.gz | docker exec -i <pg-container> psql -U postgres <db>
# 3. Verify rollback
curl -sf http://localhost:<port>/health && echo "ROLLBACK OK" || echo "ROLLBACK FAILED — ESCALATE"
```

If rollback fails → **ESCALATE TO JAY IMMEDIATELY**.

## Rules

- Gate 5: Tests pass, security clean, Blueprint score >= 95%. Coverage must meet Risk Classification thresholds: Critical 95%, Sensitive 90%, Standard 80%, Tooling 60%.
- Gate 6: Health check passed, monitoring active, smoke tests green.
- Fix = Deploy: "done" means deployed AND verified. Non-negotiable.
- Always backup before deploy. No exceptions.
- **Zero silent failures**: every command must have its output checked. No `|| true`. No swallowed errors.
- **Evidence over assertion**: paste the actual command output as proof. Never say "it should work."

See `mnk/05-Workflows-Commit-Deploy.md` WF-07 for full details.
