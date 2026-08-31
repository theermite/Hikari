---
name: concevoir
description: Full project conception workflow. POUR QUOI, research, CDC, PET, mockup prototype, slide presentation. Architecture 2 documents (CDC + PET).
model: opus
---

# /concevoir — Design a Project or Feature

Execute these steps IN ORDER. No skipping. Wait for Jay's validation at the final step.

> **Architecture documents** (depuis v2.0.0) : 2 documents, jamais 3.
> - `docs/CDC.md` = **intention** (template `templates/docs-structure/CDC.md`)
> - `docs/PET.md` = **exécution** (template `templates/docs-structure/PET.md`)
> - Plus de `Blueprint.md` projet. Les **archétypes** (Frontend-UI, Backend-API, etc.) sont des références dans `mnk/10-Blueprints.md`, pas des documents projet.

## Steps

0. **ANNOUNCE OUTPUTS**: At the very start, state explicitly to Jay the two files that will be produced and their exact paths:
   - CDC : `docs/CDC.md` (in project repo — intention figée)
   - PET : `docs/PET.md` (in project repo — exécution vivante)
   - Workflow has STOP points at each questionnaire answer and each CDC section. Confirm Jay knows where each artifact lands BEFORE step 1.

0bis. **TRADUCTION SIMPLE (BLOCKING — governs every technical STOP below)**: before EVERY validation STOP on a technical section (CDC §4 Architecture, §5 Stack, §6 Non-functional, §7 Risk Classification, §8 FMEA, §9 Human Quality Gates ; every PET section), precede the draft with 2-3 lines of plain French — no jargon:
   - « **En clair** : <what this section means, said as to a friend, zero technical term> »
   - « **Pourquoi ça compte pour toi** : <the concrete stake for Jay or the end-user> »
   Jay is a coach, not a developer — he never validates a section he has not had translated first. A technical STOP presented WITHOUT its plain-language translation is BLOCKING: do not ask for validation until it is there. This applies the cardinal principle's language corollary (`mnk/00-Philosophy.md`) to conception. Non-technical sections (POUR QUOI, Utilisateurs, Hors scope) need no translation — they are already plain.

1. **ARCHETYPE DETECT**: Identify project archetype from signals (see `mnk/10-Blueprints.md`). This is a reference lookup, NOT a document to produce.

1bis. **QUESTIONNAIRE (BLOCKING — interactive)**: Ask Jay the 6 questions from the Questionnaire section below, ONE AT A TIME. After each question:
   - STOP.
   - Wait for Jay's written answer (approval words from Interpretation-Protocol do NOT apply here — wait for substantive content).
   - Acknowledge the answer, then proceed to the next question.
   - Do NOT batch the 6 questions in one block. Do NOT infer answers from context. Do NOT proceed without all 6 answers in writing.
   - After the 6th answer, summarize Jay's choices in a compact recap, then STOP and wait for "ok / go / validé" before continuing to step 2.

2. **SKB (our brain)**: Search SKB (Shinkofa Knowledge Base) for ALL relevant domains — vision (MasterPlan), coaching, neurodiversity, marketing, gaming. Not just technical knowledge. SKB IS our collective brain.
3. **POUR QUOI (3 Layers)**: Define the WHY through all 3 layers: L3 — Does this serve Shinkofa's vision (invisible ecosystem respecting individuality)? L2 — How will this be PRESENTED to create magnetic visibility? L1 — What's the first step given current energy? All 3 must be documented. They land in CDC §1.
4. **RESEARCH + VEILLE**: Search in 7 languages (EN, FR, ZH, JA, KO, DE, RU). State-of-art < 14 days. When evaluating architecture: consider the tri-layer direction (TypeScript visible + Elixir/Phoenix backend + Rust critical modules) as validated direction, POC pending. **CRITICAL**: Verify ALL technology recommendations, architecture patterns, and best practices via web. Training data is months stale. Veille dates land in `docs/CDC.md` §5 (Stack technique).
5. **NON-TECH AGENTS (PREPARE)**: Invoke UX, Brand, Pedagogy, Content, Gaming agents to review the concept BEFORE coding decisions.

