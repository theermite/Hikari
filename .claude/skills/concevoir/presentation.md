# Étape 9 — la présentation

> Lu par `/concevoir` au moment de l'étape concernée. Les règles ci-dessous sont BLOCKING comme si elles étaient dans `SKILL.md`.

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

   **4 règles de plus, format standard depuis le dojo** (Jay 2026-10-12 : « faire des présentations en intégrant les écrans de la maquette, avec une redirection finale vers la maquette, est excellent ») — référence : `Michi-Shinkofa/docs/Dojo/Presentation-Dojo.html` :
   | # | Règle | Pourquoi |
   |---|-------|----------|
   | 7 | **Les vrais écrans de la maquette** : captures prises par script (bandeau de démonstration masqué), recadrées sur la partie utile, dans un cadre de navigateur ou de téléphone ; un bénéfice = une diapo = ses écrans ; clic pour agrandir en plein écran | Le lecteur se projette dans la plateforme réelle au lieu d'imaginer |
   | 8 | **Montrer l'adaptation par comparaison** : le même écran sous deux profils, côte à côte, en pleine largeur sous le texte ; des vues téléphone | La différence se voit d'un coup d'œil, sans explication |
   | 9 | **De la vie** : une icône par diapo et par point de liste, un emoji discret en filigrane, apparition douce du contenu (coupée si l'appareil demande moins d'animations) | Jay 2026-10-12 : « il manque un peu de vie » sur la première version |
   | 10 | **Finir sur la maquette** : bouton « 👉 Explorer la maquette » sur la dernière diapo, plus la mention d'origine (`Content-Provenance.md`) | La présentation donne envie, la maquette fait toucher |

   **Diapos du pitch** (une slide chacune, mapping depuis les docs) :
   - Hero : nom + promesse en une ligne (depuis CDC §1 POUR QUOI, traduit non-tech)
   - Pourquoi / le besoin : le problème vécu par la personne (depuis CDC §2 Utilisateurs)
   - Ce que ça change : 3-6 bénéfices concrets (depuis CDC §3 Features, traduit en bénéfices)
   - Comment ça marche : 3 étapes intuitives
   - La vision : la phrase L3 motivante (depuis CDC §1)
   - La suite : roadmap en GRANDES étapes non-tech (depuis PET §6, traduit — pas de "bricks")
   - Entre « Ce que ça change » et « La vision » : une diapo illustrée par écran clé de la maquette (découvrir, adaptation par comparaison, composer son écran, usage mobile, pratique, fin de parcours, chaque rôle) — 12 à 16 diapos au total

   **Test avant de présenter** : « Si je partage ce fichier à quelqu'un qui ne connaît rien au projet ni à la tech, est-ce qu'il comprend et a envie ? » Si non → reformuler en plus simple, plus visuel.
