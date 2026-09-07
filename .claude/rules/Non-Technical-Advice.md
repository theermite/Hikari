# Non-Technical-Advice — Advice that its reader can actually execute

**Proof state**: 🔵 modern — measured internal audit + 2026 field research.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Non-Technical-Advice.md`
> Origin: audit A7 (2026-09-03) + Jay's framing (2026-09-06): « avoir des conseils qui ne
> prennent pas en compte mes contraintes, mes challenges, l'objectif, la vision du projet
> ou le fonctionnement du projet, c'est absolument absurde ».

**Level**: BLOCKING.

**Rule**: Non-technical advice — marketing, sales, communication, content, positioning —
passes **three gates**: every figure carries a named dated source · the advice names who
executes it and fits their real constraints, tools and hours · the advice holds its
position without flattering the person who asked.

**Why**: 7 advisory agents, ~75 numeric claims, **zero sources**, and a prescribed cadence
costing **14 to 34 h/week** to one person — none of them ever gave a single piece of advice
in 112 sessions. Advice that ignores the executor is not weak advice, it is unusable.

**Trigger**: producing or reviewing any advice on marketing, sales, communication, content,
audience, pricing or positioning — for Jay, for an ambassador, or for a client.

## Gate 1 — Sourced

Every figure carries a **named source and its date**, or it is removed. A threshold with no
source produces a false alarm or a false assurance; both cost more than having no threshold.

Measured cases (audit A7, 2026-09-03): an alert on « organic traffic −20 % » that would
fire permanently · a freshness rule too lax by a factor ~24 · six funnel targets invented
outright. **A plausible number is the dangerous kind** — the conversion rate carrying a
whole business model (Shinkofa-Browser `docs/Strategie/Grille-Tarifaire.md`) was announced
as « the bottom of the industry range », when the consumer median sits near 2,1 %
(RevenueCat, State of Subscription Apps 2026, vérifié 2026-09-06), i.e. **above** — the
opposite of what the document claimed.

**This rule passes its own gate**: `check-advice-sourcing.py` was run on this file, it
failed on three lines, and they were sourced rather than exempted.

## Gate 2 — Applicable to whoever executes it

The advice **names its executor** and is built from their reality, not from an average:

| What must be named | Why |
|---|---|
| **Who executes** — Jay, an ambassador, a provider | Advice for Jay and delegable advice are not written the same way |
| **Their real tools** | No market benchmark knows tools we built. Measured 2026-09-06: automated production and distribution turned a 14-34 h/week cadence into **~9 h** |
| **A declared time budget** | Never prescribe a cadence without writing what it costs. This omission is the direct cause of the unliveable plan |
| **An abandon criterion** | What will show a channel failed, and by when. Without a stop rule, nothing ever stops — one exhausts oneself instead |

**Jay's functioning is a constraint, not a preference (BLOCKING)**: sustained executive
production is not available to him — his words, 2026-09-06: « mon fonctionnement ne me
permet pas de faire ce que tout le monde est capable de faire, surtout en termes de
production et d'actions exécutives ». **Advice that requires it is wrong for him, however
right it is elsewhere.** Prefer: what he produces once and others reuse · what a tool
carries · what an ambassador executes under his one-click approval.

**Read the ecosystem BEFORE advising, not after (BLOCKING — Jay 2026-09-06)**: « il faut
prendre en compte l'écosystème Shinkofa et les outils que l'on utilise, sinon c'est du
gâchis ». The state of the art is the **input**, never the output: take the strongest
technique available, then route it through what we already own.

| Step | What it means |
|---|---|
| 1. Take the best technique | Sourced, current, proven — no lowering of the bar |
| 2. Open the ecosystem | What already does this? Read the code or the product, do not guess |
| 3. Name the carrier for each step | Which tool carries it · what a person must do · what genuinely needs building |
| 4. Only then, price the human steps | The hours left after the tools have taken their share |

**Why it is waste otherwise**: a generic best practice re-prescribes by hand what a tool
already does. Measured 2026-09-06 — the prescribed cadence priced editing, subtitles,
vertical reframing, voice-over and multi-network publishing as manual work; all of them are
already automated here, and the approval gate the advice called for **already existed in
code**. The advice would have rebuilt what was built, and mispriced the rest by a factor of
about three.

**The ecosystem spans private and professional life.** A tool built to smooth Jay's day
counts as much as a production tool — both change what advice is realistic for him.

**Compute with the real tools, never with the market average.** A benchmark describes
people without our tools. Open the code or the product, count what is already automated,
and only then price the human steps.

## Gate 3 — Non-complacent

Declare any conflict of interest · zero manipulative pattern (see `Dignity.md`) · hold the
position under insistence that brings no new evidence. Model complacency is the number one
risk of an advisory agent, and it was guarded nowhere on this axis.

**Proof**: `scripts/check-advice-sourcing.py --check` fails on any line advancing a figure
with nothing to support it (242 lines across the 32 agents, measured 2026-09-06). Plus the
marker, emitted with the advice:

    [CONSEIL] executant: <qui> · budget: <N h/sem> · abandon: <ce qui dira que ça a échoué>

**Without hook**: emit the marker, and state the source of every figure inline. An advice
with no named executor is a draft, not advice.

**BLOCKING recap**: a figure without a dated source goes · the best technique is routed
through the ecosystem we already own, read before advising · the advice names its executor,
their tools, their hours and a stop rule · Jay's functioning bounds what can be advised to
him · never flatter, never a manipulative pattern.
