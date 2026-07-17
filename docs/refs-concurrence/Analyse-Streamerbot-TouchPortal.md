---
title: Analyse concurrence — Streamer.bot & TouchPortal
created: 2026-07-16
updated: 2026-07-16
status: validated
type: reference
version: 1.0.0
project: Hikari Stream
---

# Analyse concurrence — Streamer.bot & TouchPortal

> **À quoi sert ce document.** Hikari Stream remplace la paire Streamer.bot + deck. Ce document
> établit **comment ces outils fonctionnent réellement**, ce qu'il faut leur reprendre, et où ils
> échouent. Il ne sert pas à les copier : il sert à **prendre ce qui est bon et refaire mieux,
> plus simple, plus ergonomique, plus accessible** (cadrage Jay, 2026-07-16).
>
> **Trois sources, de force inégale** :
> 1. 🟢 **Rétro-ingénierie du fichier de données réel** — `actions.json` d'une installation en
>    production (83 actions). C'est la preuve la plus dure : le modèle de données, pas le discours.
> 2. 🟢 **Captures de l'application réelle** en usage — l'ergonomie telle qu'elle est vécue.
> 3. 🟠 **Recherche web datée du 2026-07-16** — documentation officielle + terrain (2 passes).
>
> **Confidentialité** : aucune donnée personnelle issue de l'installation analysée n'est reproduite
> ici (pseudo de chaîne, jetons, données de viewers). Seules les **structures** sont documentées.

---

## 1. Le modèle de données réel (rétro-ingénierie)

**Preuve dure.** Le fichier `actions.json` de Streamer.bot stocke une automation ainsi :

```
action = {
  id, name, group, queue,
  enabled, alwaysRun, randomAction, concurrent,
  triggers:    [ { id, type, eventName, enabled, exclusions } ],
  subActions:  [ { id, type, index, parentId, subActions[], ...champs selon le type } ]
}
```

**Ce que ça prouve, et c'est le point central de ce document** :

| Constat | Conséquence pour Hikari |
|---|---|
| Une automation est une **donnée**, pas du code | ✅ Confirme **ADR-008** (PET). Notre pari n'en est pas un : c'est le modèle du leader. |
| Une sous-action peut **contenir des sous-actions** (`subActions[]` imbriqué) | C'est ainsi qu'un « Si » porte ses enfants. Le graphe est **connu d'avance** → cycles détectables à l'enregistrement (notre garde-fou, CDC §8). |
| Chaque sous-action a un **`type`** (entier) + des champs spécifiques | Un catalogue fermé de types = validation possible. Notre palette (CDC §3bis) suit la même logique. |
| Une action porte **plusieurs triggers** possibles | ✅ Confirme le modèle « le déclencheur est un attribut, pas une nature ». |

**Le triptyque, vérifié des deux côtés (données + documentation)** :

```
Trigger  (ce qui déclenche)  →  Action  (le conteneur)  →  Sub-Action  (la brique)
```

Correspondance avec notre vocabulaire (CDC §3bis, maquette) :

| Streamer.bot | Hikari | Pourquoi notre mot |
|---|---|---|
| Trigger | **Quand** | Le mot dit ce qu'il fait, sans jargon |
| Action | **Automation** | Ce que l'utilisateur nomme et manipule |
| Sub-Action | **une ligne du Alors** | Une étape lisible, numérotée |
| Condition (If/Else) | **Si** | — |

## 2. La réponse à « une automation peut-elle être un bouton de deck ? »

**Oui — et c'est structurel, pas cosmétique.** Les deux outils convergent :

- Chez Streamer.bot, **tout est un trigger**. Un clic de bouton, une commande de chat, un nouveau
  follower, un minuteur : même mécanisme. **L'action ignore qui l'a déclenchée** — elle lit
  seulement les variables que le trigger a déposées.
- Le deck n'appelle pas une logique : il envoie un message générique (« lance l'action X, avec ces
  arguments ») au serveur intégré. Le bouton est un **client parmi d'autres**.

**Règle qui en découle pour Hikari** :

