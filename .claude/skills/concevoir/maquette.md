# Étape 6bis — la maquette

> Lu par `/concevoir` au moment de l'étape concernée. Les règles ci-dessous sont BLOCKING comme si elles étaient dans `SKILL.md`.

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

   **4 règles de plus, format standard depuis le dojo** (Jay 2026-10-12 : « on garde ce fonctionnement pour les maquettes ») — référence : `Michi-Shinkofa/docs/Maquettes/Dojo/` :
   | # | Règle | Pourquoi |
   |---|-------|----------|
   | 6 | **Bandeau de démonstration** (hors produit, en pointillé) : qui regarde (chaque rôle), profil simulé (chaque profil d'adaptation, jamais affiché au produit), états simulés (nouvel utilisateur, rien à faire, hors ligne, accès expiré, paiement refusé) | Jay voit en un clic la même plateforme vécue par chacun, et les chemins d'échec, pas seulement le chemin heureux |
   | 7 | **Libre arbitre et sobriété de navigation** : surfaces riches en grille composable (déplacer, agrandir, masquer, ajouter, « revenir à la proposition ») ; 5 choix de menu au plus par rôle, sous-menus au-delà | Mémoires `interface-composable-libre-arbitre` et `menus-cinq-choix-max-sous-menus` |
   | 8 | **Vues séparées, servies** : coquille + `vues/*.html` chargées par script (chaque fichier < 500 lignes), servie sur le serveur de maquettes (`:8446`), fichiers versionnés (`?v=`) | Une maquette d'un seul bloc dépasse vite la taille autorisée ; le serveur n'envoie aucune consigne de cache |
   | 9 | **Vérification navigateur scriptée avant de présenter** : tous les écrans × tous les rôles × ordinateur et téléphone — zéro erreur de console, zéro débordement, zéro écran vide, menus comptés, chaque lien mène à un écran et chaque écran est atteignable | Une maquette affirmée « testée » sans mesure se découvre cassée devant Jay |

   **Itérer avec Jay** jusqu'à validation du visuel et de l'ergonomie. Commit seulement à l'approbation.
