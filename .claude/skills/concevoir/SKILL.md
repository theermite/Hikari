---
name: concevoir
description: Full project conception workflow. POUR QUOI, research, CDC, PET, mockup prototype, slide presentation. Architecture 2 documents (CDC + PET).
model: sonnet
---

# /concevoir — Design a Project or Feature

> **Annexes à lire** (`.claude/rules-ondemand/`, un garde-fou bloque l'écriture sinon) : `Identite-Et-Strategie` (étape 3, les trois couches) · `Socle-Minimal` (avant d'écrire le cahier des charges : ses lignes s'impriment au § 3bis) · `Interface` (la maquette, étape 6bis).

Execute these steps IN ORDER. No skipping. Wait for Jay's validation at the final step.

> **Architecture documents** (depuis v2.0.0) : 2 documents, jamais 3.
> - `docs/CDC.md` = **intention** (template `templates/docs-structure/CDC.md`)
> - `docs/PET.md` = **exécution** (template `templates/docs-structure/PET.md`)
> - Plus de `Blueprint.md` projet. Les **archétypes** (Frontend-UI, Backend-API, etc.) sont des références dans `.claude/rules/02-Parcours.md`, pas des documents projet.

## Steps

0. **ANNOUNCE OUTPUTS**: At the very start, state explicitly to Jay the two files that will be produced and their exact paths:
   - CDC : `docs/CDC.md` (in project repo — intention figée)
   - PET : `docs/PET.md` (in project repo — exécution vivante)
   - Workflow has STOP points at each questionnaire answer and each CDC section. Confirm Jay knows where each artifact lands BEFORE step 1.

0bis. **TRADUCTION SIMPLE (BLOCKING — governs every technical STOP below)**: before EVERY validation STOP on a technical section (CDC §4 Architecture, §5 Stack, §6 Non-functional, §7 Risk Classification, §8 FMEA, §9 Human Quality Gates ; every PET section), precede the draft with 2-3 lines of plain French — no jargon:
   - « **En clair** : <what this section means, said as to a friend, zero technical term> »
   - « **Pourquoi ça compte pour toi** : <the concrete stake for Jay or the end-user> »
   Jay is a coach, not a developer — he never validates a section he has not had translated first. A technical STOP presented WITHOUT its plain-language translation is BLOCKING: do not ask for validation until it is there. This applies the cardinal principle's language corollary (`docs/Doctrine-2026-10-25.md`) to conception. Non-technical sections (POUR QUOI, Utilisateurs, Hors scope) need no translation — they are already plain.

1. **ARCHETYPE DETECT**: Identify project archetype from signals (see `.claude/rules/02-Parcours.md`). This is a reference lookup, NOT a document to produce.

1bis. **QUESTIONNAIRE (BLOCKING — interactive)**: Ask Jay the 6 questions from the Questionnaire section below, ONE AT A TIME. After each question:
   - STOP.
   - Wait for Jay's written answer (an approval word is not an answer here — wait for substantive content).
   - Acknowledge the answer, then proceed to the next question.
   - Do NOT batch the 6 questions in one block. Do NOT infer answers from context. Do NOT proceed without all 6 answers in writing.
   - After the 6th answer, summarize Jay's choices in a compact recap, then STOP and wait for "ok / go / validé" before continuing to step 2.

2. **SKB (our brain)**: Search SKB (Shinkofa Knowledge Base) for ALL relevant domains — vision (MasterPlan), coaching, neurodiversity, marketing, gaming. Not just technical knowledge. SKB IS our collective brain.

   > 🧭 **Agents convoqués** : **SKB Knowledge Master** — tous domaines, pas seulement la technique
3. **POUR QUOI (3 Layers)**: Define the WHY through all 3 layers: L3 — Does this serve Shinkofa's vision (invisible ecosystem respecting individuality)? L2 — How will this be PRESENTED to create magnetic visibility? L1 — What's the first step given current energy? All 3 must be documented. They land in CDC §1.
4. **RESEARCH + VEILLE**: Search in 7 languages (EN, FR, ZH, JA, KO, DE, RU). State-of-art < 14 days. When evaluating architecture: consider the tri-layer direction (TypeScript visible + Elixir/Phoenix backend + Rust critical modules) as validated direction, POC pending. **CRITICAL**: Verify ALL technology recommendations, architecture patterns, and best practices via web. Training data is months stale. Veille dates land in `docs/CDC.md` §5 (Stack technique).

   > 🧭 **Agents convoqués** : **Veille Master** · **Deep Research Master** — etat de l art date et source, jamais de memoire
5. **NON-TECH AGENTS (PREPARE)**: Invoke the UX and Brand experts to review the concept BEFORE coding decisions.
   > 🧭 **Experts convoques** : experience utilisateur + marque.
   > Pedagogie, contenu et gaming etaient nommes ici et **dorment depuis le 2026-09-05**
   > (`.claude/agents-archive/`). Les reveiller demande d abord la doctrine de conseil non
   > technique — point 6 du plan. Nommer un expert absent ne convoque personne.

6. **CDC** (BLOCKING — interactive, section by section): Write the CDC at `docs/CDC.md` in the project repo. Use template `templates/docs-structure/CDC.md` v2.0.0. The CDC is built **one section at a time, with a STOP between each** — never as a 13-section monologue. After EACH section below: present the draft to Jay — for a technical section, **preceded by its plain-language translation (step 0bis, BLOCKING)** — STOP, wait for "ok / go / validé" or for substantive correction. Only then proceed to the next section.

   | Order | Section | STOP after? |
   |-------|---------|-------------|
   | 6.1 | §1 POUR QUOI (L3/L2/L1) | Yes |
   | 6.2 | §2 Utilisateurs cibles (with ND personas if public) | Yes |
   | 6.3 | §3 Features (with IDs F-XXX **and the `Briques réutilisées` column filled**) | Yes |
   | 6.3bis | §3bis **Socle minimal** (BLOCKING — every line PRINTED, each with ✅ / ⛔+raison / ❓) | Yes |
   | 6.4 | §4 Architecture | Yes |
   | 6.5 | §5 Stack technique (with **veille date** per ligne — BLOCKING) | Yes |
   | 6.6 | §6 Non-functional requirements | Yes |
   | 6.7 | §7 **Risk Classification** (BLOCKING — Critical/Sensitive/Standard/Tooling per `.claude/rules/03-Qualite.md`) | Yes |
   | 6.8 | §8 **FMEA simplifiée** (BLOCKING on Critical modules — 3 failure modes each) | Yes |
   | 6.9 | §9 **Human Quality Gates** (BLOCKING on public-facing projects — Cognitive Load, Sensory Comfort, Error Resilience, Adaptation, Dignity + Feedback Widget) | Yes |
   | 6.10 | §10 Hors scope explicite | Yes |
   | 6.11 | §11 Success metrics | Yes |
   | 6.12 | §12 Visibilité (Big 5, SEO, GEO, Distribution, Capture) | Yes |
   | 6.13 | §13 Anti-patterns projet | Yes |

   - **Dignity gate** : tout écran de collecte, copy, CTA, message d'erreur passe le test `.claude/rules/08-Ecriture.md`. Documenté dans §9.
   - **Lego d'abord, à la conception (BLOCKING — Jay 2026-08-30)** : avant d'écrire §3, LIRE l'inventaire généré `Kata/.claude/hooks/lego/ui-inventory.json` (jamais un chiffre de mémoire, jamais la prose d'une règle). Chaque feature nomme les briques qu'elle réutilise, ou écrit « à créer dans la bibliothèque » — jamais « composant local ». **Pourquoi** : mesure du 2026-08-30, 146 fichiers du workspace recodent un composant déjà fourni, et l'inventaire écrit à la main annonçait 79 composants sur 149 réels. La décision « réutiliser ou recoder » se prend ici, pas au clavier.
   - **Socle affiché, jamais cité (BLOCKING — Jay 2026-08-30)** : §3bis IMPRIME chaque ligne du socle et demande un état sur chacune. Un renvoi vers la règle produit un oubli silencieux ; une liste visible produit soit une coche, soit une justification écrite. On n'écarte pas ce qu'on n'a pas sous les yeux.
   - **Deviations**: any deviation from the Universal Project Checklist (`.claude/rules/03-Qualite.md`) MUST be documented with explicit justification in the CDC (§3bis, §10 ou §13). No silent omissions.
   - **Path reminder**: at the start AND at the end of step 6, state explicitly: "CDC écrit dans `docs/CDC.md` (repo projet)." Per `.claude/rules/02-Parcours.md` décision 2026-06-27 : CDC/PET → repo projet `docs/`.