| Déclencheur de l'automation | Apparaît sur le deck ? |
|---|---|
| Bouton (manuel) | **Oui** — le bouton EST le déclencheur |
| Commande de chat | Non — le viewer déclenche |
| Événement (follow, sub, raid) | Non — ça part seul |
| Minuteur | Non — le temps déclenche |

Conséquence d'architecture : **le moteur expose une interface stable** (« liste les automations »,
« lance celle-ci avec ces arguments », « préviens-moi des événements »). Le deck local et le deck
distant en sont deux clients. Zéro logique dupliquée. → à poser en ADR (voir §6).

## 3. Ce qui est BON — à reprendre

| Élément | Ce qu'ils réussissent | État chez nous |
|---|---|---|
| **La chaîne se lit** | Les sous-actions s'affichent en phrases (« Set Channel Tags », « Twitch Channel Title… ») | ✅ maquette Quand/Si/Alors |
| **Bouton = automation** | Un bouton lance une action, avec arguments propres | ⬜ à relier (B-auto ↔ B4) |
| **Bascule à état** | Les touches ON/OFF montrent leur état (micro, stream) | ✅ CDC §3bis (4 types de touches) |
| **Valeur live sur une touche** | Le compteur de viewers s'affiche sur un bouton | ✅ CDC §3bis |
| **Rangement par familles** | Actions groupées (Emotes, Scènes, Contrôle stream…) | ⬜ à prévoir |
| **Catalogue large** | ~350 déclencheurs, ~450 sous-actions | La puissance est un acquis à égaler, pas un différenciateur |

## 4. Ce qui est TROP COMPLEXE — à refaire mieux

**C'est ici que se joue le projet.** Le diagnostic de Jay (2026-07-16) : *« Le niveau de
personnalisation est excellent, mais la complexité est trop haute car il y a beaucoup trop de
liberté. […] Il aurait été possible d'offrir autant de liberté, mais avec une ergonomie beaucoup
plus intuitive pour des personnes qui ne sont ni dev ni tech. »*

| # | Problème observé | Preuve | Ce que Hikari fait à la place |
|---|---|---|---|
| 1 | **Ajouter une étape = fouiller** | Menu en cascade profond : `Add → OBS Studio → Sources → …` sur des centaines d'entrées | **Chercher, pas fouiller** : une barre « qu'est-ce que tu veux faire ? » en langage courant |
| 2 | **6 concepts avant d'agir** | Actions · Commands · Queues · Triggers · Sub-Actions · Global Variables | **Un seul objet visible** : l'automation (Quand/Si/Alors). Le reste est de la machinerie cachée |
| 3 | **Jargon d'ingénieur en façade** | Colonnes « GCD / UCD / Queue: Default / Options: None » | Vocabulaire humain. Aucun sigle non expliqué |
| 4 | **On part du vide** | Écran d'action neuve = liste vide + menus | **Recettes prêtes** (pause, clip, follower) qu'on adapte |
| 5 | **Aucun garde-fou anti-boucle** | Une action qui s'appelle elle-même fige la file. Bug historique attesté (changelog v0.2.4 : la file par défaut s'arrêtait de traiter sur erreur) | **Refus du cycle à l'enregistrement** + profondeur bornée + temps max par action (CDC §8) |
| 6 | **Windows seulement** | Application .NET/WPF | Tauri/Rust → Windows d'abord, Linux ensuite |
| 7 | **Courbe d'apprentissage** | Plainte n°1 des deux outils (recherche + vécu Jay) | Dignité : dévoilement progressif, jamais d'étiquette « débutant » |

## 4bis. La preuve chiffrée — et ce qu'elle coûte vraiment

**Mesure sur l'historique réel** de l'installation analysée (fichiers `actions.json` successifs) :

| Mesure | 12 juillet 2026 | 16 juillet 2026 |
|---|---|---|
| Étapes au total | **833** | 129 |
| Étapes par action (moyenne) | **8,6** | 1,6 |
| **L'action la plus lourde** | **104 étapes** | 5 |
| Actions à une seule étape | 30 % | 79 % |

