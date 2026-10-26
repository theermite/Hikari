# Étape 7 — le PET

> Lu par `/concevoir` au moment de l'étape concernée. Les règles ci-dessous sont BLOCKING comme si elles étaient dans `SKILL.md`.

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
