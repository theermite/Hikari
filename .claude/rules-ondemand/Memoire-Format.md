---
title: "Annexe — Mémoire : format et dépôt d'un souvenir"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Mémoire : format et dépôt d'un souvenir

> **Quand la lire** : avant d'écrire un souvenir.
> **Pourquoi** : Une mémoire sans le bon format, au mauvais endroit, ne sera jamais retrouvée.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Memory.md#3 -->
**Rule**: write every new memory as one `.md` file in Shinzo `05-Memoire/`, with
the full Shinzo frontmatter (below). The agent memory dir is redirected there
(`autoMemoryDirectory`); a PostToolUse hook commits + pushes Shinzo on each write.

<!-- source: Memory.md#4 -->
**Why**: one memory store for all tools, enforced by code, not by AI discipline
(see Shinzo `05-Memoire/feedback-code-enforcement-over-instruction-reliance`).

<!-- source: Memory.md#5 -->
**Trigger**: any durable fact saved — past decision, user preference, lesson,
reference. Not conversation-only details.

<!-- source: Memory.md#6 -->
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

<!-- source: Memory.md#8 -->
**Les deux existent, produits par `.claude/hooks/lib/memory_index.py`, jamais
écrits à la main** (un sommaire recopié vieillit et ment — famille de l'inventaire
de composants, 79 annoncés contre 149 réels le même jour) :

| Fichier | Rôle | Contenu |
|---|---|---|
| `README.md` | sommaire complet, pour naviguer | tous, groupés par type |
| `MEMORY.md` | chargé à chaque session | `user` + `feedback` — ceux qui changent la façon de travailler |

<!-- source: Memory.md#9 -->
**Proof**: `python .claude/hooks/lib/memory_index.py --check` sort en erreur dès
qu'un souvenir manque à un sommaire.

<!-- source: Memory.md#11 -->
**Confidentiality (overrides)**: never write personal data into a memory file
(email, name, handle, phone, address, any re-identifying identifier). See
`Confidentiality.md`.

<!-- source: Memory.md#12 -->
**Proof**: the file exists in Shinzo `05-Memoire/` AND appears as a Shinzo commit
(hook prints `[memory] committed + pushed: <file>`).

<!-- source: Memory.md#13 -->
**Without hook**: write the file at the Shinzo path with the schema, then commit
+ push Shinzo by hand.