> ⚠️ **Honnêteté de lecture (obligatoire)** : ce n'est **pas** « les mêmes actions ont maigri ».
> Entre les deux dates, 96 actions ont été supprimées et 82 créées — **une seule survit**. Le jeu a
> été **reconstruit**, pas allégé en place. Ce qui est **prouvé** : avant, les actions pesaient 8,6
> étapes en moyenne, jusqu'à **104 pour une seule**. Ce qui relève du **témoignage** (cohérent avec
> les sessions du 2026-07-10, macros Advanced Scene Switcher) : la raison de cette fonte.
>
> ⚠️ **Piège de mesure rencontré** : le schéma de données a changé (v15 → v23). L'ancien champ
> s'appelait `actions`, le nouveau `subActions`. Une première mesure a conclu « 0 étape » sur un
> fichier de 374 Ko — artefact, pas résultat. **Lire le schéma avant de compter.**

**Ce que la fonte cache réellement — le cœur du sujet.** Elle ne vient pas que d'une optimisation.
Elle vient d'un **renoncement**. Témoignage direct de Jay (2026-07-16), designer de métier :

> *« J'ai réellement allégé parce que je me suis séparé de certaines actions à cause du temps que
> ça coûtait de les recréer. […] Certaines actions de caméras qui clignotent ou se déplacent sur le
> rebord de l'écran, je n'ai pas pu les recréer : ça demande beaucoup trop de temps et beaucoup trop
> de sous-actions différentes. »*

**Le mécanisme exact du coût** — et c'est lui qu'Hikari doit tuer :

```
un effet cosmétique  =  N sous-actions dans Streamer.bot
                      + de la préparation dans OBS
                      = deux outils, travail multiplié
```

| Ce que ça produit | Conséquence |
|---|---|
| Un clignotement de caméra devient **inabordable** | L'idée est abandonnée |
| Même avec une IA en renfort, certains effets restent hors de portée | Le plafond n'est pas la compétence — c'est l'outil |
| Un designer de 23 ans de métier **sacrifie ses propres idées visuelles** | La complexité ne coûte pas du temps : elle **détruit l'intention créative** |

**La bonne métrique d'Hikari n'est donc pas « des étapes économisées »** :

| Métrique faible | Métrique juste |
|---|---|
| « 833 → 129 étapes » | **« Combien d'idées as-tu abandonnées ? »** Cible : zéro. |

**Pourquoi Hikari peut y arriver, structurellement** : une seule application qui **embarque le
moteur possède les deux côtés**. Ce qui exige « N sous-actions + réglages OBS » chez eux devient
**un geste natif** chez nous. Ce n'est pas une promesse d'ergonomie — c'est une conséquence de
l'architecture (CDC §4, F-001).

## 4ter. Le calvaire de configuration — le vrai marché

**Constat de Jay (2026-07-16)**, à traiter comme un pilier et non comme un détail de confort :

> *« La majeure partie des personnes n'utiliseront pas une IA comme je l'ai fait. Avec toutes les
> extensions, les plugins d'OBS plus Streamer.bot, c'est un calvaire tel que beaucoup de streamers
> ne le font pas ou rechignent à le faire : ce sont des heures et des heures cumulées juste pour une
> configuration de stream. »*

**Ce que ça change dans la lecture du projet** :

| Avant (lecture faible) | Après (lecture juste) |
|---|---|
| Hikari = « un moteur d'automations de plus » | Hikari = **la configuration cesse d'être une épreuve** |
| F-001 (installation unique) = confort | **Pilier** |
| F-002 (accueil guidé) = politesse | **Pilier** |

**Confirmation externe** — la veille SKB `Stream-Deck-OBS-Alternatives-Exhaustive-Veille.md`
(Eichi, 2026-07-10, déjà citée au CDC §5) établit dans sa *Gap Analysis* :
- « **No neurodiversity-friendly design.** Every stream deck software assumes neurotypical
  interaction patterns. »
- « **Adaptive interface** : no streaming software adapts its UI complexity to the user's skill
  level. Beginner mode vs. advanced mode is just surface-level. »

Le trou est donc constaté **de l'extérieur aussi**, pas seulement par notre vécu.

