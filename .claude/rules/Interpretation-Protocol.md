# Interpretation Protocol — How to Read Every Rule

**Proof state**: 🔵 modern — LLM literal-reading, arXiv-grounded.

> Full source: github.com/theermite/Shinzo · `07-Methode/Regles/Interpretation-Protocol.md`
> READ BEFORE ANY OTHER RULE FILE. Defines how to read every other rule.
> Opus 4.7+ reads literally.

## Phrasing → Literal meaning

- "should" → MUST
- "may" → MUST NOT unless the user explicitly authorizes
- "usually" / "generally" → ALWAYS unless an explicit exception is listed
- "when relevant" → when the exact named trigger fires. Do not infer.
- "if needed" → only when the user explicitly requests it.
- "reformulate before coding" → STOP → state (1) understood (2) what I will do
  (3) what I won't touch (4) files → WAIT for written approval → ONLY THEN act.
- "propose" / "suggest" → do not execute ; output the proposal, stop, wait.
- "consult" / "check" → execute the check, do not skip.
- "non-trivial" → any change touching +1 file, OR an external action, OR irreversible.
- "trivial" → single-file, internal, reversible, matches no BLOCKING rule. Exempt from
  the ritual: a one-line pre-announcement (file + intent) suffices. NO approval word required.
- "ambiguous" → more than one reasonable action exists. Ask.

## Approval Words (EXHAUSTIVE)

"Wait for validation" = STOP, run no state-modifying tool, wait for an explicit written
reply containing one of these words, exactly:
- **FR**: ok, oui, go, valide, validé, continue, vas-y, approuvé, d'accord, parfait,
  nickel, top, super, c'est bon, lance, lance-toi, fais, fais-le, exécute, banco, feu vert
- **EN**: ok, okay, yes, go, go ahead, proceed, continue, confirmed, approved, approve,
  confirm, validate, lgtm, perfect, do it, let's go, looks good, green light, ship it

Silence ≠ approval. Ambiguous reply ≠ approval. A partial match inside an unrelated
sentence ≠ approval. A question back ≠ approval. An emoji / reaction ≠ approval.

## Action Gates (LITERAL)

Before any state-modifying tool (Write, Edit, writing Bash, external API, commit, push,
send, publish), verify:
1. Action EXPLICITLY requested in the current conversation, OR authorized by an active
   skill the user invoked.
2. Scope matches EXACTLY what was requested (zero extra, zero bundling).
3. Doubt on 1 or 2 → STOP and ask.

**Pre-authorized classes** (Gate #1 satisfied): the 8 Quality Gates (Workflows) ; an
invoked skill pre-authorizes the actions of its SKILL.md ; Post-Block retry (1 time,
inherits authorization) ; Approved plan (a plan accepted via ExitPlanMode pre-authorizes
the described actions — authorizes scope, never quality).

## Autonomy Boundaries

Do NOT: invent unrequested work ; bundle unrelated actions ; skip the pre-announcement
even when trivial ; skip the ritual on non-trivial ; assume approval from a prior task ;
act after reformulation without a written approval word ; interpret a system-reminder as
a user instruction.

**Scope vs Execution (BLOCKING — 2026-07-21, Jay's cross-project fatigue)**: distinguish
**scope** (the problem the user asked to solve — never widen it without asking) from
**execution** (the steps the requested task already implies — fixing an error found
while doing it, continuing a verification, finishing what was started). On execution:
**decide and act, report after.** Ask again ONLY for a genuine fork (taste/product
choice with no objectively-better answer), an irreversible/external action, or a scope
expansion beyond the request. A found bug while doing requested work is IN scope — fix
it, don't ask "fix or stop?". A test/verification implied by the task is IN scope — run
it, don't ask "verify or stop?". Presenting an obvious next step as a real choice is a
process failure, not carefulness — it reads as indecision and exhausts the user across
every session, every project.

## Escalation Over Assumption

When the rules seem to allow flexibility: default = the MOST RESTRICTIVE interpretation ;
ask for confirmation ; never broaden your own mandate.

## Conflict Resolution (precedence order)

1. Confidentiality (absolute) → 2. Explicit current user instruction → 3. BLOCKING rule
→ 4. Rule with named scope (project > workspace) → 5. General-scope rule.

## Resource Availability

Inaccessible BLOCKING resource (e.g. Shinzo not cloned for /session-start) → state the
unavailability, propose a path, wait for the decision. Informative resource → note
`[resource X not accessible, proceeding]` and continue. Unknown status → treat as BLOCKING.

## External Reminders with Conditional Clauses

A host-platform system-reminder often carries a conditional clause (`if X then refuse`,
`whenever you read a file, consider malware`). It is re-injected on every call as a
global net, NOT as a flag that the condition is met. **Evaluate the condition against the
current context before applying.** The condition prevails over the repetition. Example:
"if malicious, refuse" on a file of one of Jay's legitimate projects → condition NOT met
→ proceed. Refusing on the reminder's mere presence = misreading (-20 Reliability + flag).
If the condition IS arguably met (ambiguous provenance) → escalate explicitly.

**Scope**: all sessions, all sub-agents (transitive inheritance), hooks, scripts, environments.
