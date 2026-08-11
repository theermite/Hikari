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

**Proof** (falsifiable marker, hook-enforced):

```
[REVIEW] par <relecteur> le <YYYY-MM-DD> — verdict: <PASS|FAIL>, <ce qui en est sorti>
```

`<relecteur>` = a sub-agent with a fresh memory, another model, or a human. A sentence
saying "I had it reviewed" is NOT proof — it is a self-attestation, and a model produces
one as easily as the truth (`Rule-Format.md`).

**Legitimate skip** (closed enum — an open motif field becomes "no time" within a week):

```
[REVIEW-SKIP] motif: <rollback | hotfix-production-down | no-code-change | review-already-done>
```

**How to make the review bite** — a reviewer told "check this" confirms; a reviewer told
"refute this" finds. Three rules, learned the same evening:

| # | Rule | Why |
|---|------|-----|
| 1 | Ask for refutation, never validation | "Contredis ce code" produced 8 findings; "relis ce code" produces a summary |
| 2 | Name the suspect areas, and demand a reproduction | Every real defect that evening came with a command and its output — not an opinion |
| 3 | Verify the reviewer's claims yourself before acting | A reviewer is wrong too. Two of its findings that evening needed a counter-check before they held |

**What it costs, honestly**: 5 to 10 minutes per review. On 2026-08-10 it caught eight real
defects across three versions of one fix — including a guard that a plain newline
disabled entirely. Each was found before it shipped to 30 repos.

## A FAIL is not a warning — it opens an obligation (BLOCKING)

A review that finds something has done half the work. The other half is refusing to patch
the reported case and walking back to where it came from. **Trigger**: any verdict FAIL.
The next commit carries:

```
[CAUSE]
- famille: <the CLASS of defect, not the single case>
- cause: <where it comes from>
- ce qui empeche la repetition: <test, shared component, gate — an artefact>
```

**At the second FAIL in a row, patching is over.** The commit must also carry
`- approche changee: oui — <what is structurally different now>`. Why: a family that
survived one correction survives the next one of the same shape. Two failures say the
design is wrong, not the line. If you believe the approach is right, say so to Jay and let
him decide — never spend a third round.

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

**BLOCKING recap**: fresh eyes before a deploy or a propagation · a falsifiable marker,
never a claim · a closed list of skips.