> **Réserve honnête** : Jay se souvient d'un « audit des douleurs des créateurs et streamers » où la
> simplicité de configuration ressortait. **Cet audit dédié n'a pas été retrouvé** dans le vault ni
> dans les docs projet (recherche du 2026-07-16). Le plus proche est la *Gap Analysis* ci-dessus.
> Le constat repose donc sur : vécu direct + terrain des deux outils + gaps de la veille — **pas**
> sur une étude quantitative dédiée. À produire si une décision lourde doit s'y appuyer.

## 5. TouchPortal — le deck, et le choix qu'il révèle

**Architecture** : desktop = serveur, mobile = client, dialogue en réseau local (sans cloud).
Extensible par greffons (fichier JSON + connexion locale, agnostique du langage).

**Le point de conception décisif** — TouchPortal permet **les deux modèles** :

| Modèle | Qui porte la logique | Limite constatée |
|---|---|---|
| Bouton **intelligent** (natif) | le bouton (conditions, boucles, délais) | Moteur bridé : pas de minuteur global, un « stop » qui n'arrête que le flux courant |
| Bouton **déclencheur** (avec Streamer.bot) | un moteur externe | Deux outils à installer, deux modèles mentaux |

**Ce que les pros font** : ils utilisent TouchPortal comme surface d'entrée et déportent
l'orchestration vers Streamer.bot. Autrement dit, **le marché a tranché : le bouton est un
déclencheur**. C'est le modèle qu'Hikari adopte — mais dans **une seule application**, pas deux.

**Repères chiffrés à battre** :

| Mesure | Eux | Cible Hikari |
|---|---|---|
| Latence deck distant — relevé sur **Streamer.bot Decks** en usage réel | **239 ms** | **< 100 ms en local** (CDC §6) |
| Nombre d'applications à installer | 2 (+ OBS = 3) | **1** (F-001) |

### 5bis. Quel deck sert de référence — et le vécu réel

> ⚠️ **Correction du 2026-07-16.** Une première version de ce document attribuait les captures de
> deck à TouchPortal. **C'est faux** : elles montrent **Streamer.bot Decks** (le deck web intégré à
> Streamer.bot). Le repère des 239 ms est donc **celui de Streamer.bot Decks**. TouchPortal est cité
> ici comme **référence du marché** du deck logiciel, pas comme l'outil observé en production.

**Historique des decks essayés par Jay** — il éclaire deux de ses quatre critères :

| Outil | Statut | Pourquoi il a été quitté | Critère touché |
|---|---|---|---|
| **Deckboard** | Utilisé longtemps, **abandonné par son auteur** | Plus maintenu → devenu inutilisable | **Constance** |
| **TouchPortal** | Installé et essayé | **Payant** pour le niveau de personnalisation nécessaire | Accessibilité |
| **Streamer.bot Decks** | En usage aujourd'hui | Faute de mieux (intégré à l'outil déjà là) | — |

**Enseignement (Monozukuri #6 — le long terme)** : Jay a **perdu un outil parce qu'il est mort**.
C'est l'argument de fond de l'open-source pour Hikari : un outil ouvert ne peut pas disparaître
sans son utilisateur. La « constance » n'est pas qu'une qualité d'exécution — c'est une propriété
du modèle de distribution.

## 6. Les 6 principes retenus pour Hikari

Ils traduisent les 4 critères de réussite fixés par Jay (intuitivité · prise en main · stabilité et
fiabilité · constance) en règles de conception opposables.

| # | Principe | Ce qu'il interdit |
|---|---|---|
| **P1** | **Le cas simple est trivial** — la chaîne Quand/Si/Alors se lit et s'écrit sans manuel | Interdit d'exiger un tutoriel pour un enchaînement de 2 étapes |
| **P2** | **Chercher, pas fouiller** — on décrit ce qu'on veut en langage courant | Interdit le menu en cascade comme chemin principal |
| **P3** | **Partir d'une recette, jamais du vide** | Interdit l'écran neuf vide comme seule porte d'entrée |
| **P4** | **La machinerie est cachée, pas absente** — files, temporisations, priorités : réglages sains par défaut, « avancé » repliable | Interdit d'exposer un réglage dont une seule valeur est correcte (Knob Footgun, Quality.md) |
| **P5** | **Deck et automations sont les mêmes objets** — un bouton est un déclencheur « manuel » | Interdit deux modèles séparés, donc deux logiques à maintenir |
| **P6** | **Un effet visuel est un geste, pas un montage** — Hikari embarque le moteur, donc il possède les deux côtés (§4bis) | Interdit qu'un effet cosmétique courant (clignoter, se déplacer, apparaître) coûte un assemblage manuel d'étapes |

**La mesure de réussite qui tranche** (issue du §4bis, décidée avec Jay le 2026-07-16) :

> **« Combien d'idées l'utilisateur a-t-il abandonnées parce que l'outil les rendait trop chères ? »
> Cible : zéro.**
>
> C'est la traduction opérationnelle des 4 critères de Jay (intuitivité · prise en main · stabilité
> et fiabilité · constance). Un outil qui fait renoncer un créateur à son intention a échoué, même
> si toutes ses fonctions marchent.