6. **CDC** (BLOCKING — interactive, section by section): Write the CDC at `docs/CDC.md` in the project repo. Use template `templates/docs-structure/CDC.md` v2.0.0. The CDC is built **one section at a time, with a STOP between each** — never as a 13-section monologue. After EACH section below: present the draft to Jay — for a technical section, **preceded by its plain-language translation (step 0bis, BLOCKING)** — STOP, wait for "ok / go / validé" or for substantive correction. Only then proceed to the next section.

   | Order | Section | STOP after? |
   |-------|---------|-------------|
   | 6.1 | §1 POUR QUOI (L3/L2/L1) | Yes |
   | 6.2 | §2 Utilisateurs cibles (with ND personas if public) | Yes |
   | 6.3 | §3 Features (with IDs F-XXX **and the `Briques réutilisées` column filled**) | Yes |
   | 6.3bis | §3bis **Socle minimal** (BLOCKING — the 15 lines PRINTED, each with ✅ / ⛔+raison / ❓) | Yes |
   | 6.4 | §4 Architecture | Yes |
   | 6.5 | §5 Stack technique (with **veille date** per ligne — BLOCKING) | Yes |
   | 6.6 | §6 Non-functional requirements | Yes |
   | 6.7 | §7 **Risk Classification** (BLOCKING — Critical/Sensitive/Standard/Tooling per `mnk/06-Quality.md`) | Yes |
   | 6.8 | §8 **FMEA simplifiée** (BLOCKING on Critical modules — 3 failure modes each) | Yes |
   | 6.9 | §9 **Human Quality Gates** (BLOCKING on public-facing projects — Cognitive Load, Sensory Comfort, Error Resilience, Adaptation, Dignity + Feedback Widget) | Yes |
   | 6.10 | §10 Hors scope explicite | Yes |
   | 6.11 | §11 Success metrics | Yes |
   | 6.12 | §12 Visibilité (Big 5, SEO, GEO, Distribution, Capture) | Yes |
   | 6.13 | §13 Anti-patterns projet | Yes |

   - **Dignity gate** : tout écran de collecte, copy, CTA, message d'erreur passe le test `rules/Dignity.md`. Documenté dans §9.
   - **Lego d'abord, à la conception (BLOCKING — Jay 2026-08-30)** : avant d'écrire §3, LIRE l'inventaire généré `Kata/.claude/hooks/lego/ui-inventory.json` (jamais un chiffre de mémoire, jamais la prose d'une règle). Chaque feature nomme les briques qu'elle réutilise, ou écrit « à créer dans la bibliothèque » — jamais « composant local ». **Pourquoi** : mesure du 2026-08-30, 146 fichiers du workspace recodent un composant déjà fourni, et l'inventaire écrit à la main annonçait 79 composants sur 149 réels. La décision « réutiliser ou recoder » se prend ici, pas au clavier.
   - **Socle affiché, jamais cité (BLOCKING — Jay 2026-08-30)** : §3bis IMPRIME les 15 lignes du socle et demande un état sur chacune. Un renvoi vers la règle produit un oubli silencieux ; une liste visible produit soit une coche, soit une justification écrite. On n'écarte pas ce qu'on n'a pas sous les yeux.
   - **Deviations**: any deviation from the Universal Project Checklist (`rules/Quality.md`) MUST be documented with explicit justification in the CDC (§3bis, §10 ou §13). No silent omissions.
   - **Path reminder**: at the start AND at the end of step 6, state explicitly: "CDC écrit dans `docs/CDC.md` (repo projet)." Per `rules/Workflows.md` décision 2026-06-27 : CDC/PET → repo projet `docs/`.

