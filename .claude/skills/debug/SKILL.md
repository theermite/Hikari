---
name: debug
description: Bug investigation. LOGS FIRST. L1 local, L2 SKB+web 8 languages, L3 report to Jay.
model: opus
---

# /debug — Investigate and Fix a Bug

LOGS FIRST. Always. No exceptions. No hypothesizing before reading logs.

## Level 1: Local

> 🧭 **Expert convoque** : investigation de bug — LOGS D ABORD, aucune hypothese avant la preuve.


1. Read logs / error output.
2. Check recent commits (`git log --oneline -10`).
3. Follow: error message → most likely location. No circular searching.
4. Isolate the cause. Check the module's **risk classification** (Critical/Sensitive/Standard/Tooling) — this determines fix rigor.
5. Fix, write test, verify. **The 8 automatic quality gates apply to the fix** (see `rules/Workflows.md`):
   - Critical path fix: defensive assertions (>= 2), PII detection on outputs, anti-circular Layer 1 (PBT if validation logic)
   - All fixes: test must cover the exact failure mode, zero lint errors, security scan if auth/data touched

## Level 2: Expanded (if L1 fails)

> 🧭 **Expert convoque** : investigation de bug (suite) + savoir (SKB) avant le web.


1. Search SKB (Shinkofa Knowledge Base) for known patterns.
2. Web research in 8 languages (EN, FR, ZH, JA, KO, DE, RU, ES).
3. Try fix, verify with tests.

## Level 3: Escalation to Jay (if L2 fails)

1. **STOP.** Do not keep trying.
2. Generate detailed report: what failed, what was tried, what was searched, what sources were consulted.
3. Present options to Jay for brainstorming.
4. Jay decides direction.

## Convocation par la matiere (BLOCKING)

Avant d ecrire dans un fichier, regarder ce qu il EST. La matiere designe son expert —
aucune commande ne peut le prevoir, seul le fichier touche le sait.

| Ce que tu touches | Expert convoque |
|---|---|
| `.ex` · `.exs` · `mix.exs` | Elixir / Phoenix |
| `.rs` · `Cargo.toml` | Rust |
| `.tsx` · `.jsx` · composants d interface | facade |
| routes et controleurs serveur, schemas d API | serveur |
| migrations, schemas, requetes SQL / Ecto | base de donnees |
| `Dockerfile` · `compose` · `nginx` · config VPS | infrastructure |
| ecrans mobiles, PWA, manifeste | mobile |
| manifestes de dependances et verrous | dependances |
| `.github/workflows/*.yml` | integration continue |
| Stripe, routes de paiement, webhooks de paiement | paiement (chemin Critical) |
| `tauri.conf.json` · Electron · empaquetage bureau | application de bureau |
| OBS · WebRTC · encodage · overlays | diffusion video |
| pipelines RAG · Ollama · embeddings | intelligence artificielle et RAG |

**Convoquer n est pas obligatoire a chaque fichier** — une correction d une ligne dans un
fichier Elixir n appelle pas l expert Elixir. Le declencheur est la DECISION : nouvelle
structure, choix d architecture, code sur un chemin Critical, ou blocage de plus de deux
tentatives. Dans ces cas, ne pas convoquer est un defaut, pas une economie.

**Sans convocation** : ecrire pourquoi dans le rapport, une ligne. « Aucun expert convoque —
correction triviale » est une reponse valable. Le silence, non.
Tableau complet et raison d etre : `docs/Routage-Experts.md`.

## Rules

- Context Reset: After 2 failed corrections on same issue → `/clear` or new conversation.
- Gate 7 applies: every diagnostic verified via external source, not assumption.
- Never present uncertainty as fact. If unsure, say so.

See `mnk/05-Workflows.md` WF-05 for full details.