**Décisions à porter au PET** (proposées, non encore actées) :
- Relier **B-auto ↔ B4** : le modèle d'automation porte un déclencheur, dont le type « bouton de deck ».
- **ADR à poser** : le moteur expose une interface stable ; deck local et deck distant en sont deux
  clients ; aucune logique dupliquée.

## 7. Ce qui reste à vérifier (honnêteté)

| Lacune | Statut |
|---|---|
| Limites exactes du code C# embarqué chez eux (bac à sable, accès système) | ⚪️ non documenté publiquement — sans impact sur notre conception (on n'exécute pas de code utilisateur, ADR-008) |
| Seuil de saturation d'une file non bloquante | ⚪️ non chiffré |
| Terrain communautaire (Reddit, Discord) | 🟠 partiel — le robot d'exploration est bloqué par Reddit. Le terrain repose sur les changelogs officiels (bugs **prouvés car corrigés**) + le vécu direct de Jay |
| Ergonomie de l'écran des files d'attente | ⚪️ pas de capture — à demander si le sujet devient chaud |

---

## Sources

**Rétro-ingénierie** (preuve dure, 2026-07-16) : fichiers `actions.json` successifs d'une
installation Streamer.bot v1.0.4 en production — schéma v15 (4 juin, 12 juillet) et v23 (16 juillet).
Structures et volumétries uniquement, aucun contenu personnel. Captures de l'application et de
**Streamer.bot Decks** en usage réel.

**Témoignage direct** (Jay, 2026-07-16) : le renoncement aux effets de caméra (§4bis) · le calvaire
de configuration (§4ter) · l'historique des decks essayés (§5bis). Source de première main sur le
vécu — distincte de la mesure, et signalée comme telle partout où elle est utilisée.

**SKB / Eichi** : `13-Intelligence-Artificielle-Technologies/Stream-Deck-OBS-Alternatives-Exhaustive-Veille.md`
(2026-07-10) — *Gap Analysis* : absence de conception adaptée à la neurodiversité sur **tous** les
decks du marché ; interface adaptative absente de tous les logiciels de stream.

**Documentation officielle** : [Actions](https://docs.streamer.bot/guide/core/actions) ·
[Sub-Actions](https://docs.streamer.bot/api/sub-actions) ·
[Triggers](https://docs.streamer.bot/api/triggers) ·
[Variables](https://docs.streamer.bot/guide/variables) ·
[Action Queues](https://docs.streamer.bot/api/sub-actions/core/action-queues) ·
[WebSocket Server](https://docs.streamer.bot/api/websocket/guide/configuration) ·
[Changelog v0.2.4](https://streamer.bot/changelogs/v0.2.4) (preuve du bug de file) ·
[Stream Deck officiel](https://streamdeck.streamer.bot/)

**TouchPortal** : [API plugin](https://www.touch-portal.com/api/) ·
[Logique](https://www.touch-portal.com/blog/post/tutorials/understanding_logic_functions.php) ·
[Documentation Page/Button](https://github.com/touch-portal-community/documentation) ·
[Avis terrain (OBS Forums)](https://obsproject.com/forum/resources/touch-portal.755/reviews) ·
[Greffon Streamer.bot](https://github.com/EnmaDarei/tp_streamerbot_plugin)

**Cadrage** : Jay, session 2026-07-16 — critères de réussite + diagnostic « trop de liberté, pas
assez d'ergonomie ».