6bis. **PROTOTYPE / MOCK-UP** (BLOCKING — **avant le PET depuis 2026-08-30**): Generate a standalone clickable HTML mockup in `docs/` (ex: `docs/Mockups-<Projet>.html`) — a navigable prototype of the platform's key screens. Jay validates ergonomics, navigation and visual identity BEFORE the execution plan and before any code.

   **Pourquoi la maquette passe AVANT le plan** (Jay 2026-08-30) : le modèle d'interaction naît dans la maquette. Tant qu'elle n'existe pas, on planifie l'exécution d'écrans que personne n'a vus — et le plan ignore alors ce qui compte le plus pour l'utilisateur. Jay : « ils ne prennent pas en compte le modèle d'interaction ». La maquette devient une ENTRÉE du plan, plus un après-coup.

   **5 règles BLOCKING du mock-up** :
   | # | Règle | Pourquoi |
   |---|-------|----------|
   | 1 | **Écrans clés depuis CDC §3** | Dashboard + surfaces principales. Une seule navigation, chaque écran réaliste avec données **fictives (ZÉRO donnée personnelle)**. |
   | 2 | **Charte graphique de la plateforme** | Thème sombre, **plat/moderne (zéro relief 3D ni dégradé façon bouton)**, couleurs d'accent, avatar/marque en illustration. Cette charte devient la référence pour la présentation ET le dev. |
   | 3 | **Responsive réel** | Desktop **pleine largeur** (contenu non-boxé) + mobile/tablette (menu hamburger). Tester les deux. |
   | 4 | **Adaptatif au rôle** | Sections liées à un rôle **cachées** sans le rôle (jamais de mur « pas membre »). |
   | 5 | **Briques réelles, jamais redessinées** | Tout réglage de confort (thème, mouvement, densité, police, daltonisme) est dessiné par `MorphicButton` de `@theermite/morphic-adapter` — chargé par CDN dans une maquette statique. Les autres éléments citent la brique `@shinkofa/ui` correspondante. Un panneau refait à la main est **bloqué à l'écriture** par `hooks/lego/morphic-decoy-check.py`. Audit 2026-08-30 : 4 dépôts avaient dessiné un faux panneau, dont un bouton « Contraste » décoratif signalé comme un bug du vrai module. |

   **Itérer avec Jay** jusqu'à validation du visuel et de l'ergonomie. Commit seulement à l'approbation.

6ter. **INTÉGRATION** (BLOCKING — **nouvelle étape 2026-08-30**): Before writing the PET, step back and fill PET §0 — how this lands in what already exists. Present each block to Jay, plain language first (step 0bis applies), then STOP.

   **Pourquoi cette étape existe** (Jay 2026-08-30) : « le cahier des charges et le plan ne prennent en compte que ce qui a été vu pendant la conception. Ils ne prennent pas de recul pour regarder réellement comment intégrer l'idée dans la plateforme, en prenant en compte le modèle d'interaction, et toutes les dépendances et phases de développement qui ne sont peut-être pas citées. » Une conversation de conception produit une liste de souhaits, jamais une architecture. **Ce qui n'a pas été dit à voix haute n'existait nulle part** — et se découvrait au clavier, trop tard.

   | § | Bloc | Ce qu'il force |
   |---|------|----------------|
   | 0.1 | Ce que ça change pour qui utilise déjà | L'utilisateur existant n'a rien demandé. Que voit-il changer, que casse-t-on, doit-il réapprendre ? |
   | 0.2 | Modèle d'interaction — parcours complet | Écran par écran depuis la maquette validée, y compris AVANT (comment il arrive) et APRÈS (où il repart). Chemin d'échec décrit autant que le chemin heureux ; 3 états sur tout écran alimenté par le serveur. |
   | 0.3 | Dépendances jamais citées | 13 lignes passées une par une (auth, migration, reprise de données, i18n, morphique, Lego, envois, paiement, clés, ports, sauvegarde, erreurs prod, RGPD). « Sans objet » est valable ; une case vide ne l'est pas. |
   | 0.4 | Phases implicites | Reprise de données, rétro-compatibilité, déploiement progressif, retour arrière, doc, vérification post-livraison, projets voisins impactés. Chacune devient une brique ou est écartée avec sa raison. |
   | 0.5 | Ce qu'on a découvert ici | Liste franche. **Une liste vide signale que le recul n'a pas été pris** — sur un projet réel elle ne l'est jamais. |

   Une section §0 incomplète est BLOCKING : ne pas écrire la feuille de route tant qu'elle n'est pas remplie et validée.

