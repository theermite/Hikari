# Rule-Format — How to write a rule

**Proof state**: 🔵 modern — LLM instruction-writing, arXiv-grounded.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Rule-Format.md`
> Writing standard for every rule. Applied when creating / editing rules, not every session.

**The principle**: a written rule does not apply by itself. An LLM perfectly recites
the rule it just violated, and reasoning degrades adherence to strict rules. Write for
how models actually behave, not to look nice. Stays portable outside Claude Code.

**The format — 6 fields, fixed order**:

| Field | Role | Mandatory? |
|-------|------|-----------|
| Level | BLOCKING / DEFAULT / GUIDE — a single marker | yes |
| Rule | statement in the POSITIVE, imperative, deterministic | yes |
| Why | 1 line — the reason | yes |
| Trigger | WHEN, named precisely (never "when relevant") | yes |
| Proof | falsifiable artefact (dated marker, test) — NEVER a checkbox | if verifiable |
| Without hook | what the AI does when no code enforces it | if portable |
| Proof state | 🟢 robust / 🟠 partial / 🔵 modern — the rule's grounding strength (Go Rin legend), a one-line label at the very top of the file | yes |

**Proof state (🟢/🟠/🔵)**: distinct from *Proof* (the falsifiable artefact). Proof state
= HOW WELL-GROUNDED the rule is. 🟢 robust (documented tradition + solid science/industry),
🟠 partial (real grounding but thinner), 🔵 modern (mainly recent science/engineering or
internal design). Inherited from Michi no Kata Go Rin. It is a header label on EVERY rule,
regardless of the variable geometry below.

**Variable geometry** (beyond ~30 active instructions, conformity drops):
BLOCKING = 6 fields ; DEFAULT = Rule + Why + Trigger ; GUIDE = Rule + Why.

**The key: falsifiable proof, never a checkbox.** A "✓ verified" box is
non-falsifiable (the model ticks it as a plausible word). A dated, sourced artefact is
verifiable. Golden rule: ask for a verifiable artefact, never a self-attestation.

**Anti-negation**: write each rule in the positive ("do X"). This is reliability, not
style — a model reads negation poorly, the salient token stays X, the instruction may
produce the opposite. If a prohibition is unavoidable, glue the positive alternative
right after ("never rm -rf on work; instead mv x x-backup").

**Key writing rules**: a single emphasis marker (no BLOCKING+MUST+CRITICAL stacked) ;
named trigger ; jargon glossed on first use ; for a rules file, BLOCKING at the top AND
repeated at the end (lost-in-the-middle).

**Portable-form rules**:
- **P1** — define the single source (Shinzo) once at the top with its full path
  (github.com/theermite/Shinzo), never the name alone (a model translates 心臓 = "heart"
  and loses the repo).
- **P2** — numbers = ceilings paired with an intent ("shortest possible, max 1500
  chars"), never bare targets (a literal model fills the ceiling).

**Portability — the "Without hook" field in 3 tiers**: Code-enforced (Claude Code /
Kobo, a hook enforces the proof) ; Structured-written (Gemini / Perplexity / chat, the
AI emits the proof without a net) ; Micro (≤1500 chars, only the spirit + 2-3 BLOCKING hold).

**The honest limit**: this format raises the probability of conformity, does not
guarantee it. The only hardness comes from an external verifier (hook, human, 2nd model).

**Detail** (AI mechanism per field with arXiv / Anthropic sources, developed examples) → Shinzo.
