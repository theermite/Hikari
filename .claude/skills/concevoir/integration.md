# Étape 6ter — l'intégration (PET §0)

> Lu par `/concevoir` au moment de l'étape concernée. Les règles ci-dessous sont BLOCKING comme si elles étaient dans `SKILL.md`.

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
