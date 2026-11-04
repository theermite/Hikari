---
title: "Annexe — Session qui code seule"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Session qui code seule

> **Quand la lire** : avant de lancer plusieurs briques sans validation brique par brique.
> **Pourquoi** : Trois portes bloquantes : pré-vol prouvé, relecture indépendante avant fusion, rien d'irréversible.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Autonomous-Session.md#3 -->
**Rule**: An autonomous session proves its ground before starting, hands its output to a
different context for review, and leaves every irreversible act to Jay.

| # | Gate | What it means |
|---|------|---------------|
| 1 | **Pre-flight proves** | Run ONE real project command (`mix test`, `pnpm test` — never `echo`) AND read the PET. Start only when the command exits 0 and the PET names exactly one unambiguous next brick. |
| 2 | **Independent review before merge** | The context that wrote the code never reviews it. A fresh context reads the diff and reports what it found. |
| 3 | **Nothing irreversible** | Work on a branch. Leave `main`, deploys, force-push and every outward write (send, publish, pay) to Jay. |

<!-- source: Autonomous-Session.md#4 -->
**Why**:
- **Gate 1** — both failures happened on 2026-07-16. A systemd sandbox killed every Bash
  call (`EROFS`), and an ambiguous PET stalled a run. Each was detectable in 30 seconds,
  before spending the run.