6bis. **PROTOTYPE / MOCK-UP** (BLOCKING): maquette HTML cliquable dans `docs/`, validée par Jay **avant le PET** (le modèle d'interaction naît dans la maquette). 9 règles : écrans clés, charte, responsive, rôles, briques réelles, bandeau de démonstration, libre arbitre, vues servies, vérification navigateur.

   **Lire `maquette.md` avant de commencer cette étape** — les règles y sont, elles s'appliquent toutes.

6ter. **INTÉGRATION** (BLOCKING): avant le PET, remplir PET §0 : ce que ça change pour qui utilise déjà, parcours complet, 13 dépendances jamais citées, phases implicites, ce qu'on a découvert. Une §0 incomplète bloque la feuille de route.

   **Lire `integration.md` avant de commencer cette étape** — les règles y sont, elles s'appliquent toutes.

7. **PET** (BLOCKING): écrire `docs/PET.md` (journal vivant de l'exécution), précédé de sa traduction en clair (étape 0bis). §0 et §1 à 9 obligatoires dès la création, sinon on ne passe pas à l'étape 8.

   **Lire `pet.md` avant de commencer cette étape** — les règles y sont, elles s'appliquent toutes.


8. **VERIFY** (BLOCKING): Cross-check CDC + PET before presenting:
   - [ ] CDC and PET are at `docs/CDC.md` and `docs/PET.md` in the project repo
   - [ ] CDC §5 has veille dates for every stack row
   - [ ] CDC §7 Risk Classification covers every module
   - [ ] CDC §8 FMEA exists for every Critical module
   - [ ] CDC §9 Human Quality Gates filled (or N/A justified for non-public projects)
   - [ ] PET §3 traceability matrix links every CDC §3 feature to bricks
   - [ ] PET §0 Intégration complete (5 blocks, no empty cell — « sans objet » is a valid answer, an empty cell is not)
   - [ ] PET §6 Roadmap is populated (even if all Pending), with `Briques réutilisées` filled on every brick that draws an interface
   - [ ] CDC §3bis Socle minimal: every line carries a state
   - [ ] CDC §3 `Briques réutilisées` read from the GENERATED inventory, never from prose
   - [ ] Cross-check against `.claude/rules/03-Qualite.md` (Quality Pyramid V2, anti-circular protocol, risk classification, 5 metrics)
   - [ ] Cross-check against `.claude/rules/08-Ecriture.md` (4 human gates, HECQ, ND-friendly design) — N/A only if project is explicitly non-public AND non-user-facing
   - [ ] Cross-check against `.claude/rules/03-Qualite.md` — QE V2, 25 décisions (archive d'origine : `docs/Archives/Mnk/improvements/004-QE-V2-Composition-Brief.md`)
   - If any gap found: fix CDC or PET, then re-verify. Do not proceed with gaps.

9. **PRESENT** (BLOCKING): diaporama HTML partageable à n'importe qui : langage non technique, bénéfices, format slides, charte de la maquette, vrais écrans, finir sur la maquette. Test : quelqu'un qui ne connaît rien au projet comprend-il et a-t-il envie ?

   **Lire `presentation.md` avant de commencer cette étape** — les règles y sont, elles s'appliquent toutes.


10. **SHINZO SYNC**: Create `[SHINZO]/02-Projets/[project].md` with sections: Notes, Décisions, Bugs, Prochaines étapes, Connexions. Add an entry to `[SHINZO]/02-Projets/_Index.md`. Reference `docs/CDC.md` + `docs/PET.md`. Commit + push Shinzo. `[SHINZO]` = `D:/30-Dev-Projects/Shinzo` (local) · `~/Shinzo` (VPS).

11. **VALIDATE**: Wait for Jay's explicit approval before ANY coding.

## Questionnaire (6 questions for Jay — asked ONE AT A TIME in step 1 bis)

1. What is this project? (describe like telling a friend)
2. Who is it for? (you / family / public / clients)
3. What does the user see? (website / phone app / bot / desktop / terminal)
4. Do people create accounts? (yes/no)
5. Do people pay for it? (yes/no)
6. Anything special? (coaching / gaming / AI / voice / streaming / ND-friendly)

**Asking protocol** : ask question 1, STOP, wait for written answer, acknowledge, then ask question 2, STOP, wait, etc. NEVER batch the 6 questions in one block. After the 6th answer, recap Jay's choices and STOP for explicit "ok / go / validé" before continuing to step 2 (SKB).

After Jay validates the recap, suggest ALL technical choices. Jay validates.

## Rules

- **Traduction simple avant chaque STOP technique (BLOCKING — step 0bis).** Jay est coach, pas développeur : toute section technique (Architecture, Stack, Risk, FMEA, Quality Gates, PET) est précédée de 2-3 lignes en clair (« En clair » + « Pourquoi ça compte pour toi ») AVANT toute demande de validation. Jay ne valide jamais ce qu'il n'a pas compris.
- **2 documents, jamais 3.** Pas de `Blueprint.md` projet. Les archétypes restent dans `.claude/rules/02-Parcours.md` comme références.
- **CDC = intention** : modifié uniquement quand l'intention change.
- **PET = exécution** : modifié à chaque brick (avant + après).
- **Cross-référence asymétrique** : PET référence CDC. CDC ne référence PAS le PET (l'intention est stable, n'a pas besoin de connaître l'exécution).
- **Order (changed 2026-08-30)**: CDC -> mock-up -> INTEGRATION -> PET -> Verify -> presentation. The mock-up now comes BEFORE the PET: the interaction model is born in the mock-up, and planning the execution of screens nobody has seen is what made the PET blind to it.
- **Mock-up = charte graphique de référence** : la présentation (slides) et le dev réutilisent son design system. Cohérence présentation ↔ prototype ↔ écran final.
- **Présentation = slides, jamais un one-pager à scroller.** Public non-tech, charte de la plateforme.
- Everything is potentially sellable — visibility-first (CDC §12).
- Non-tech agents intervene BEFORE coding decisions (step 5), not during.
- **Lego décidé à la conception, jamais au clavier (BLOCKING — 2026-08-30)** : chaque feature du CDC et chaque brique du PET nomme ce qu'elle réutilise, lu dans l'inventaire GÉNÉRÉ (`Kata/.claude/hooks/lego/ui-inventory.json`). « À créer dans la bibliothèque » est une réponse ; « composant local » n'en est pas une. Mesure : 146 fichiers du workspace recodent un composant déjà fourni.
- **Le socle est imprimé, jamais cité (BLOCKING — 2026-08-30)** : les lignes vivent dans le CDC avec un état chacune. On n'écarte pas ce qu'on n'a pas sous les yeux.
- **§0 Intégration précède la feuille de route (BLOCKING — 2026-08-30)** : une conversation de conception produit une liste de souhaits, pas une architecture. Ce qui n'a pas été dit à voix haute n'existait nulle part, et se découvrait au clavier. Une §0 vide dans « ce qu'on a découvert » signale que le recul n'a pas été pris.
- QE V2 is the floor — never produce a CDC/PET without the mandatory sections.
- Human Quality Gates apply to ALL public-facing projects. Non-public projects may mark them N/A with justification.

See `.claude/rules/02-Parcours.md` for full workflow details.

## End of the brick — the three proofs (recette)

Never declare work finished on "tests pass". The three proofs are **written before coding** and
checked at the end:

| Proof | The question | Who judges |
|---|---|---|
| **Visible** | does it look like the mockup, on screen? | Jay |
| **Proven** | which command, and which output, prove it works? | the independent review |
| **Experienced** | does it hold live, end to end? | Jay |

A brick without these three has a stop, not an end.
Source: `docs/Doctrine-2026-10-25.md` § 3.