7. **PET** (BLOCKING): Write the PET at `docs/PET.md` in the project repo. Use template `templates/docs-structure/PET.md` v2.0.0. State the path explicitly to Jay before writing — the PET is highly technical, so **precede it with its plain-language translation (step 0bis, BLOCKING)**: in 2-3 lines, what the PET is for Jay (« le carnet de bord vivant de l'exécution ») and why it matters, before showing the sections. The PET is the **living execution journal**. It MUST contain ALL of the following sections at creation, then be updated at every brick:

   | # | Section | Content |
   |---|---------|---------|
   | 0 | **Intégration (BLOCKING)** | Rempli à l'étape INTÉGRATION : ce que ça change pour l'utilisateur existant · le parcours complet depuis la maquette · les 13 dépendances jamais citées · les phases implicites · ce qu'on a découvert. Une §0 incomplète bloque la feuille de route. |
   | 1 | Principe d'exécution | Brick-by-brick, TDG, backup cadence (tag every 3-4 commits), trace continue |
   | 2 | Anti-Circular Testing Protocol | 3 layers (PBT + Writer/Reviewer + cross-model) |
   | 3 | Bidirectional Traceability | CDC requirement → bricks → tests |
   | 4 | 5 Test Reliability Metrics | Targets per metric |
   | 5 | Defensive Assertions | List of critical functions + >= 2 assertions each |
   | 6 | **Roadmap (Bricks)** | Live table — UPDATED AT EVERY BRICK. Colonne **Briques réutilisées** obligatoire : une case vide bloque le démarrage de la brique. |
   | 7 | **Détail par brick** | Per brick: scope, veille préalable, TDG tests, impact analysis, implémentation, **tests post (preuves)**, **erreurs rencontrées**, décisions in-flight, commit SHA |
   | 8 | PII Detection | Configuration: tools, scope, automated vs manual |
   | 9 | Quality Gates pré-commit | Checklist per brick (coverage, lint, tests, security, a11y, cross-browser, veille, confidentiality) |
   | 10 | Post-Deploy Verification | Health checks, smoke tests, feedback widget verification |
   | 11 | Risques rencontrés en exécution | Different from CDC FMEA — risks DISCOVERED during work |
   | 12 | Décisions architecturales (ADR-light) | In-flight decisions not in CDC |
   | 13 | Déviations vs CDC | Tracked here; if permanent → update CDC |
   | 14 | Journal de session | References to session reports |

   A PET missing §0 or any of sections 1-9 at creation is BLOCKING — do not proceed to step 8.

8. **VERIFY** (BLOCKING): Cross-check CDC + PET before presenting:
   - [ ] CDC and PET are at `docs/CDC.md` and `docs/PET.md` in the project repo
   - [ ] CDC §5 has veille dates for every stack row
   - [ ] CDC §7 Risk Classification covers every module
   - [ ] CDC §8 FMEA exists for every Critical module
   - [ ] CDC §9 Human Quality Gates filled (or N/A justified for non-public projects)
   - [ ] PET §3 traceability matrix links every CDC §3 feature to bricks
   - [ ] PET §0 Intégration complete (5 blocks, no empty cell — « sans objet » is a valid answer, an empty cell is not)
   - [ ] PET §6 Roadmap is populated (even if all Pending), with `Briques réutilisées` filled on every brick that draws an interface
   - [ ] CDC §3bis Socle minimal: every one of the 15 lines carries a state
   - [ ] CDC §3 `Briques réutilisées` read from the GENERATED inventory, never from prose
   - [ ] Cross-check against `mnk/06-Quality.md` (Quality Pyramid V2, anti-circular protocol, risk classification, 5 metrics)
   - [ ] Cross-check against `mnk/15-Human-Quality.md` (4 human gates, HECQ, ND-friendly design) — N/A only if project is explicitly non-public AND non-user-facing
   - [ ] Cross-check against `mnk/improvements/004-QE-V2-Composition-Brief.md` (25 decisions)
   - If any gap found: fix CDC or PET, then re-verify. Do not proceed with gaps.

9. **PRESENT** (BLOCKING): Generate a standalone HTML **slide deck** in `docs/` (ex: `docs/Presentation-<Projet>.html`). This presentation is a **magnetic pitch shareable to ANYONE** — not an internal tech sheet. The reader (non-technical) must UNDERSTAND the project AND want to adhere to it.

   **Base obligatoire** : réutiliser la **charte graphique du mock-up** — même palette, même thème, même avatar/marque. Cohérence totale entre présentation, mock-up et écran final. (Le template `.claude/skills/concevoir/presentation-template.html` sert de squelette de secours si aucun mock-up n'existe.)

   **6 règles BLOCKING du rendu** :
   | # | Règle | Pourquoi |
   |---|-------|----------|
   | 1 | **Langage 100% non-tech** | Partageable à n'importe qui. Zéro jargon, zéro nom de stack, zéro fonction. Terme technique inévitable = glosé en parenthèse simple. |
   | 2 | **Bénéfices, pas features** | On dit ce que ça CHANGE pour la personne, pas comment c'est codé. |
   | 3 | **Format SLIDES** | Une diapo plein écran à la fois (clavier ←/→, points de navigation, swipe mobile). JAMAIS un one-pager à scroller. |
   | 4 | **Charte graphique de la plateforme** | Réutilise le design system du mock-up (thème sombre, couleurs d'accent, avatar/marque). Cohérence avec l'écran final. |
   | 5 | **Visuel, intuitif** | Hero, cartes, étapes numérotées, compteur de diapos, barre de progression. Le lecteur scanne. |
   | 6 | **Le tech interne reste dans CDC/PET** | Risk Classification, FMEA, stack, Quality Gates → JAMAIS dans la présentation. Ils vivent dans le CDC/PET. |

   **Diapos du pitch** (une slide chacune, mapping depuis les docs) :
   - Hero : nom + promesse en une ligne (depuis CDC §1 POUR QUOI, traduit non-tech)
   - Pourquoi / le besoin : le problème vécu par la personne (depuis CDC §2 Utilisateurs)
   - Ce que ça change : 3-6 bénéfices concrets (depuis CDC §3 Features, traduit en bénéfices)
   - Comment ça marche : 3 étapes intuitives
   - La vision : la phrase L3 motivante (depuis CDC §1)
   - La suite : roadmap en GRANDES étapes non-tech (depuis PET §6, traduit — pas de "bricks")

   **Test avant de présenter** : « Si je partage ce fichier à quelqu'un qui ne connaît rien au projet ni à la tech, est-ce qu'il comprend et a envie ? » Si non → reformuler en plus simple, plus visuel.

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
- **2 documents, jamais 3.** Pas de `Blueprint.md` projet. Les archétypes restent dans `mnk/10-Blueprints.md` comme références.
- **CDC = intention** : modifié uniquement quand l'intention change.
- **PET = exécution** : modifié à chaque brick (avant + après).
- **Cross-référence asymétrique** : PET référence CDC. CDC ne référence PAS le PET (l'intention est stable, n'a pas besoin de connaître l'exécution).
- **Order (changed 2026-08-30)**: CDC -> mock-up -> INTEGRATION -> PET -> Verify -> presentation. The mock-up now comes BEFORE the PET: the interaction model is born in the mock-up, and planning the execution of screens nobody has seen is what made the PET blind to it.
- **Mock-up = charte graphique de référence** : la présentation (slides) et le dev réutilisent son design system. Cohérence présentation ↔ prototype ↔ écran final.
- **Présentation = slides, jamais un one-pager à scroller.** Public non-tech, charte de la plateforme.
- Everything is potentially sellable — visibility-first (CDC §12).
- Non-tech agents intervene BEFORE coding decisions (step 5), not during.
- **Lego décidé à la conception, jamais au clavier (BLOCKING — 2026-08-30)** : chaque feature du CDC et chaque brique du PET nomme ce qu'elle réutilise, lu dans l'inventaire GÉNÉRÉ (`Kata/.claude/hooks/lego/ui-inventory.json`). « À créer dans la bibliothèque » est une réponse ; « composant local » n'en est pas une. Mesure : 146 fichiers du workspace recodent un composant déjà fourni.
- **Le socle est imprimé, jamais cité (BLOCKING — 2026-08-30)** : les 15 lignes vivent dans le CDC avec un état chacune. On n'écarte pas ce qu'on n'a pas sous les yeux.
- **§0 Intégration précède la feuille de route (BLOCKING — 2026-08-30)** : une conversation de conception produit une liste de souhaits, pas une architecture. Ce qui n'a pas été dit à voix haute n'existait nulle part, et se découvrait au clavier. Une §0 vide dans « ce qu'on a découvert » signale que le recul n'a pas été pris.
- QE V2 is the floor — never produce a CDC/PET without the mandatory sections.
- Human Quality Gates apply to ALL public-facing projects. Non-public projects may mark them N/A with justification.

See `mnk/05-Workflows-Concevoir.md` for full workflow details.