- **Gate 2** — on the first autonomous delivery, an independent review found 2 real
  defects: an unformatted test (the run's own lint gate) and a transcription language
  hardcoded to `"fr"`. A run optimises the brick as written; it cannot judge the need
  behind it. Anti-circular Layer 2, applied (see `Quality.md`).
- **Gate 3** — the run's job is to produce a reviewable branch, never to decide what ships.

<!-- source: Autonomous-Session.md#5 -->
**Trigger**: any session asked to run more than one brick without per-brick validation —
a `/autonome` bot run, or a local session told "do phase X of project Y".

<!-- source: Autonomous-Session.md#6 -->
**Proof**: an append-only run journal `docs/Sessions/run-<YYYY-MM-DD-HHMM>.md`, one line
per brick — brick · delivered · verification (the real command AND its exit code) · commit
SHA · decision. Header carries the global verdict: bricks done, where it stopped, why.
Plus the reviewer's verdict before any merge. A command output or a SHA, never a
checkbox: "tests OK" proves nothing, "`mix test` → 5424 tests, 0 failures" does.

<!-- source: Autonomous-Session.md#7 -->
**Without hook**: emit the journal yourself and quote the pre-flight result verbatim in
the report. Jay stays the last external verifier — the only hard guarantee
(`Quality.md` A9, Jidoka Portability Bridge).

<!-- source: Autonomous-Session.md#8 -->
**Stop protocol** (from the conception, unchanged):

| Trigger | Action |
|---------|--------|
| 1st failure (test, lint, types, coverage, review) | **Informed retry**: veille FIRST (real cause, current method), then fix. Never a blind retry — a stale dataset causes many failures, and a veille clears them without disturbing Jay. |
| 2nd blocking failure, same brick | STOP · trace · notify ("context reset recommended") |
| No commit produced · budget exhausted · external dependency absent | Immediate stop, no retry — nothing to diagnose |

<!-- source: Contrat-Autonomie-2026-10-17.md (ajout 2026-11-04 : demande de Jay du 2026-10-17, restée sur une branche non fusionnée) -->
**Autonomy contract (BLOCKING — Jay 2026-10-17)**: a run longer than one brick starts
only from `docs/Contrat-Autonomie.md`, written at the end of `/concevoir` (step 8bis) and
validated with the CDC/PET. It sets the **mode** (`brique` · `lot` · `projet` to the
deliverable), a **live-verifiable deliverable** (for UI: the mock-up's parcours replayed on
the real app), a **measured budget** (alert 80 %, clean stop 100 %), **checkpoints** (blocking,
or digest while the run continues on independent bricks) and the **deploy policy** (default
`jamais`). Gate 1 also lints the contract: `python .claude/hooks/lib/contract_lint.py
docs/Contrat-Autonomie.md --cdc-version <v> --pet-version <v>` — no budget, `projet` without a
blocking checkpoint, CDC/PET version changed → the run does not start. The cost estimate
(median cost per brick × bricks × 1.5 vs the ceiling) only runs when `--history <costs.json>` is
given; without it the linter warns `estimate_unavailable` and the live budget stop (100 %) is the
only limit. No tool writes that history file yet. Jay's validation replaces the reformulation for the whole run; it authorises scope,
never quality. Detail → `docs/Briefs/Contrat-Autonomie-2026-10-17.md`.
A blocking checkpoint flagged `avant_mise_en_ligne` is Jay's agreement for that deployment;
without it gate 3 applies (nothing is deployed).

<!-- source: Reprise-Sur-Ordre-2026-11-04 (demande de Jay : reprendre un run arrêté sans tout refaire) -->
**Hot resume, on Jay's order (BLOCKING — Jay 2026-11-04)**: a run that stopped (token limit, cut,
checkpoint) restarts only when Jay says so ("reprends"), and its brief is COMPUTED, not written
from memory: `python .claude/hooks/lib/run_resume.py docs/Contrat-Autonomie.md
docs/Sessions/run-<date>.jsonl --cdc-version <v> --pet-version <v>`. Exit 0 = resume at the brick
it names (or nothing left); exit 1 = refused or waiting for Jay; exit 2 = unreadable.
**The journal is written by a tool, never by hand or in prose**: one JSON line per event, appended with
`python .claude/hooks/lib/run_journal.py brique <file> --brique B07 --livre oui --commande "..." --sortie "..."
--sha <hex> --cout <USD|inconnu>` (also `arret <file> --raison ...` when the run stops, and
`point-valide <file> --id C1` ONLY on Jay's word). Write the cost of EVERY attempt. The reader is
CLOSED: a line that is not exactly a valid event stops the resume; nothing is skipped, nothing is
guessed. The list of bricks is closed too: `scope` of the contract (brique, lot) or its `briques`
list (projet, COMPUTED from the PET roadmap by `python .claude/hooks/lib/plan_bricks.py docs/PET.md`, never copied by hand; `--check <contract>` lists every gap, and the tool refuses while the PET contradicts itself; closure invariant: every brick id written ANYWHERE in the PET, and every brick named by a range written `B40-B43` or `B02a-c`, must exist in the roadmap, whatever the Markdown structure; any HOLE in the numbering of the roadmap (B13 then B15) is a problem whatever way a range is written in words (`--trou`, `--numerotation-libre` to accept on purpose); the roadmap is ANCHORED to the section titled « Roadmap » / « Feuille de route » (`--section TITLE`), a table elsewhere is never merged but its brick ids must exist in the roadmap; work items without a brick id (priority or session tables) are NOT in the list; NOT guaranteed: a brick forgotten at the very start or end of the numbering and written nowhere else or only abbreviated (`B03-05`, `B24a/b/c`, `B15/16/17`, `B-008→010`), a wrong status in the roadmap, ids outside the `B` format (T12, B1000), a whole family missing; `--inclure` / `--connu` settle a case on purpose, visibly); the resume tool itself parses no PET.
A brick is proven only if its LAST attempt is delivered, names a command and an output (text, not a
dash) and carries a SHA git knows; anything else is redone. The tool refuses when the contract is
void or does not lint, or when the spend reaches the stop threshold. It WAITS (exit 1) while a
blocking checkpoint, or a milestone naming no brick (`apres: "fin du lot"`), is not validated; while
any line of the journal is unreadable; and while any attempt has a null or non-numeric cost (an
unmeasured spend is never counted as zero). Limits, written: a SHA proves a commit exists, not that the
brick's work is in it (a SHA shared by several bricks is flagged); a checkpoint validation must only be
written on Jay's word, never by the run on its own; `tokens_max` and `duree_max_h` of the contract are
not checked here, only the cost ceiling. The tool never launches work: after exit 0, the session
reads the brief to Jay in two lines and continues from the named brick. **Not covered yet**:
automatic resume after a limit (no scheduler), and nothing yet writes the cost history that
activates the estimate.

<!-- source: Autonomous-Session.md#9 -->
**Trust model**: never believe the agent's textual "it works". Truth comes from sources
independent of the agent — re-executed commands (exit codes), git state (does a commit
exist?), coverage numbers, and a reviewer of equal or superior level (fresh and complete context) on Critical modules.
*[Amendé 2026-10-28 : « a different model on Critical modules » remplacé par un relecteur de niveau égal ou supérieur, en contexte frais et complet (Jay 2026-10-28).]*
