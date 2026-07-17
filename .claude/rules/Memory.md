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

**Index**: the Shinzo memory index is `README.md`, not `MEMORY.md`. Do not create
a `MEMORY.md`.

**Confidentiality (overrides)**: never write personal data into a memory file
(email, name, handle, phone, address, any re-identifying identifier). See
`Confidentiality.md`.

**Proof**: the file exists in Shinzo `05-Memoire/` AND appears as a Shinzo commit
(hook prints `[memory] committed + pushed: <file>`).

**Without hook**: write the file at the Shinzo path with the schema, then commit
+ push Shinzo by hand.

**Detail** (raw note vs curated fact, 3 portability tiers, Kobo re-sync) → Shinzo.
