# Independent-Review — Fresh eyes before anything ships

**Proof state**: 🟠 partial — real grounding (8 defects caught in one evening, 2026-08-10), still a young rule.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Independent-Review.md`

**Level**: BLOCKING.

**Rule**: before a deploy or a propagation, a context that did NOT write the code reads
the diff and returns a verdict. Emit the verdict as a marker, then ship.

**Why**: the context that wrote the code cannot see what it failed to imagine. It
optimises the solution it already chose. A fresh reader starts from the problem.

**Trigger** — any command that puts code in front of someone else:

| Class | Examples |
|-------|----------|
| Deploy | `docker compose up`, `systemctl restart`, `ssh <host> <action>`, `deploy.sh` |
| Force-push | `git push --force`, `--force-with-lease`, `-f` — history you cannot get back |
| Publish | `npm publish`, `cargo publish`, `twine upload`, `mix hex.publish` |
| Propagate | `propagate-methodology.py`, `sync-repo` — 30 repos multiplies a defect |

**Not** every commit, and **not an ordinary push** (Jay 2026-08-11): a branch push is
reversible, and a review several times a day would kill the rule by friction. What stays
gated is what cannot be taken back. A build (`pnpm build`) is not shipping.

**Proof** — THREE markers, in THIS order. The gate refuses at each step, so emitting them
out of order costs a round trip (it cost three, on 2026-09-07):

```
[REVIEW-BRIEF]
- objectif: <what the project is for>
- perimetre: <what is under review>
- zones suspectes: <where to dig>
- consigne: <must ask to REFUTE, never to validate>
```
then, after the review comes back:
```
[REVIEW] par <relecteur> le <YYYY-MM-DD> sur <empreinte> — verdict: <PASS|FAIL>, <ce qui en est sorti>
```

`<relecteur>` = a sub-agent of a level EQUAL OR SUPERIOR to the writer's, in a fresh AND complete context (the
full brief, not an empty one), or a human (Jay 2026-10-28).
Never a weaker reviewer, never the writer's own conversation. A sentence
saying "I had it reviewed" is NOT proof — it is a self-attestation, and a model produces
one as easily as the truth (`Rule-Format.md`).

**`<empreinte>` is the commit that was actually read** (7+ hex, from `git rev-parse HEAD`).
Added 2026-09-07 after Jay asked « as-tu bien vérifié tout ce que tu vas propager ? ». The
answer was no: seven commits had landed after the last green verdict, and the gate would
have let them ship — it read the verdict's WORD, never which code it covered. A green light
does not survive the code it validated: when HEAD has moved, the gate refuses and names both
SHAs. A phrase cannot prove what it covered; a commit can.

**Correcting a finding starts with a search, never with code (BLOCKING — Jay 2026-09-07)**:
« lorsqu'il y a des relectures qui sont faites et que les corrections sont tentées, il faut
absolument faire des recherches Web pour s'assurer d'avoir les informations à jour ». The
`[CAUSE]` block owed after a FAIL carries a fourth line, `- veille: <dated source or link
consulted BEFORE fixing>`. A line without a date or a URL is refused — "I looked" is not a
search, and a model writes that sentence as easily as the truth.

**Why**: measured the same day. Five review rounds, ~15 real defects, every fix written from
scratch with zero research — each time waved through as "internal refactor, no new
dependency", true to the letter and a way past the real question. The first search, run only
because Jay asked, found that the reference tool for what we hand-roll **refuses to start on
a repo with uncommitted work** — the very rule whose absence had cost the whole morning. A
fix written in reaction feels urgent and research feels like a detour; it is the reverse.

**Legitimate skip** (closed enum — an open motif field becomes "no time" within a week):

```
[REVIEW-SKIP] motif: <rollback | hotfix-production-down | no-code-change | review-already-done>
```

## The launch is gated too, not only the verdict (BLOCKING — Jay 2026-08-30)

A reviewer handed no objective can only check that the code agrees with itself. That is
the bias Jay named: *« il ne prend pas en compte l'objectif et/ou la vision du projet, ce
qui lui donne un point de vue biaisé. »* Until 2026-08-30 nothing governed the launch —
this rule checked the verdict that came back, while the prompt was improvised each time.

**Emit the brief BEFORE launching the reviewer:**

```
[REVIEW-BRIEF]
- objectif: <what the project is FOR, one sentence, in user terms — never technical>
- perimetre: <the diff / files handed over>
- zones suspectes: <where to look first>
- consigne: refuter
```

`consigne` is a closed value: **refuter**. A reviewer told "check this" confirms; a
reviewer told "refute this" finds — "contredis ce code" produced 8 findings where "relis
ce code" produced a summary (2026-08-10). Asking for validation is not a review.

**Demand the verdict as the FIRST LINE of the reviewer's output, and re-ask when it is
missing.** A reviewer stops without concluding about one time in two — nine relaunches in
one evening (Kanee 2026-08-19), and a first output that was a train of thought rather than
a verdict (Boken 2026-08-18). Both were noted as actions for the methodology and neither
was implemented until now.

**Verify the reviewer's claims yourself before acting.** A reviewer is wrong too: two of
the eight findings of 2026-08-10 needed a counter-check before they held.

**Proof**: `hooks/guards/pre-deploy-review-check.py` refuses a PASS verdict with no
`[REVIEW-BRIEF]` carrying its four filled fields and a `consigne` that asks to refute. The
brief must precede the verdict and sit after the previous PASS, so review #1's brief cannot
excuse review #2. It carries over a FAIL and its corrective round — the objective did not
change, and re-writing four lines each round is friction with no added truth.

**The honest limit** (independent review, 2026-08-30): the gate checks that a brief exists
and belongs to this cycle. It **cannot** check that the brief describes the diff actually
handed over — a brief about the payment module would satisfy a review of the theme toggle.
Nothing textual can prove that link. So this raises the probability of a real briefing; it
does not guarantee one. The hard guarantee stays an external verifier (`Quality.md` A9).

**Without hook**: write the brief in the conversation before launching, and quote the
reviewer's first line verbatim.

**The reviewer emits the marker itself, never a paraphrase** (independent review,
2026-08-30). The review agents are told to answer with `[REVIEW] par <relecteur> le <date>
— verdict: ...` as their first line — the exact form both gates parse. A template
prescribing any other wording (`VERDICT: PASS`) makes a compliant reviewer INVISIBLE to
the gates, so a real FAIL never opens its `[CAUSE]` obligation. That defect was introduced
and caught the same day; same family as 2026-07-30, *when a written rule does not bite,
look for the template that contradicts it*. A test now reads the agent files on disk and
parses every marker they prescribe, so the two cannot drift apart in silence.

**What it costs, honestly**: 5 to 10 minutes per review. On 2026-08-10 it caught eight real
defects across three versions of one fix — including a guard that a plain newline
disabled entirely. Each was found before it shipped to 30 repos.

## Proportion: severity, usage, ceiling and the step back (BLOCKING — Jay 2026-10-28)

Measured the same day (`docs/Briefs/Audit-Systeme-De-Relecture-2026-10-28.md`): 93 reviewers
launched since 2026-09-05, three sessions at 14, 15 and 16. The reviewers' facts held (every
survivor replayed was real) ; what produced the chains was a system with no severity threshold, no
ceiling, and briefs that asked for mutation campaigns. Jay had named it on 2026-10-17 (« une trentaine
de relectures pour des cas qui n'arriveront peut-être jamais, ce qui est absurde ») — and the fix was
only ever coded in the autonomous-worker review of Telegram-Bots. Five changes, accepted by Jay:

1. **Closed severity.** A FAIL is for SHIPPED code only, in four cases: (a) something that should be
   refused passes · (b) a legitimate command stays refused in normal use · (c) data loss · (d) a
   secret exposed. Everything else is a remark.
2. **Ceiling.** Five remarks at most, gravest first ; at most five targeted mutation tries, except for
   the **critical** class (rule 03 § 2 bis), where mutation is required.
3. **Usage context in the brief**: who uses it, how many, with which rights, and the risk class. The
   class sets the depth: mutation only for the critical.
4. **The model is traced by code, never by hand**: the session journal carries each message's model.
   A reviewer or a report that writes « rédacteur : Opus » from memory writes something false.
5. **Review what ships, not what proves it.** Tests read by a fresh context are remarks, never a FAIL,
   while the shipped code is PASS.

**The step back (Jay 2026-10-28)**: at the **second FAIL on the same family of defect**, OR the second
FAIL in a row on the same set of files (different families included), the writer does NOT retry the
same kind of correction. It takes a step back on the problem to find the ROOT cause (dated research,
changed approach) and writes it in its report. This is the expert's job, not a hand-off: Jay looks at
the whole and proposes another direction when the writer has not found the root cause. So Jay is
consulted only if, after the step back, the root is still not found (mandate stop 3: exact state,
what was tried, what blocks, every pertinent option) — never systematically at the second FAIL.
Rounds that find a different defect on different files are the review doing its job and are not counted.

**Honest limit — what the code holds today**: the guard (`pre-deploy-review-check.py`) now judges what
ships (a dry run is not shipping ; a documentation-only gap keeps a green light valid, for the
methodology propagation only ; the brief is read in the real launch prompt). The five changes above
live in this rule and in the reviewer's own definition (`agents/cross-model-reviewer-master.md`). **Not
yet code**: a required `usage` field in the brief, the model trace read from the journal, and the
count of consecutive FAILs on the same files. Until then they hold by discipline — and the audit says
what discipline alone produced.

## A FAIL is not a warning — it opens an obligation (BLOCKING)

A review that finds something has done half the work. The other half is refusing to patch
the reported case and walking back to where it came from. **Trigger**: any verdict FAIL.
The next commit carries:

```
[CAUSE]
- famille: <the CLASS of defect, not the single case>
- cause: <where it comes from>
- ce qui empeche la repetition: <test, shared component, gate — an artefact>
- appelants reels: <yes — how verified (grep, callsites) | non-applicable — why>
- garde a l'envers: <does the test redden if you remove the guard? yes | non-applicable>
```

**The last 2 lines (BLOCKING — 2026-09-11)**: measured across Shinkofa-Backend, Kōbō and
Hikari over 21 days, almost every defect a review kept finding was detectable BEFORE writing
— a fix with no real caller (« le correctif n'avait aucun appelant reel »), a guard whose
test never actually exercised it without the guard. Same fields added to `[ROBUSTNESS]`
(`Monozukuri.md`) — one question, asked at both the points where it already fires.

**At the second FAIL in a row ON THE SAME FAMILY, patching is over — step back (Jay 2026-10-28).**
The commit must also carry `- approche changee: oui — <what is structurally different now>`, and the
report says what the step back found: the root cause, the dated source consulted, why this approach
differs. Why: a family that survived one correction survives the next one of the same shape. Two
failures say the design is wrong, not the line. Taking the step back is the writer's own work; Jay is
asked only when the root stays unfound after it — he brings the view of the whole that points to
another direction. (`post-review-cause-check.py` demands the `approche changee` line at the commit; the
quality of the step back holds by discipline today.)

**The counter counts DEFECTS, never rounds (BLOCKING — Jay 2026-08-30)**: *« si la
relecture trouve une nouvelle erreur ce n'est pas une deuxième tentative [...] si tu
essaies 2 ou 3 fois de corriger LA MÊME erreur et n'y parviens pas, tu dois prendre du
recul et/ou me consulter. »* Two reviews finding two DIFFERENT problems is the review
doing its job, not persistence — escalating there punishes a working review. So a FAIL
marker names the family it is about:

```
[REVIEW] par <relecteur> le <YYYY-MM-DD> — verdict: FAIL, famille: <slug>, <ce qui en est sorti>
```

A different family restarts the count at one. An **unnamed** family counts with the
previous unnamed one — leaving the slug out must never be the cheap way past the gate. **One exception (Jay
2026-10-28)**: two FAILs in a row on the SAME set of files also call for the step back even when their
families differ — a chain on one artifact says the design, not the line, is wrong.

**Proof**: the marker sits in the commit message, hook-enforced
(`hooks/quality/post-review-cause-check.py`). A commit on an unrelated subject may be
excused with `[CAUSE-SKIP] motif: <sans-rapport | revert | wip-sauvegarde>` — but never at
the second failure, where the excuse is exactly what must not happen.

**Where this came from**: 2026-08-10, five reviews in a row rejected the same family —
hand-rolled shell parsing. Each fix closed the reported case and reopened the family one
bypass later. The cure was one shared parser, and it arrived at the fifth round instead of
the second. Jay: « le problème n'est pas que tu aies fait une erreur, c'est que tu as
persévéré dans cette erreur. »

**The honest limit**: the hook checks that a marker appeared, and that its verdict says
PASS. It cannot prove the reviewer was truly independent — the agent could write the marker
itself. So this gate raises the probability of a real review; it does not guarantee one.
The hard guarantee stays what it always was: an external verifier — Jay, or a model that is
not this one (`Quality.md` A9).

**Without hook**: emit the marker yourself, quote the reviewer's verdict verbatim, and
name what it found. Jay stays the last external verifier (`Quality.md` A9).

**BLOCKING recap**: fresh eyes before a deploy or a propagation · a launch brief carrying
the project's objective and asking to REFUTE · the verdict as the reviewer's first line ·
a falsifiable marker, never a claim · a closed list of skips · the FAIL counter counts the
same family, never the rounds.
