# Memory — Every memory lands in Shinzo

**Proof state**: 🔵 modern — code-enforcement design, internal.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Memory.md`

**Level**: BLOCKING.

**Rule**: write every new memory as one `.md` file in Shinzo `05-Memoire/`, with
the full Shinzo frontmatter (below). The agent memory dir is redirected there
(`autoMemoryDirectory`); a PostToolUse hook commits + pushes Shinzo on each write.

**Why**: one memory store for all tools, enforced by code, not by AI discipline
(see Shinzo `05-Memoire/feedback-code-enforcement-over-instruction-reliance`).

**Trigger**: any durable fact saved — past decision, user preference, lesson,
reference. Not conversation-only details.

**Schema (required frontmatter)**:

    ---
    name: <short readable title>
    description: <one-line recall hook>
    type: feedback | project | user | reference
    project: <project name, or empty if cross-cutting>
    audience: universal | host:<tool>
    status: approved | draft
    confidence: verified | probable | uncertain
    why: <why this memory exists>
    date: YYYY-MM-DD
    ---

    <the fact, short. Link related memories with [[name]].>

**Index — corrigé 2026-09-05, la règle précédente était fausse.** Elle disait
« l'index est `README.md`, ne créez pas de `MEMORY.md` ». Or `MEMORY.md` est
justement le fichier que le harnais CHARGE à chaque session : l'interdire
revenait à interdire le seul index réellement lu. Mesure du jour : 601 souvenirs,
28 indexés.

**Les deux existent, produits par `scripts/generate-memory-index.py`, jamais
écrits à la main** (un sommaire recopié vieillit et ment — famille de l'inventaire
de composants, 79 annoncés contre 149 réels le même jour) :

| Fichier | Rôle | Contenu |
|---|---|---|
| `README.md` | sommaire complet, pour naviguer | les 601, groupés par type |
| `MEMORY.md` | chargé à chaque session | `user` + `feedback` — ceux qui changent la façon de travailler |

**Proof**: `python scripts/generate-memory-index.py --check` sort en erreur dès
qu'un souvenir manque à un sommaire.

**Rappel au bon moment** : le sommaire rend les souvenirs visibles ; il ne
garantit pas qu'on les lise. `hooks/memory/memory-recall.py` remonte le souvenir
qui parle du sujet avant une commande qui modifie quelque chose. Il ne bloque
jamais, se tait sur les commandes de lecture, et ne répète pas.

**Confidentiality (overrides)**: never write personal data into a memory file
(email, name, handle, phone, address, any re-identifying identifier). See
`Confidentiality.md`.

**Proof**: the file exists in Shinzo `05-Memoire/` AND appears as a Shinzo commit
(hook prints `[memory] committed + pushed: <file>`).

**Without hook**: write the file at the Shinzo path with the schema, then commit
+ push Shinzo by hand.

**Detail** (raw note vs curated fact, 3 portability tiers, Kobo re-sync) → Shinzo.
