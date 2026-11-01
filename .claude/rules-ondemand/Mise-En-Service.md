---
title: "Annexe — Mise en service : test de fumée complet"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Mise en service : test de fumée complet

> **Quand la lire** : avant et après toute mise en ligne.
> **Pourquoi** : Un contrôle de santé qui répond 200 ne prouve rien sur les dépendances : on sonde le parcours critique de bout en bout.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Workflows.md#25 -->
## Post-Deploy Smoke Test (BLOCKING on live apps)

Within 5 min: auth (protected endpoint without token → 401/403, with → 200) · API
connections (health-check each downstream) · GlitchTip (test error surfaces + zero
post-deploy spike) · critical paths · reverse proxy (no 502/504) · stale storage
regression · session-lifetime regression (cookie Max-Age / refresh TTL) · end-to-end
inter-service connectivity. Anti-pattern: a `/health` returning 200 proves nothing about
downstreams — probe the critical path end-to-end (N/N reachable). Failure → immediate
rollback/hotfix. **Fix = Deploy**: a fix is done only when deployed AND verified.

**Live check before saying « online » (Jay 2026-10-30)**: after a deploy, and before telling Jay a site is
online, run `web_check` (shinkofa-web) on the public URL and one critical path, and quote the output. Without
shinkofa-web loaded: `curl -fsS -o /dev/null -w "%{http_code}"` on the URL and on that path. « Online » means
reachable AND working: a page that answers but errors on its critical path is not online. *Held by discipline
today: `deploy/smoke-test-required.py` only warns once and only sees a `curl`, never an MCP call — a guard
that reads the live check is the next brick.*
*[Amendé 2026-10-30 : contrôle en ligne avant de dire « en ligne » ajouté (décision de Jay).]*
