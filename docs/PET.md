---
title: Hikari Stream — PET (Plan d'Exécution Technique)
created: 2026-07-11
updated: 2026-07-17
status: active
type: pet
version: 1.8.1
project: Hikari Stream
---

# Hikari Stream — PET (exécution vivante)

> **Carnet de bord vivant.** Référence le CDC (`CDC.md`) ; le CDC ne référence pas le PET.
> Mis à jour à chaque brique (avant + après). Créé le 2026-07-11 au `/concevoir`.
>
> ✅ **Spike moteur B0.0 FAIT (2026-07-17) — verdict GO, branche A** (décision Jay). Pile prouvée :
> diffusion en direct depuis Rust (NVENC) + survie du processus séparé. Le développement de
> production peut commencer (B0.3 → B1). Détail et preuves : fiche B0.0 §7.
> ⚠️ **Passe d'exhaustivité complète prévue APRÈS B0.0** : le détail interne de plusieurs briques
> dépend de sa mesure. Ce PET pré-décide tout le connaissable, puis sera raffiné en version finale
> exhaustive une fois le spike passé (décision Jay 2026-07-11).
>
> **v1.8.0 (2026-07-17) — passe d'exhaustivité TERMINÉE (vagues 4+) + veille libobs.** §7quinquies :
> les 12 dernières briques (B8, B11-B16, B-dash/settings/cloud/stats/pack). **Veille faite** sur le
> pont : création de source générique + filtres + replay buffer → **B6, B-cam, B7-mouvements passent
> 🟢**. Les 25 briques de production ont une fiche autonome (🟢) ou un cadrage honnête (🟡 + veille au
> démarrage). **Le PET est exécutable de bout en bout.**
>
> **v1.7.0 (2026-07-17) — passe d'exhaustivité, vagues 2 et 3.** §7ter (cockpit interactif :
> B-shell, B-auto, B4, B5) + §7quater (live riche : B6, B7, B-cam, B9, B10). Honnêteté assumée :
> beaucoup de briques vague 3 sont **🟡 (API libobs audio/transitions/caméra non prouvée au spike)**
> — leur vérité externe = « API à confirmer par veille au démarrage ». Solides 🟢 : B-auto (logique
> pure + Streamer.bot), B9 (détection encodeurs prouvée). Reste vagues 4+ : B8, B11-B16, B-dash/
> settings/cloud/stats/pack.
>
> **v1.6.0 (2026-07-17) — passe d'exhaustivité, vague 1 (chemin critique).** Ajout §7bis : fiches
> **exécutables par un run autonome** pour B0.3 · B1 · B2 · B3, chacune avec sa **vérité externe**
> (le champ anti-circulaire). Découverte utile : **B1 doit être scindé** — B1a (moteur + sources =
> autonome) et B1b (aperçu cross-process = mini-spike humain, inconnu réel non prouvé au spike).
> Vagues 2+ détaillées juste-à-temps. Répond à la question de Jay : oui, le PET devient exécutable
> en autonome, brique par brique, sur le chemin critique.
>
> **v1.5.0 (2026-07-17) — le spike B0.0 est exécuté : verdict GO, branche A.** La pile est prouvée
> sur la machine cible — diffusion en direct depuis Rust avec NVENC (reçue par un serveur RTMP) et
> survie du moteur en processus séparé. Le coût d'Hikari est mesuré (faible, surtout GPU). Restent
> différées, **en fin de développement** (décision Jay), la comparaison vs OBS nu et les épreuves
> (d)/(e) — un spike nu ne donne pas le coût du produit. Le développement de production démarre
> (B0.3 → B1). Détail et preuves : fiche B0.0 §7.
>
> **v1.4.0 (2026-07-17) — le pari technique est tombé, le spike change de nature.**
> Une recherche de contre-exemple (**demandée par Jay**, pas spontanée — voir la mémoire
> `rare-n-est-pas-impossible`) a trouvé **`league_record`** : une application **livrée depuis mars
> 2022**, en **Rust + Tauri + moteur d'OBS**, qui enregistre des parties de League of Legends. Plus
> cinq autres projets sur la même base, dont **Cap**. L'affirmation « aucune app connue en
> production » (veille du 2026-07-11) était **fausse et jamais vérifiée**.
>
> | Ce qui change | Avant | Maintenant |
> |---|---|---|
> | Nature du spike | un **pari** (go/no-go) | une **mesure** (à quel coût) |
> | Durée | 2 jours | **1 jour** |
> | L'épreuve reine | « le moteur bloque-t-il notre fil ? » | « **la diffusion tient-elle, et combien coûte-t-on de plus qu'OBS nu ?** » |
> | Architecture | à découvrir | **prouvée** : moteur en **processus séparé** (ADR-013) |
> | Le repli Electron | vivant | **presque mort** — il ne sert plus que si la diffusion échoue |
>
> **Le seul inconnu restant** : personne n'a prouvé « Rust + moteur d'OBS + **diffusion en direct** ».
> `league_record` **enregistre**, il ne diffuse pas. Streamlabs diffuse, mais en Electron. Le
> croisement des deux, personne. C'est là, et **seulement là**, que se situe le risque.
>
> **Correction de cadrage de Jay (2026-07-17)** : un spike sur sa machine ne prouve rien pour les
> autres. Le livrable devient **le surcoût par rapport à OBS nu** (transférable) et le **plancher
> matériel** = plancher d'OBS + ce surcoût (ADR-014).
>
> **v1.2.0 (2026-07-16) — passe d'audit avant dev.** Un contrôle croisé des 64 fonctions du CDC contre
> ce PET a trouvé **7 fonctions sans aucune brique**. Toutes sont désormais rattachées :
>
> | Fonction orpheline | Rattachement | Nature |
> |---|---|---|
> | **F-023** automations avec logique | **B-auto** (brique neuve, Critique) | Le différenciateur du projet — était absent du PET **et** de la maquette |
> | **F-060/061/062** stats · débit · viewers | **B-stats** (brique neuve) | L'écran « Suivi » existe dans la maquette, sans brique |
> | **F-001** installation unique | **B-pack** (brique neuve) | Le livrable final n'était planifié nulle part |
> | F-005 presets de scènes | B9 (socle/wizard) | — |
> | F-027 mode focus live | B-shell (c'est un mode de disposition) | — |
> | F-028 silence alertes 1 clic | B16 (contrôles rapides) | Engagement du CDC §9 « toujours visible », non porté |
> | F-037 waveforms audio | B6 (audio) | — |
>
> F-071 (avatar) était couvert par B13/B14 sans être nommé → identifiant explicité.
> **Contrôle de non-régression** : aucun identifiant du PET n'existe hors du CDC (vérifié dans les deux sens).

---

## 1. Principe d'exécution

- **Brique par brique** : une brique = un lot cohérent, un commit atomique (jamais un commit géant).
- **TDG** : test écrit AVANT le code, rouge d'abord, puis vert, puis refactor.
- **Backup** : tag git tous les 3-4 commits.
- **Trace continue** : chaque brique documentée en §7 (scope, veille, tests, preuves, erreurs, SHA).
- **Plan mode par brique** : chaque brique non commencée passe par le plan natif ; le plan approuvé = reformulation + autorisation de scope.
- **Dérisquage d'abord** : phase P0 (spikes) avant toute construction.

## 2. Anti-Circular Testing Protocol (3 couches)

1. **Algorithmique** : property-based testing + mutation + fuzzing sur la logique déterministe (permissions deck, propagation marque, découpe clips).
2. **Contexte différent** : sessions Writer/Reviewer séparées + tests holdout sur les chemins critiques (moteur, deck+permissions, OAuth).
3. **Modèle différent** : Cross Model Reviewer sur tout module Critique avant « fini » (deck+permissions, encodage/diffusion, connexion comptes).

## 3. Traçabilité bidirectionnelle (CDC → briques → tests)

| Exigence CDC | Briques | Tests clés |
|---|---|---|
| Moteur fiable (F-020, §4, §8) | B0.0, B1 | **diffusion en direct depuis le processus séparé** · **le moteur tué → l'app survit et relance** · **surcoût < 20 % vs OBS nu** |
| Multistream + vertical (F-025, F-026) | B0.2, B3 | double encodage RTX 3060 sans drop |
| Deck local robuste (F-022, F-047) | B4 | latence < 100 ms, marche sans réseau |
| Deck distant + permissions (F-048, §7) | B5 | modérateur bloqué au-delà de ses droits |
| Connexion comptes (§7, §8) | B2, B12 | refresh jeton, coffre système, révocation |
| Audio (F-021, F-037, F-039) | B6 | suppression bruit, ducking déclenché à la voix, **waveform reflète le niveau réel** |
| Scènes avancées (F-029, F-038) | B7 | transition appliquée, source déplacée au switch |
| **Automations avec logique (F-023, §3bis famille Logique)** | **B-auto** | condition vraie → action part · condition non évaluable → **action ne part pas** · cycle refusé à l'enregistrement · délai max par action respecté |
| **Lien automation ↔ deck (F-022 + F-023, ADR-011)** | **B-auto + B4** | une automation à déclencheur « bouton » **apparaît comme touche assignable** · une automation à déclencheur événement **n'apparaît pas** · une touche lance l'automation **avec ses arguments** · le moteur répond **sans réseau** |
| Caméra (F-024, F-036) | B-cam | masque cercle, fond sans écran vert, cam mobile |
| Édition/marqueurs (F-040→F-044) | B11 | marqueur → clip, replay instantané |
| Sous-titres live (F-045) | B0.1, B11 | transcription temps réel locale |
| Publication marque auto (F-050, F-072) | B8, B12 | propagation live→clip→post→miniature |
| Accessibilité ND (§6, §9, F-070) | B9, B15 | WCAG 2.2 AA, reduced-motion, charge cognitive |
| Deck détaillé : 4 types, palette, boards (F-022, §3bis) | B4 | types de touches rendus, action déclenchée, bascule de board |
| Cockpit réorganisable + multi-écran (F-100) | B0.4, B-shell | drag/dock, détacher fenêtre 2ᵉ écran, sync état |
| Modes de disposition Préparation/Live + presets (F-101) | B-shell | bascule preset, sauvegarde/restauration de layout |
| Dashboard d'accueil (F-102) | B-dash | KPIs + derniers streams affichés |
| Écran Paramètres unifié (F-103) | B-settings | onglets comptes/périph/encodage/deck/marque/stockage |
| Connexion cloud utilisateur (F-104) | B-cloud | OAuth Drive/Dropbox/OneDrive/S3, archivage ciblé sur le cloud user |
| Palette de commandes Ctrl+K (F-105) | B15 | ouverture, filtrage, action/écran atteint |
| Centre de santé stream (F-106) | B3, B-shell | état par plateforme, alerte reconnexion |
| Modération inline chat (F-030) | B10 | timeout/ban/épingler depuis un message |
| Morphique police/langue/contraste (F-107→F-109) | B15 | persistance, contraste AA, langue FR/EN/ES |
| **Suivi : stats · débit · viewers (F-060, F-061, F-062)** | **B-stats** | chiffres de lives/clips affichés · débit et stabilité remontés en direct · compteur viewers rafraîchi |
| **Installation unique + moteur embarqué (F-001)** | **B-pack** | installation sur machine vierge **sans OBS préinstallé** · somme de contrôle du binaire vérifiée · refus si version hors plage |
| Presets de scènes (F-005) | B9 | preset chargé puis modifiable (jamais un mur) |
| Mode focus live (F-027) | B-shell | bascule focus masque le superflu, les colonnes ne bougent pas |
| Silence alertes 1 clic (F-028) | B16 | bouton **toujours visible** · un clic coupe toute alerte |
| Avatar VRM 2 étapes (F-071) | B13, B14 | étape 1 source externe · étape 2 natif |

## 4. Cinq métriques de fiabilité des tests

| Métrique | Cible |
|---|---|
| Couverture ligne | ≥ 80 % global · 95 % critique · 90 % sensible |
| Tests vides | 0 (bloquant) |
| Tests triviaux | < 10 % |
| Ratio mock:assert | < 3:1 |
| Couverture de type | 100 % du code neuf (tsc/clippy strict) |

## 5. Assertions défensives (fonctions critiques — ≥ 2 chacune)

- **Permissions deck** (B5) : rôle valide ∈ ensemble connu · action demandée ⊂ droits accordés.
- **Encodage/diffusion** (B2, B3) : réglage ≤ plafond matériel · flux cible ∈ plateformes autorisées.
- **Jetons OAuth** (B2, B12) : jeton non expiré avant usage · jamais loggé/écrit en clair.
- **Découpe clips** (B11) : borne début < borne fin · timestamps ⊂ durée du VOD.
- **Pont VPS** (B5) : session authentifiée avant toute action · origine appairée (QR) valide.
- **Connexion cloud** (B-cloud) : fournisseur ∈ liste supportée · jeton cloud non expiré avant transfert.
- **Détachement panneau** (B-shell) : layout sérialisé valide avant `fromJSON` · panneau détaché ré-intégré à la fermeture de la fenêtre (jamais perdu).
- **Moteur d'automations** (B-auto, Critique — ≥ 2 exigées, 5 posées) : profondeur de séquence ≤ plafond (anti-boucle) · action demandée ⊂ palette autorisée · **type de déclencheur ∈ ensemble fermé** (bouton · commande chat · événement · minuteur — un type inconnu est refusé, jamais ignoré en silence) · déclencheur chat ⊂ liste blanche de commandes exposées · condition non évaluable → **refus fermé** (l'action ne part pas, le fait est journalisé).
- **Installation / moteur embarqué** (B-pack) : somme de contrôle du binaire OBS vérifiée **avant** exécution · version OBS récupérée ∈ plage supportée déclarée.

## 6. Roadmap (briques) — VIVANTE

**Légende** : ⬜ à faire · 🟧 en cours · ✅ fait · ⛔ bloqué

### Phase P0 — Dérisquage (AVANT tout dev)
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B0.0 | **Spike moteur** : diffusion RTMP depuis Rust + moteur en processus séparé + coût mesuré | Critique | ✅ GO branche A (2026-07-17) |
| B0.1 | Spike sous-titres live locaux (modèle type whisper.cpp) | Sensible | ⬜ |
| B0.2 | Validation double encodage RTX 3060 (H + vertical) | Critique | ⬜ |
| B0.4 | Spike détachement panneau dockview sur Tauri (`WebviewWindow` + sync `emit`/`listen`) | Sensible | ⬜ |

### Phase P1 — Socle & moteur
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B0.3 | Scaffold Tauri 2.x + Rust + React 19 + Tailwind 4 | Standard | ✅ FAIT (2026-07-18, fc1b278) |
| B1a | Moteur intégré : scène + sources + protocole JSON-lignes | Critique | ✅ FAIT (2026-07-18, merge 40f45a3) |
| B1b | Aperçu cross-process (moteur → webview) | Critique | ✅ FAIT (2026-07-18, merge 4e97b4c) |
| B2a | Diffusion réelle (RTMP + NVENC), pilotable, sans OAuth | Critique | ✅ FAIT (2026-07-18, merge 6909372) |
| B2b | Comptes OAuth Twitch + YouTube + coffre | Critique | ✅ FAIT (2026-07-18) — Twitch et YouTube prouvés en conditions réelles |
| *(hors brique)* | 1ʳᵉ tranche UI visible : bouton "Connecter Twitch" câblé à `commands.rs` (ADR-011 côté app) | Standard | ✅ FAIT (2026-07-18, `7eb9be0`) — Jay a vu la fenêtre, testé le bouton, ça marche |

### Phase P2 — Live complet
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B3 | Multistream + vertical simultané | Critique | ⬜ |
| B6 | Audio : mixage + filtres micro + suppression bruit + ducking + **routage écoute/diffusion** + **waveforms** (F-021, F-037, F-039) | Standard | ⬜ |
| B7 | Scènes avancées : transitions, mouvements, auto-move (F-029, F-038) | Standard | ⬜ |
| B-cam | Caméra : perso, masques, fond sans écran vert, cam mobile (F-024, F-036) | Standard | ⬜ |

### Phase P3 — Deck
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B4 | Deck local (local-first, < 100 ms) — **client de l'interface du moteur** (ADR-011) ; une touche peut lancer une action simple **ou une automation entière** | Critique | ✅ |
| B5 | Pont VPS (Phoenix) + deck distant + permissions rôle (F-047, F-048) — **2ᵉ client de la même interface**, jamais un passage obligé | Critique | ⬜ |
| **B-auto** | **Moteur d'automations** : condition · délai · variables · séquence + déclencheurs (bouton, chat, événement, minuteur) — sans script externe (F-023, §3bis famille Logique). **Expose l'interface consommée par B4/B5** | **Critique** | ⬜ |

### Phase P4 — Pré-vol, socle utilisateur, interaction
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B9 | Détection matériel + réglage sûr + wizard + **presets de scènes** + pré-vol + feu vert (F-002, F-003, F-005, F-010→F-012) | Sensible | ⬜ |
| B10 | Interaction : chat multi-plateforme + **modération auto + inline** + alertes + pop-up + bandeaux + objectifs (F-030→F-035) | Sensible | ⬜ |

### Phase P5 — Édition (chemin critique visibilité)
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B11 | Marqueurs + clips + replay + sous-titres + chapitres + sous-titres live (F-040→F-045) | Standard/Sensible | ⬜ |

### Phase P6 — Marque & publication
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B8 | Kit de marque + propagation (F-004, F-072) | Standard | ⬜ |
| B12 | Publication native + planning + miniatures + infos diffusion + pont Kobo (F-050→F-054) | Sensible | ⬜ |

### Phase P7 — Avatar
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B13 | Avatar VRM étape 1 (Spout2, source externe) | Standard | ⬜ |
| B14 | Avatar VRM étape 2 (MediaPipe + three-vrm natif) | Standard | ⬜ |

### Phase P8 — Confort, accessibilité, finition
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B15 | Morphique (densité/sensoriel/**police**/**langue**/**contraste élevé**) + **palette de commandes Ctrl+K** + WCAG 2.2 AA + widget feedback + collections/export config (F-006, F-006b, F-070, F-105, F-107→F-109) | Standard | ⬜ |
| B16 | Contrôles rapides (mute micro · confidentialité écran · **silence alertes 1 clic, toujours visible**) + caméra virtuelle + co-stream + don discret (F-028, F-046, F-090→F-093) | Standard | ⬜ |

### Phase P9 — Coque cockpit & écrans transverses
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| B-shell | Coque cockpit **dockview** : panneaux dock/onglets/redimension + détachement 2ᵉ écran + modes Préparation/Live/**Focus** + presets de layout + **centre de santé stream** (F-027, F-100, F-101, F-106) | Sensible | 🟧 **PROCHAINE BRIQUE (2026-07-18)** — le moteur est prouvé (B1/B2 faits), la note de la ligne suivante s'applique : B-shell passe devant l'ordre séquentiel des phases |
| B-dash | Dashboard d'accueil (chiffres clés + derniers streams + à venir/à faire) (F-102) | Standard | ⬜ |
| B-settings | Écran Paramètres unifié (comptes, périphériques, encodage, deck & appairage, kit de marque, stockage, à propos) (F-103) | Sensible | ⬜ |
| B-cloud | Connexion espace cloud utilisateur + archivage auto ciblé (Drive/Dropbox/OneDrive/S3-WebDAV) (F-104) | Sensible | ⬜ |
| **B-stats** | **Écran Suivi** : statistiques lives/clips + stabilité & débit + compteur viewers en direct (F-060, F-061, F-062) | Standard | ⬜ |

### Phase P10 — Livraison
| Brique | Scope | Niveau | Statut |
|---|---|---|---|
| **B-pack** | **Installation unique** : empaquetage Tauri + moteur OBS embarqué (`libobs-bootstrapper`) + somme de contrôle + première ouverture sur machine vierge (F-001) | **Sensible** | ⬜ |

*(Ordre indicatif ; réévalué après le go/no-go du spike B0.0. La coque B-shell est prioritaire dès que le moteur est prouvé — elle héberge tous les panneaux. Exhaustivité finale post-spike.)*

> **Note d'ordonnancement (2026-07-16, révisée)** — deux dépendances à ne pas perdre de vue :
> - **B-auto avant B4** (révision du sens de la dépendance, ADR-011). Le moteur **expose** l'interface,
>   le deck la **consomme** — donc le moteur vient en premier, ou au minimum son interface est figée
>   avant que le deck ne se construise dessus. Ni l'un ni l'autre ne dépend de **B5** : le deck local
>   et les automations doivent tourner **sans réseau** (CDC §13 anti-pattern #4).
> - **B-pack est en fin de route, mais sa stratégie se décide en B0.0** : embarquer OBS dans
>   l'installeur **ou** le télécharger à la première ouverture (`libobs-bootstrapper`). Ce choix pèse sur
>   la taille du paquet — que B0.0 mesure déjà. **À trancher au go/no-go**, pas en P10.

## 7. Détail par brique

> Chaque brique porte : **objectif · approche décidée · tests TDG · critère d'acceptation**.
> Rempli à l'exécution avec : preuves post, erreurs rencontrées, décisions in-flight, SHA.

### B0.0 — Spike `libobs-wrapper` (go/no-go moteur)

> **Régime SPIKE** (§9bis) : code jetable. Pas de TDG, pas de couverture. En échange, les
> **critères ci-dessous sont chiffrés et écrits AVANT** — ils remplacent les tests. Le verdict se
> prouve par des mesures conservées, jamais par une impression.

> 🔄 **RÉÉCRIT le 2026-07-17 — la question a changé, et la peur qui la fondait est tombée.**
>
> **Ce qui est désormais PROUVÉ** (recherche de contre-exemple, 2026-07-17 — déclenchée par Jay, pas
> par moi) : `FFFFFFFXXXXXXX/league_record` est une application **livrée depuis mars 2022**
> (4 ans, poussée en 2026-05, binaires téléchargés) qui fait **Rust + Tauri + moteur d'OBS**, pour
> enregistrer des parties de **League of Legends**. Cinq autres projets utilisent la même base, dont
> **Cap** (enregistreur d'écran connu). **« Aucune application connue en production » était FAUX** —
> affirmation du 2026-07-11 jamais vérifiée. Voir la mémoire `rare-n-est-pas-impossible`.
>
> **Et ils donnent la réponse architecturale** : leur moteur ne tourne **pas** dans l'application.
> Modules `intprocess-recorder` + **`ipc-link`** + binaire **`extprocess_recorder`** → le moteur vit
> dans un **processus séparé**, piloté par un tuyau. La friction async n'est pas résolue : elle est
> **contournée**. Et c'est exactement l'isolation des pannes de l'ADR-001.
>
> **Chiffres qu'ils publient** : moteur ≈ **75 Mo** · **3 % processeur / 50 Mo mémoire** en
> enregistrement · **GPL-3.0** pour respecter la GPL-2.0 du moteur (confirme notre licence).
>
> **Ce qu'ils NE prouvent PAS, et qui devient le sujet** : ils **enregistrent**, ils ne **diffusent
> pas**. Personne n'a prouvé « Rust + moteur d'OBS + **diffusion en direct** ». Streamlabs prouve la
> diffusion (branche B) ; league_record prouve Rust (branche A) ; **le croisement, personne**.

- **Objectif** : répondre à **une** question — *la **diffusion en direct** tient-elle, depuis Rust,
  avec le moteur dans un processus séparé — et **combien coûte-t-on de plus qu'OBS nu** ?*
- **Ce que cette question sert** : elle ne décide plus « go/no-go » (la faisabilité est prouvée). Elle
  **mesure**, et sa mesure nourrit **F-003** (détection matériel + réglage sûr par défaut).

> ⚠️ **Le piège que ce spike doit éviter — correction de cadrage de Jay (2026-07-17).**
> Mesurer « ça marche sur la RTX 3060 de Jay » ne sert **presque à rien** : Hikari doit tourner chez
> **n'importe qui**. Un résultat sur une machine est **un point**, jamais une courbe.
>
> **La parade** — on ne mesure pas la machine, on mesure **notre surcoût** :
>
> | Ce qu'on mesure | Transférable ? |
> |---|---|
> | « ça tourne sur une RTX 3060 » | ❌ un seul point, inutile aux autres |
> | **« on coûte X % de plus qu'OBS nu, à travail égal »** | ✅ **valable sur toutes les machines** |
>
> D'où la règle : **plancher d'Hikari = plancher d'OBS + notre surcoût**. OBS publie ses exigences
> minimales et a dix ans de terrain — on **hérite** de leur plancher, on mesure seulement ce qu'on
> **ajoute**. C'est ce qui rend une mesure sur une seule machine utile à toutes.
>
> **Limite honnête, à ne pas cacher** : la RTX 3060 est **NVIDIA**. Ce spike ne dira **rien** sur les
> cartes AMD, Intel, ni sur les machines **sans encodeur matériel** (repli logiciel). Le moteur d'OBS
> les gère toutes ; **nos** chemins de code, personne ne le sait encore. La vraie matrice matérielle
> viendra des **premiers utilisateurs**, jamais de ce spike. Conséquence : le code **détecte** la
> capacité à l'exécution, il ne **présume** jamais (F-003).

**Prérequis (à réunir AVANT de commencer)**

| Élément | Valeur | Vérifié |
|---|---|---|
| Machine | poste principal, **RTX 3060** (⚠️ **NVIDIA seulement** — voir la limite ci-dessus) | ✅ RTX 3060 confirmée 2026-07-17 |
| Système | Windows 11 (Windows d'abord, CDC §6) | ✅ build 26200 |
| **OBS Studio installé** | 32.x — servait de mesure de référence. ⚠️ **Comparaison vs OBS différée** (Jay 2026-07-17 : mesurer sur l'app finie, pas un spike nu) | ✅ 32.1.2 présent |
| Rust | **1.97.1** stable (msvc) | ✅ mis à jour 1.94.0 → 1.97.1 le 2026-07-17 |
| Chaîne de compilation | nightly ? (league_record l'exige pour ses artefacts binaires) | ✅ **RÉSOLU : nightly PAS nécessaire** — on évite `-Z bindeps` (2 binaires workspace, moteur lancé par chemin) → **Rust stable**. Contrainte permanente écartée |
| `libobs-wrapper` | **9.0.4+32.0.2** | ✅ 2026-07-17 crates.io — binaires résolus à **32.0.4** par cargo-obs-build (checksums OK) |
| `libobs-sources` | 3.3.1+32.0.2 | ✅ 2026-07-17 |
| `cargo-obs-build` | **2.0.3** — pose `libobs` dans `target/` | ✅ 2026-07-17 installé + exécuté |
| `libobs-bootstrapper` | 0.4.0 — pour l'épreuve (e) | 2026-07-17 (épreuve e différée) |

**Durée bornée : 1 jour ouvré** *(réduite de 2 j → 1 j le 2026-07-17 : on ne cherche plus dans le
noir, on part d'une architecture prouvée)*. Au-delà → **arrêt + escalade à Jay**, sans exception. Un
spike qui déborde EST un résultat (§9bis).

**Livrable (rangé, jamais éparpillé)**

| Quoi | Où |
|---|---|
| Le code jetable | `theermite/Hikari` → `spikes/b0.0-libobs/`, branche `spike/b0.0-libobs` — **jamais fusionnée dans `main`** |
| Les mesures brutes | `spikes/b0.0-libobs/mesures/` (relevés mémoire, sortie encodée, journaux). Les artefacts lourds sont ignorés par git (`.gitignore`) |
| **Le verdict** | **ici même**, dans cette fiche : go/no-go + le chiffre qui tranche + la date |

**Approche décidée** *(réécrite 2026-07-17)* : **copier l'architecture prouvée**, ne pas la
redécouvrir. Le moteur tourne dans un **processus séparé** ; l'application lui parle par un tuyau.

```
[ app Rust ] --tuyau--> [ processus séparé : le moteur d'OBS ]
```

**Pourquoi cette forme, et pas le moteur dans l'app** : (1) c'est ce que fait la seule application
livrée sur cette pile, depuis 4 ans ; (2) elle **contourne** la friction async au lieu de la
combattre — un moteur qui ne partage pas notre fil ne peut pas geler notre interface ; (3) elle
**EST** l'isolation des pannes de l'ADR-001 — le moteur peut mourir, l'app survit et le relance.

**Les 5 épreuves et leurs seuils chiffrés**

| # | Épreuve | Comment on mesure | Seuil de réussite |
|---|---|---|---|
| **a** | **DIFFUSER en direct** ⭐ | Diffuser 5 min vers un serveur d'ingestion (local ou clé de test), depuis le processus séparé | Le flux **arrive** · codec matériel **confirmé** (jamais un repli logiciel muet) · **0 image perdue** · débit stable |
| **b** | **Le processus séparé tient** ⭐ | **Tuer le processus moteur pendant la diffusion**, observer l'app | L'app **survit** (elle ne meurt pas avec lui) · elle **détecte** la mort · elle **relance** · elle le **dit** à l'utilisateur. C'est l'ADR-001 prouvé, ou infirmé. |
| **c** | **Notre surcoût vs OBS nu** ⭐⭐ ⏳ *différé fin de dev* | **Le même travail deux fois** : OBS Studio nu diffuse → relever GPU/CPU/mémoire/images. Puis Hikari fait l'identique. **Comparer.** | ⚠️ Le coût mesuré est **sur le GPU** (NVENC), le CPU est quasi nul → le seuil « < 20 % CPU » est à revoir. Comparaison vs OBS **reportée à l'app finie** (Jay 2026-07-17) : un spike nu ne donne pas le coût du produit. |
| **d** | Double encodage en jouant | Horizontal + vertical, **avec un jeu qui tourne** | **0 image perdue** sur les deux sorties **ET** chute du jeu **< 10 %** |
| **e** | Installation | Taille des deux options + le pont expose-t-il une somme de contrôle ? | Deux tailles relevées **ET** réponse binaire (non → l'embarqué devient obligatoire, CDC §8). Repère : leur moteur pèse **75 Mo** |

> **Pourquoi (c) est devenu le juge, à la place du blocage async.** L'épreuve du blocage tombe : le
> processus séparé la rend sans objet — le moteur n'est plus sur notre fil. Le vrai enjeu se déplace
> vers **ce qu'on coûte**. Un surcoût mesuré est le **seul** résultat qui serve un utilisateur qu'on
> n'a jamais vu. Sans mesure de référence, ce spike ne parle que de la machine de Jay.

**Ce que le spike PRODUIT (le livrable réel, pas un verdict)**

| Sortie | Ce qu'elle nourrit |
|---|---|
| **Le surcoût chiffré** (% processeur / mémoire vs OBS nu) | **F-003** — réglage sûr par défaut · le plancher matériel annoncé |
| **Le plancher** = plancher publié d'OBS **+** notre surcoût | Les exigences minimales d'Hikari · la fiche descriptive publique |
| Le seuil du double encodage sur RTX 3060 | **Un point** de la matrice, pas la matrice · l'alerte avant Go Live (CDC §8) |
| Le comportement à la mort du moteur | La parade « relance auto isolée » (CDC §8) |

**Critère d'acceptation / fork** *(le « go/no-go » n'existe plus — il est remplacé)*

| Branche | Condition | Conséquence |
|---|---|---|
| **A — confirmé** | (a) + (b) passent **ET** (c) < 20 % | On bâtit en **Rust natif**, moteur en processus séparé, **GPL-3.0**. Le chiffre (c) part dans F-003. |
| **A′ — confirmé, mais on coûte cher** | (a) + (b) passent, (c) ≥ 20 % | On bâtit quand même — **et on remonte le plancher matériel annoncé**. Honnêteté : mieux vaut un plancher haut et vrai qu'une promesse fausse. |
| **B — repli** | **(a) échoue** — la diffusion ne tient pas depuis Rust | **C'est le seul vrai no-go restant.** Repli Electron + `obs-studio-node`. ⚠️ **La licence passe alors en GPL-2.0** — le dépôt public est en GPL-3.0, il faut re-trancher **avec Jay, au moment du verdict**. |

> ✅ **Verdict rendu le 2026-07-17 : branche A.** (a) et (b) passent ; le coût sur la machine cible
> est faible. La condition « (c) < 20 % » est **différée** (comparaison vs OBS en fin de dev, Jay) —
> le verdict A est prononcé sur (a)+(b) + coût absolu faible, jamais sur un chiffre de surcoût qu'un
> spike nu ne peut pas donner honnêtement. La branche B (repli Electron) est écartée.

> ⚠️ **Piège de la branche B — relevé le 2026-07-16, à ne PAS découvrir le jour du no-go.**
> Le paquet npm `obs-studio-node@0.10.10` date de **décembre 2020** et se décrit « Experimental » —
> un fantôme. Le vrai projet `stream-labs/obs-studio-node` est **poussé le 2026-07-16**, 681 étoiles,
> maintenu (Streamlabs Desktop tourne dessus, en production). **La distribution passe par le dépôt
> Streamlabs, jamais par npm.** Un `npm install` ferait conclure à tort que le repli est mort.
> Autre signal : 69 tickets ouverts — mature ≠ sans friction.

**Ce que ce spike ne fait PAS** (anti-dérive) : ni interface soignée, ni scènes multiples, ni audio,
ni chat, ni deck. **Diffuser, mesurer, comparer.** Rien d'autre.

**Ce qu'il ne PEUT PAS dire, et qu'on n'écrira donc nulle part** : le comportement sur AMD, Intel, ou
sans encodeur matériel. Une seule machine, un seul point. La matrice vient des premiers utilisateurs.

- **Statut** : ✅ **fait — 2026-07-17** (branche `spike/b0.0-libobs`, commits `78bde90` → `eb08e3e`).
- **Verdict** : **GO — branche A** (décision Jay, 2026-07-17). La pile est prouvée.
  - **(a) diffusion** ✅ : Rust + moteur d'OBS en **processus séparé** diffuse en direct, reçu de
    bout en bout par un serveur RTMP (MediaMTX). **Codec matériel confirmé** :
    `OBS_NVENC_H264_TEX hardware=true` (jamais un repli x264 muet). Preuve :
    `spikes/b0.0-libobs/mesures/epreuve-a-diffusion.md`.
  - **(b) survie** ✅ : moteur **tué en plein flux** → le contrôleur survit, détecte, relance, le
    dit. Prouvé des **deux côtés** (contrôleur + 2 sessions de publication MediaMTX). C'est
    l'ADR-001/ADR-013 rendus observables. Preuve : `mesures/epreuve-b-survie.md`.
  - **(c) coût** : mesuré côté Hikari — **CPU 0,8 % · GPU 27 % · encodeur NVENC 35 % · RAM 487 Mo**
    (capture 1080p, NVENC CBR 6000). Constat : le coût est **sur le GPU**, le CPU est quasi nul.
    Preuve : `mesures/epreuve-c-surcout.md`.
  - **Inconnu résolu** : Rust **nightly PAS nécessaire** — on évite `-Z bindeps` (2 binaires
    workspace, moteur lancé par chemin) → **Rust stable**. Une contrainte permanente écartée.
  - **Différé par décision de Jay (2026-07-17)** : la **comparaison surcoût vs OBS nu** (c), le sceau
    5 min + Twitch de (a), le **double encodage (d)**, la **taille d'installation (e)**. Raison : le
    surcoût pertinent est celui de l'**application finie**, jamais d'un spike nu — on mesurera vs OBS
    **en fin de développement**, et la matrice matérielle viendra des premiers utilisateurs. Rien de
    cela ne bloque le développement pour Jay (D12). Voir amendement ADR-014.

### B0.1 — Spike sous-titres live locaux *(fiche complétée 2026-07-16)*

> **Régime SPIKE** (§9bis).

- **Objectif** : répondre à **une** question — *peut-on transcrire la parole en direct, **sur la
  machine**, sans service cloud et sans étouffer le stream ?* (F-045)
- **Pourquoi ça compte** : F-045 est classé **Sensible** (CDC §7) — accessibilité, et obligation
  légale à venir. Mais un sous-titrage qui vole du CPU à l'encodage casse le live : le remède serait
  pire que le mal.

**Prérequis**

| Élément | Valeur | Vérifié |
|---|---|---|
| `whisper.cpp` | **v1.9.1** (build CUDA) | 2026-07-16 via API GitHub |
| Machine | RTX 3060 — le modèle tourne sur le **même GPU que l'encodage**, c'est tout l'enjeu | — |
| Audio | **micro réel**, parole **en français** (la langue réelle des streams) | — |

**Durée bornée : 1 jour ouvré.** **Livrable** : `spikes/b0.1-soustitres/` · verdict écrit ici.

**Approche décidée** : whisper.cpp en mode continu sur le micro, **pendant qu'un encodage tourne**.
Jamais mesuré à vide : un modèle seul sur une machine au repos ne prouve rien.

**Les 3 épreuves et leurs seuils**

| # | Épreuve | Comment on mesure | Seuil |
|---|---|---|---|
| **a** | Latence | Horodater parole → texte affiché | **< 2 s** (seuil CDC) |
| **b** | Cohabitation | Encodage actif en parallèle, compter les images perdues | **0 image perdue** sur l'encodage. C'est le juge : le sous-titrage ne prend jamais le pas sur le stream. |
| **c** | Intelligibilité (français) | Lire un texte connu de **100 mots**, compter les mots faux | **< 15 % de mots faux** — au-delà, le sous-titre nuit plus qu'il n'aide (il donne une fausse information à qui ne peut pas entendre, ce qui viole la Dignité) |

**Critère d'acceptation / fork**

| Branche | Condition | Conséquence |
|---|---|---|
| **A — go** | (a) + (b) + (c) passent | F-045 confirmé, B11 l'implémente |
| **B — no-go** | (b) échoue (le stream souffre) | **Sous-titres live reportés au backlog.** F-042 (post-live) **conservé** — l'accessibilité n'est pas perdue, elle est différée. CDC §10 « reporté au backlog » déjà prévu → pas de déviation. |
| **C — à arbitrer** | (a) ou (c) échoue seul | Techniquement là, qualité insuffisante. Jay décide : livrer dégradé (jamais si (c) échoue — un faux sous-titre trompe), ou reporter. |

- **Statut** : ⬜ non commencé.
- **Verdict** : *(go/no-go + les 3 mesures + date)*

### B0.2 — Double encodage RTX 3060 *(fiche complétée 2026-07-16)*

> **Régime SPIKE** (§9bis).

- **Objectif** : répondre à **une** question — *la RTX 3060 encaisse-t-elle l'horizontal 1080p **et**
  le vertical simultané (F-026) **pendant que Jay joue** ?*

> 🟢 **Bonne nouvelle datée (2026-07-16) — une peur périmée levée.** La limite historique de
> **2 sessions NVENC simultanées** sur cartes grand public **n'existe plus** : passée à 3 (2020),
> 5 (2023), puis **8 ou plus** aujourd'hui, sur toutes les générations depuis Maxwell. Le double
> encodage n'est **pas** bloqué par une limite artificielle. Le seul juge reste la **puissance
> réelle**. (Sources : VideoCardz, Tom's Hardware, note d'application NVENC.)

**Prérequis**

| Élément | Valeur |
|---|---|
| Matériel | **RTX 3060** — la carte réelle, jamais une autre |
| Pilote | à jour (la limite de sessions dépend du pilote) |
| Charge | **un jeu réel qui tourne** (LoL ou Dofus) — voir ci-dessous |

**Durée bornée : 1 jour ouvré.** **Livrable** : `spikes/b0.2-double-encodage/` · verdict ici.

**Approche décidée** : banc d'essai sur la machine réelle, deux sorties (1080p horizontal + vertical),
**avec un jeu qui tourne**.

> **Pourquoi le jeu doit tourner — correction du cadrage.** Le CDC §6 dit « double encodage RTX 3060
> sans chute d'image ». Mesurer ça sur une machine au repos donnerait un **faux go** : l'usage réel,
> c'est encoder **en jouant**. Un double encodage qui passe à vide mais fait chuter le jeu à 40 images
> par seconde est un échec — le stream serait sauvé, la partie sacrifiée.

**Les 3 épreuves et leurs seuils**

| # | Épreuve | Comment on mesure | Seuil |
|---|---|---|---|
| **a** | Les deux sessions s'ouvrent | Lancer les 2 encodages | 2 sessions NVENC actives, **aucun repli logiciel silencieux** (codec confirmé sur les deux) |
| **b** | Zéro image perdue | 10 min de charge, relever les deux sorties | **0 image perdue** sur **chaque** sortie, à réglage sûr |
| **c** | Le jeu reste jouable | Images par seconde du jeu, avec et sans le double encodage | Chute **< 10 %** — au-delà, l'outil coûte la partie |

**Critère d'acceptation / fork**

| Branche | Condition | Conséquence |
|---|---|---|
| **A — go** | (a) + (b) + (c) passent | F-026 (vertical simultané) confirmé sans réserve |
| **B — plafonner** | (b) ou (c) échoue | **Plafonner** : vertical à cadence réduite, ou résolution moindre. **Documenter le seuil matériel** → il nourrit F-003 (réglage sûr par défaut) et l'alerte avant Go Live (FMEA CDC §8). Le vertical n'est pas abandonné, il est **borné et honnête**. |

- **Statut** : ⬜ non commencé.
- **Verdict** : *(go/plafonnement + les 3 mesures + le seuil trouvé + date)*

### B0.4 — Spike détachement de panneau (dockview sur Tauri) *(fiche ajoutée 2026-07-16)*

> **Régime SPIKE** (§9bis). Fiche absente jusqu'ici : la brique était dans la feuille de route
> depuis le 12 juillet **sans objectif, ni seuil, ni critère** — donc non exécutable.

- **Objectif** : répondre à **une** question — *un panneau du cockpit peut-il vivre dans une
  **fenêtre native séparée**, sur un 2ᵉ écran, avec son état synchronisé ?* (F-100)
- **Pourquoi c'est un spike et pas une brique** : l'API de détachement de dockview vise le **web**
  (une popup navigateur). Tauri ouvre des **fenêtres natives**. Personne ne garantit que les deux se
  marient — c'est un pari, donc il se prouve avant (ADR-005).

**Prérequis**

| Élément | Valeur | Vérifié |
|---|---|---|
| Tauri | **2.11.5** | 2026-07-16 via API crates.io |
| `dockview-react` | **7.0.2** (React 19 déclaré en dépendance de pair) | 2026-07-16 via API npm |
| React | **19.2.7** | 2026-07-16 |
| Matériel | **2 écrans physiques** — un seul écran ne prouve rien | — |

**Durée bornée : 1 jour ouvré.** Au-delà → arrêt + escalade.

**Livrable** : `spikes/b0.4-detach/` sur la branche `spike/b0.4-detach` · verdict écrit ici.

**Approche décidée** : mini-app Tauri + dockview à **3 panneaux**. Détacher le panneau 2 vers une
`WebviewWindow` native, synchroniser par `emit`/`listen`. **Jamais `BroadcastChannel`** — les
contextes JavaScript sont séparés, il ne les traverse pas (ADR-005).

**Les 4 épreuves et leurs seuils**

| # | Épreuve | Comment on mesure | Seuil |
|---|---|---|---|
| **a** | Détacher | Sortir un panneau, le poser sur le 2ᵉ écran | La fenêtre s'affiche **sur le 2ᵉ écran**, le panneau y est rendu, et il a **disparu** de la fenêtre principale (jamais dupliqué) |
| **b** | Synchroniser | Modifier l'état d'un côté, observer l'autre | Aller **et** retour · propagation **< 100 ms** (même exigence que le deck local, CDC §6) |
| **c** | Réintégrer | Fermer la fenêtre détachée | Le panneau **revient** dans la fenêtre principale, à sa place, **jamais perdu** (assertion §5) |
| **d** | Survivre | `toJSON` avec un panneau détaché → relancer → `fromJSON` | La disposition se restaure **sans panneau fantôme ni panneau manquant** |

> **Pourquoi (c) et (d) sont les vrais juges.** Détacher est facile ; c'est le **retour** qui casse.
> Un panneau perdu à la fermeture, ou un fantôme après redémarrage, rend le cockpit inutilisable —
> et c'est le mode de panne qu'aucune démonstration ne montre.

**Critère d'acceptation / fork**

| Branche | Condition | Conséquence |
|---|---|---|
| **A — go** | les 4 épreuves passent | F-100 (multi-écran) est confirmé ; B-shell l'implémente |
| **B — repli** | (a) ou (b) échoue | **Le cockpit reste mono-fenêtre en v1.** Panneaux déplaçables et redimensionnables conservés, détachement **reporté au backlog**. Le CDC §3ter (F-100) est alors **amendé**, et la déviation notée en §13. |
| **C — à arbitrer** | (c) ou (d) échoue seul | Détachement techniquement possible mais **fragile**. Décision de Jay : reporter, ou payer le coût d'une gestion d'état maison. Ne jamais livrer un cockpit qui perd des panneaux. |

- **Statut** : ⬜ non commencé.
- **Verdict** : *(à écrire ici — go/repli/arbitrage + les mesures + date)*

## 7bis. Fiches exhaustives — VAGUE 1 (chemin critique) *(ajouté 2026-07-17, post-spike)*

> **But** : rendre chaque brique **exécutable par un run autonome**. Chaque fiche porte 7 champs,
> dont la **vérité externe** (contre quoi un relecteur d'un autre contexte vérifie le résultat —
> sans elle, un run s'auto-valide, `Quality.md` anti-circulaire). Détaillé **juste-à-temps** : on
> ne fige que les briques dont le détail est *connaissable* aujourd'hui (le spike a prouvé l'API).
>
> **Légende autonomie** : 🟢 prête pour un run autonome · 🟡 cadrage humain / mini-spike d'abord.

### B0.3 — Scaffold de l'application (Tauri 2 + React 19 + Tailwind 4) · Standard · 🟢 — ✅ FAIT (2026-07-18)

> **✅ Livré (commit `fc1b278`, sur `main`)** : socle Tauri 2.11 + React 19.2 + Vite 7 + TS 5.8
> strict + Tailwind 4.3 + Biome 2.5 + Vitest 4.1. Tous verts : `pnpm test`/`lint`/`build`,
> `cargo build`/`clippy` (0 avertissement). Combo **stable** (Vite 8 / TS 7 reportés). Socle pur
> (boilerplate retiré). **Constat pour B1** : `@testing-library/react` 16.3 + jsdom sont
> incompatibles avec l'`act` de React 19.2 (`React.act` = `undefined`) → retirés ; test smoke via
> `renderToStaticMarkup`. Le test interactif (jsdom + Testing Library) est à recâbler en B1 avec une
> veille fraîche (autre lib, ou attendre une version RTL compatible).

- **Objectif** : le socle réel — fenêtre Tauri, front React qui build, lint + tests câblés. B1+ s'y greffent.
- **Approche décidée** : Tauri **2.11.x** (`src-tauri/`) · React **19.x** + Vite + Tailwind **4** (`src/`) · pnpm · Biome (lint TS) + Clippy (Rust). Le **moteur reste une crate/binaire séparé** (ADR-013) : le workspace `src-tauri` accueillera `engine` en B1. `dockview` **pas ici** (B-shell). Zéro logique métier.
- **Fichiers** : `package.json` · `src-tauri/{Cargo.toml, tauri.conf.json, build.rs, src/main.rs, src/lib.rs}` · `src/{main.tsx, App.tsx}` · `index.html` · `vite.config.ts` · `tsconfig.json` · `biome.json` · `.gitignore`.
- **Tests TDG** : `should_build_release_when_scaffolded` (`pnpm tauri build` exit 0) · `should_render_shell_when_mounted` (Vitest) · `should_pass_tsc_strict` (0 erreur type).
- **Critère d'acceptation** : `pnpm build` + `cargo build` verts · `pnpm test` + `cargo test` verts · Biome + Clippy zéro · fenêtre s'ouvre en `tauri dev`.
- **Vérité externe** : la doc **officielle** Tauri 2 (versions re-vérifiées au démarrage de la brique) + le build/run **mécanique**. Rien à inventer → le relecteur rejoue `build` + `dev`.
- **Pré-vol** : `pnpm -v` + `cargo -V` sortent 0 · brique non ambiguë.

### B1 — Moteur intégré : scène + sources + aperçu · Critique · ✅ FAIT (B1a + B1b livrées)

> ✅ **B1a livré (2026-07-18, merge `40f45a3`)** : moteur + contrôleur portés du spike en
> crates de `src-tauri` (`hikari-protocol` + `engine` + `engine_bridge`), protocole JSON-lignes
> figé (ADR-011), sources exposées. 10 tests verts (protocole proptest + supervision).
> Revue Gate 2 GO-avec-réserves, 3 défauts corrigés. Détail : `docs/Sessions/run-2026-07-18-0127.md`.
> ✅ **B1b — les 2 jalons du spike sont GO (2026-07-18)** : jalon 1 (aperçu vivant, un
> processus) et jalon 2 (reparent HWND cross-process, `SetParent`) prouvés avec Jay —
> `spikes/b1b-preview/` (branche `spike/b1b-preview`), verdicts dans son README. Le risque
> documenté avant codage (Microsoft/Raymond Chen : files d'entrée attachées cross-process)
> **ne s'est pas matérialisé** (redimensionnement + déplacement fluides, fermeture propre,
> zéro processus orphelin). **Piste retenue : reparent HWND** (la texture GPU partagée
> n'est plus nécessaire).
>
> ✅ **B1b — brique de production livrée et mergée (2026-07-18, `4e97b4c`)** : moteur
> capable d'aperçu (obs_display + fenêtre native, reste en vie, sort proprement sur
> `Stop`) · `preview_bridge.rs` (greffe HWND cross-process testée, régression du bug
> spike gardée par un test dédié) · protocole `PreviewReady{hwnd}`. TDG a trouvé et
> corrigé 2 vrais bugs (dimensions à 0 sur entrée dégénérée) avant tout run réel. Revue
> Gate 2 GO-avec-réserves : 1 Majeur (reporting d'erreur cassé dans `resumed()`, une
> callback winit sans `Result` — corrigé) + 2 Mineurs, tous corrigés. 16 tests verts,
> clippy 0. **Dette fuite mémoire du spike corrigée** (ordre `display` avant `context`).
>
> ⚠️ **Dette test héritée de B0.3** : jsdom + Testing Library sont retirés (incompat `act` React
> 19.2). Recâbler le test interactif au moment des briques d'écran, veille fraîche. B1a est du
> Rust pur → non concerné.
>
> ⚠️ **Dette B1a (hors périmètre, notée par la revue)** : `engine_path()` suppose le binaire
> moteur voisin du contrôleur — vrai en dev (`target/<profil>/`), à prouver dans le layout d'un
> bundle Tauri (sidecars/`externalBin`) avant packaging (B-shell).

- **Objectif** : l'app pilote le moteur (processus séparé) ; une scène avec ≥1 source s'affiche en **aperçu**.
- **Approche décidée** : porter l'`engine` du spike en crate du workspace `src-tauri`. Le contrôleur (Rust) lance + supervise le moteur (survie/relance **prouvées** en B0.0). **Protocole du tuyau** = messages **JSON lignes** sur stdio (c'est l'interface de l'ADR-011, à figer ici). Sources via `libobs-simple` (capture écran/jeu/fenêtre, API **prouvée** au spike).
- **✅ L'inconnu de l'APERÇU est levé** : le spike B1b (2 jalons GO) a prouvé l'affichage
  ET le reparent cross-process avec `windows` 0.62.2 (`SetParent`, style `WS_CHILD | WS_VISIBLE`
  — composer les bits, jamais remplacer tout le style : bug vécu et corrigé au spike).
  `WebviewWindow::hwnd()` existe côté Tauri (vérifié dans le code source du crate `tauri`
  2.11.1, `src/webview/webview_window.rs:1835`), rend le même type `windows::Win32::Foundation::HWND`
  que celui utilisé au spike — composable directement.
- **Fichiers** : `src-tauri/crates/engine/src/main.rs` (ajout aperçu) · `src-tauri/crates/protocol/src/lib.rs` (message `PreviewReady`) · `src-tauri/src/preview_bridge.rs` (nouveau) · `src-tauri/src/lib.rs` (câblage commande Tauri).
- **Tests TDG** : round-trip protocole étendu (`PreviewReady`, proptest) · `child_style_bits` (composition WS_CHILD|WS_VISIBLE, pur) · `fit_size` (rapport 16:9, pur, repris du spike) · ordre de destruction display-avant-contexte (corrige la dette fuite mémoire du spike).
- **Critère d'acceptation** : ✅ une scène + une capture s'affichent en aperçu, greffées dans une fenêtre hôte (mécanisme testé — câblage bout-en-bout dans une vraie fenêtre Tauri = B4/B-shell) · protocole JSON testé par propriétés · `cargo test`/`clippy --workspace` verts.
- **Vérité externe** : l'API `libobs-wrapper` (transcrite, prouvée au spike B0.0) + le mécanisme de reparent (transcrit, **prouvé** au spike B1b, jalons 1 et 2) + `WebviewWindow::hwnd()` (vérifié dans le code source Tauri 2.11.1).
- **Dette restante (hors périmètre B1b, notée pour B-shell/B4)** : câblage UI bout-en-bout (lancement du moteur au démarrage de l'app, bouton frontend qui déclenche la greffe) · `engine_path()` non prouvé en bundle Tauri (héritée de B1a).
- **Autonomie** : **B1a** (🟢 autonome, tout transcrit/prouvé) → ✅ livré en run autonome 2026-07-18 · **B1b** (mini-spike humain, inconnu réel) → ✅ spiké et livré avec Jay 2026-07-18, jamais en run aveugle.

### B2 — Encodage + diffusion (single) + connexion comptes OAuth · Critique · scindée (B2a ⬜ / B2b ⬜) *(scindée 2026-07-18, précédent B1)*

> **Pourquoi scinder** : B2 mélangeait 2 natures distinctes — la diffusion (transcription
> pure, prouvée au spike B0.0) et l'intégration OAuth (a besoin d'une vraie app développeur
> Twitch/YouTube que seul Jay peut créer — client ID, URI de redirection — jamais inventable
> ni committable). Séparer évite de bloquer la diffusion sur une ressource externe absente.

#### B2a — Diffusion réelle (RTMP + NVENC) · Critique · ✅ FAIT (2026-07-18, merge `6909372`)

> Moteur pilotable (`StartStream`/`StopStream`), transcription fidèle du spike B0.0 vérifiée
> ligne à ligne par la revue Gate 2. 16 tests verts, clippy 0. Cible RTMP toujours par
> variables d'environnement (B2b la remplace). **B2b prête à démarrer** : Jay a déjà l'app
> développeur Twitch + les clés YouTube (2026-07-18) — identifiants transmis au moment voulu,
> jamais en clair dans la conversation ni committés (Confidentialité).

- **Objectif** : le moteur diffuse réellement un flux RTMP (cible manuelle, comme au spike —
  **pas encore via un compte connecté**, ça viendra en B2b), pilotable par commande
  (`StartStream`/`StopStream`) au lieu d'une durée fixe codée en dur.
- **Approche décidée** : porte le code du spike B0.0 (`rtmp_output` + NVENC/x264 + service
  RTMP via FFI `run_with_obs!`) dans `crates/engine`. **Cible RTMP toujours par variables
  d'environnement** (`HIKARI_RTMP_SERVER`/`HIKARI_RTMP_KEY`, défaut MediaMTX local, zéro
  secret) — le protocole ne transporte JAMAIS de clé ; construire un transport de secret
  IPC maintenant serait prématuré, B2b le remplace par le coffre + OAuth.
- **Fichiers** : `src-tauri/crates/engine/src/main.rs` (étendu) · `src-tauri/crates/protocol/src/lib.rs` (`StartStream`/`StopStream`, `Started` sans durée fixe, `StreamStopped`).
- **Tests TDG** : round-trip protocole étendu (proptest) · reste (choix encodeur, FFI service) validé par exécution réelle (régime intégration, comme B0.0/B1a/B1b — `libobs` empêche un test headless).
- **Critère d'acceptation** : diffusion réelle vers MediaMTX local (ou Twitch avec clé de test fournie par Jay, jamais committée) · codec matériel confirmé ou repli **dit** · statistiques d'images perdues rapportées en continu (pas une seule mesure finale comme au spike) · arrêt propre sur `StopStream`.
- **Vérité externe** : la diffusion (prouvée B0.0, transcrite).
- **Pré-vol** : `cargo test --workspace` exit 0 · brique non ambiguë.

#### B2b — Comptes OAuth + coffre · Critique · ✅ FAIT (Twitch + YouTube, prouvés en conditions réelles)

> **Pivot suite au challenge de Jay** : le flux prévu (Authorization Code + PKCE) exige un
> secret client d'après la doc officielle Twitch — inadapté à une app desktop open-source
> (code public, secret extractible). Basculé sur le **Device Code Flow** (crate
> `twitch_oauth2`, vérifié dans son code source) : `client_id` public uniquement, app
> Twitch enregistrée en type **Public** (aucun secret émis). PKCE générique (`oauth.rs`)
> conservé pour YouTube, qui le supporte pour les apps installées.
>
> Livré (Twitch) : `accounts/vault.rs` (coffre système, type `Secret` — fuite devient une
> erreur de compilation) · `accounts/twitch.rs` (flux réel, `TWITCH_CLIENT_ID` câblé, erreurs
> typées `TwitchAuthError::{Expired,Other}`). 27 tests verts, clippy 0, 2 revues Gate 2.
>
> ⚠️ **YouTube — incident de process reconnu (2026-07-18)** : `accounts/youtube.rs`
> (Authorization Code + PKCE, serveur local `tiny_http` port 8731) a été **committé
> directement sur `main`, sans branche ni revue préalable** — rupture de la discipline
> suivie sur tout le reste du projet. Rattrapé par une revue Gate 2 rétroactive (2 défauts
> Majeurs réels : chemin de redirection non vérifié, absence de délai — corrigés `fe5af55`).
> 2 tests réseau automatisés retirés (faisaient pendre la suite 10+ min, cause diagnostiquée
> **avec Jay** — WSL2, commutateur virtuel Hyper-V bloquant des connexions sur ports
> éphémères, confirmé via `netsh`) ; ce mécanisme est validé par exécution manuelle
> uniquement, comme le moteur libobs.
>
> ✅ **Prouvé en conditions réelles (2026-07-18, `a6684e3`)** : `cargo run --example
> youtube_manual_auth` — flux OAuth complet avec les identifiants réels de Jay, écriture ET
> relecture depuis le vrai Windows Credential Manager, expiration cohérente (~1h, standard
> Google). 2 bugs trouvés et corrigés en le lançant : `cmd /C start` tronquait l'URL au
> premier `&` (remplacé par `explorer.exe`) · process de test resté vivant verrouillait la
> recompilation (diagnostiqué, arrêté). Twitch déjà prouvé de la même façon (§ Device Code
> Flow ci-dessus). **Les deux plateformes sont vertes ET prouvées, pas seulement testées.**
>
> **Reste hors périmètre** : câblage UI (bouton de connexion → B4/B-shell) pour les deux
> plateformes.

- **Objectif** : connexion de compte (OAuth Twitch/YouTube), jetons au coffre système,
  URL/clé RTMP **depuis le compte** (remplace la variable d'environnement de B2a).
- **Fichiers** : `src-tauri/src/accounts/{oauth.rs, vault.rs, twitch.rs}` · `src/features/accounts/*` (câblage UI, à venir).
- **Tests TDG** : `should_refuse_stream_when_token_expired` · `should_never_leak_tokens_in_debug_output`/`should_never_leak_secret_in_display_output` · `should_only_address_whitelisted_platforms` · `should_request_only_the_stream_key_scope`. Le flux réseau lui-même (démarrage + poll Twitch) reste validé par exécution réelle (régime intégration) — pas de test automatisé contre le vrai serveur Twitch.
- **Critère d'acceptation Twitch** : ✅ jeton obtenu via Device Code Flow, coffre vérifié (`Secret`, jamais en clair) · **YouTube reste à faire**.
- **Vérité externe** : doc officielle Twitch (Authorization Code — vérifiée verbatim, exige un secret) + code source du crate `twitch_oauth2` 0.17.1 (`DeviceUserTokenBuilder`, `Scope::ChannelReadStreamKey`) + Twitch Developer Forums (client Public confirmé).
- **Pré-vol YouTube** : app développeur Google/YouTube créée par Jay (déjà annoncée disponible) · scope + flux à revérifier à la source avant de coder (Google a son propre modèle, jamais supposer qu'il copie Twitch).
- **Autonomie** : 🟡 la 1ʳᵉ intégration (Twitch) a nécessité une validation humaine — confirmé nécessaire : le choix du flux Device Code vs Authorization Code venait d'un challenge de Jay, pas d'une évidence technique. YouTube peut réutiliser le motif PKCE déjà posé, mais sa propre vérité externe reste à établir.

### B3 — Multistream + vertical simultané · Critique · 🟢 (dépend de B2)

- **Objectif** : diffuser vers N plateformes **et** une sortie verticale, en même temps (F-025, F-026). **Absorbe l'ex-spike B0.2** (double encodage en jouant).
- **Approche décidée** : plusieurs `rtmp_output` + services (motif **prouvé** en B2) · un 2ᵉ encodeur/sortie pour le vertical. NVENC gère ≥ 3 sessions (peur périmée levée). **Mesurer en jouant** (un jeu qui tourne) = l'ex-épreuve (d).
- **Fichiers** : `src-tauri/crates/engine/src/multistream.rs` · `src/features/multistream/*` · `src/features/health/*` (centre de santé F-106).
- **Tests TDG** : `should_open_n_outputs_when_multistream` · `should_report_per_platform_status` · `should_not_drop_frames_when_dual_encode` (banc, jeu qui tourne) · `should_confirm_hardware_codec_on_each_output`.
- **Critère d'acceptation** : N/N plateformes atteintes (aucun échec silencieux) · 0 image perdue par sortie · chute du jeu < 10 % (seuil CDC §6).
- **Vérité externe** : le motif de diffusion (prouvé B2) **répliqué** · le compteur d'images perdues (`obs_output_get_frames_dropped`, **prouvé** au spike) · réception vérifiée **côté serveur** (MediaMTX / plateforme).
- **Pré-vol** : B2 livrée et verte · un jeu disponible pour la mesure.
- **Autonomie** : 🟢 réplication d'un motif prouvé — dépend de B2 livrée.

## 7ter. Fiches exhaustives — VAGUE 2 (le cockpit interactif) *(ajouté 2026-07-17)*

> ⚠️ **Rédigées AVANT la construction de la vague 1.** À re-valider quand leur tour vient — bâtir
> B1-B3 peut les affiner (ADR-004). 🟢 vérité externe solide aujourd'hui · 🟡 un point à prouver/cadrer.

### B-shell — Coque cockpit (dockview) · Sensible · 🟢 (détachement 🟡)
- **Objectif** : coque à panneaux dock/onglets/redimension + modes Préparation/Live/Focus + presets + centre de santé (F-027, F-100, F-101, F-106). Héberge tous les écrans.
- **Approche décidée** : `dockview-react` (ADR-005, jamais un dock maison). Layouts `toJSON`/`fromJSON` → presets (persistés `plugin-store`). Empaquetée Lego `@shinkofa/ui`. Détachement 2ᵉ écran = `WebviewWindow` Tauri + sync `emit`/`listen` (jamais `BroadcastChannel`).
- **Fichiers** : `src/features/shell/{Cockpit.tsx, layout.ts, presets.ts}` · `src/features/health/*`.
- **Tests TDG** : `should_restore_layout_when_deserialized` · `should_switch_preset_when_selected` · `should_never_lose_panel_when_window_closed` (assertion §5).
- **Critère d'acceptation** : dock/onglets/resize OK · bascule preset OK · layout survit à un redémarrage.
- **Vérité externe** : doc **officielle** dockview-react (`toJSON`/`fromJSON`, prouvable par test) — 🟢. **Le détachement 2ᵉ écran dépend du spike B0.4** (non fait) → 🟡.
- **Autonomie** : 🟢 coque mono-fenêtre · 🟡 détachement (attendre B0.4).

### B-auto — Moteur d'automations · Critique · 🟢
- **Objectif** : automation = **donnée** (déclencheur → conditions → séquence), jamais du code exécuté (F-023, ADR-008). Expose l'interface consommée par B4/B5 (ADR-011).
- **Approche décidée** : modèle `{nom, déclencheur, conditions[], actions[], actif}` ; déclencheur = bouton|chat|événement|minuteur (attribut, ADR-012). Moteur d'évaluation **pur**. Détection de cycle **à l'enregistrement**. Refus **fermé** sur condition non évaluable. Exécution hors du fil UI, une tâche isolée par automation (Let It Crash). Sans réseau.
- **Fichiers** : `src-tauri/crates/automation/{model.rs, engine.rs, triggers.rs}` · `src/features/automations/*` (écran déjà maquetté).
- **Tests TDG** (Critique 95 % + propriétés + mutation) : `should_run_action_when_condition_true` · `should_refuse_when_condition_unevaluable` · `should_reject_cycle_at_save` · `should_reject_unknown_trigger_type` (assertion §5) · `should_never_expose_event_trigger_as_deck_key` (ADR-012).
- **Critère d'acceptation** : 5 assertions §5 tenues · anti-circulaire (mutation) sur le moteur d'éval.
- **Vérité externe** : le **fichier de données réel de Streamer.bot** (`refs-concurrence/`) = le modèle prouvé · logique pure vérifiable par propriétés/mutation (pas d'API externe). 🟢.
- **Autonomie** : 🟢 — logique déterministe. Excellent candidat (Critique → relecture modèle différent obligatoire).

### B4 — Deck local · Critique · 🟢 (après B-auto)
- **Objectif** : deck local-first (< 100 ms, sans réseau) ; une touche lance une action simple **ou une automation** (client de l'interface B-auto, ADR-011).
- **Approche décidée** : consomme l'interface du moteur (lister exposables · lancer avec args · s'abonner). 4 types de touches, palette, boards. Chemin local prioritaire.
- **Fichiers** : `src/features/deck/*` · `src-tauri/src/deck_bridge.rs`.
- **Tests TDG** : `should_trigger_action_under_100ms_when_pressed` · `should_work_when_offline` · `should_show_button_automation_as_key` (ADR-012).
- **Critère d'acceptation** : latence < 100 ms · marche sans réseau · automation à bouton d'office sur le deck.
- **Vérité externe** : l'interface B-auto (livrée avant) + mesure de latence. 🟢.
- **Autonomie** : 🟢 après B-auto.

### B5 — Pont VPS + deck distant + permissions · Critique · 🟡 (infra)
- **Objectif** : 2ᵉ client de la même interface (ADR-011) via pont VPS optionnel + permissions rôle fail-closed (F-047, F-048).
- **Approche décidée** : Phoenix côté pont (websocket), appairage QR, permissions **refus par défaut**. Jamais un passage obligé. Assertions §5 : session authentifiée avant action · origine appairée valide.
- **Fichiers** : pont `phoenix/*` (VPS) · `src/features/deck-remote/*` · `src-tauri/src/pairing.rs`.
- **Tests TDG** : `should_block_moderator_beyond_role` · `should_require_auth_before_action` · `should_reject_unpaired_origin`.
- **Critère d'acceptation** : modérateur bloqué au-delà de ses droits · appairage QR OK · le local reste autonome sans le pont.
- **Vérité externe** : specs Phoenix/websocket (officielles) + logique fail-closed (vérifiable). 🟡 la 1ʳᵉ mise en place du pont (infra, ports → consulter `Shinkofa-Infra`) mérite une validation humaine.
- **Autonomie** : 🟢 la logique permissions/appairage · 🟡 le déploiement du pont VPS.

## 7quater. Fiches exhaustives — VAGUE 3 (le live riche) *(ajouté 2026-07-17)*

> Même avertissement. Point de départ 🟡 : l'API libobs audio / transitions / caméra n'avait pas été
> explorée au spike (seuls diffusion + capture le sont).
>
> **✅ Veille faite le 2026-07-17 (source : dépôt libobs-rs)** : le pont expose la **création de source
> générique** (`obs_source_create` par id + réglages — comme le service RTMP du spike) ET l'**API de
> filtres** (`obs_source_filter_add`, `sources/filter.rs`). Conséquence : **B6 (audio) et B-cam
> (caméra) passent 🟢** — source `wasapi_input` / `dshow_input` + filtres (suppression bruit, sidechain,
> masque, retrait de fond) = transcriptibles. **B7 : 🟢 mouvements** (scene items + transforms prouvés)
> **· 🟡-léger transitions** (source de transition à activer — un appel à confirmer, pas un inconnu).

### B6 — Audio · Standard · 🟡 (API à confirmer)
- **Objectif** : mixage + filtres micro + suppression bruit + ducking + routage écoute/diffusion + waveforms (F-021, F-037, F-039).
- **Approche décidée** : sources/filtres audio libobs (suppression bruit = filtre NVIDIA/RNNoise, ducking = sidechain). Waveform = niveau réel lu du moteur.
- **Fichiers** : `src-tauri/crates/engine/src/audio.rs` · `src/features/audio/*`.
- **Tests TDG** : `should_apply_noise_suppression_when_enabled` · `should_duck_when_voice_detected` · `should_reflect_real_level_in_waveform`.
- **Critère d'acceptation** : bruit supprimé · ducking à la voix · waveform = niveau réel.
- **Vérité externe** : API filtres audio `libobs-wrapper` — **à confirmer par veille** (non explorée). 🟡.
- **Autonomie** : 🟡 — mini-veille de l'API d'abord, puis 🟢.

### B7 — Scènes avancées · Standard · 🟡 (API à confirmer)
- **Objectif** : transitions, mouvements, auto-move (F-029, F-038).
- **Approche décidée** : transitions via l'API scènes libobs ; mouvements = filtres/animations de sources.
- **Fichiers** : `src-tauri/crates/engine/src/scenes.rs` · `src/features/scenes/*`.
- **Tests TDG** : `should_apply_transition_when_switching` · `should_move_source_when_switch`.
- **Critère d'acceptation** : transition appliquée au switch · source déplacée.
- **Vérité externe** : API transitions `libobs-wrapper` — **à confirmer par veille**. 🟡.
- **Autonomie** : 🟡.

### B-cam — Caméra · Standard · 🟡 (API à confirmer)
- **Objectif** : caméra perso, masques (cercle), fond sans écran vert, cam mobile (F-024, F-036).
- **Approche décidée** : source dshow (webcam) + filtres (masque, retrait de fond NVIDIA/segmentation).
- **Fichiers** : `src-tauri/crates/engine/src/camera.rs` · `src/features/camera/*`.
- **Tests TDG** : `should_apply_circle_mask` · `should_remove_background_without_greenscreen`.
- **Critère d'acceptation** : masque cercle · fond retiré sans écran vert.
- **Vérité externe** : API dshow + filtres `libobs-wrapper` — **à confirmer**. 🟡.
- **Autonomie** : 🟡.

### B9 — Pré-vol + wizard + presets de scènes · Sensible · 🟢
- **Objectif** : détection matériel + réglage sûr + wizard + presets + feu vert pré-vol (F-002, F-003, F-005, F-010→F-012).
- **Approche décidée** : détecter la capacité (`available_video_encoders`, **API prouvée** au spike) → réglage sûr par défaut. Pré-vol = checks auto → Go Live.
- **Fichiers** : `src-tauri/src/preflight.rs` · `src/features/onboarding/*`.
- **Tests TDG** : `should_detect_available_encoders` · `should_pick_safe_default_when_detected` · `should_block_golive_when_precheck_fails`.
- **Critère d'acceptation** : matériel détecté (jamais présumé, F-003) · réglage sûr · feu vert fonctionnel.
- **Vérité externe** : l'API de détection d'encodeurs (**prouvée** au spike : `ENGINE:ENCODERS`) + les checks. 🟢.
- **Autonomie** : 🟢.

### B10 — Interaction : chat + modération + alertes · Sensible · 🟡 (API plateformes)
- **Objectif** : chat multi-plateforme + modération auto + inline + alertes + pop-up + bandeaux + objectifs (F-030→F-035).
- **Approche décidée** : connexions chat **officielles** par plateforme (Twitch IRC/EventSub, YouTube) ; modération inline (timeout/ban/épingler).
- **Fichiers** : `src-tauri/src/chat/*` · `src/features/{chat,alerts}/*`.
- **Tests TDG** : `should_timeout_user_from_message` · `should_raise_alert_when_event` · `should_merge_multiplatform_chat`.
- **Critère d'acceptation** : chat multi-plateforme fusionné · modération inline OK · alertes déclenchées.
- **Vérité externe** : les API **officielles** chat/EventSub des plateformes — **à confirmer par veille** (versions, scopes). 🟡.
- **Autonomie** : 🟡 — confirmer les API plateformes d'abord.

## 7quinquies. Fiches — VAGUES 4+ (finition, publication, avatar, livraison) *(ajouté 2026-07-17)*

> Rédigées d'avance ; re-valider au tour venu. Veille externe (API plateformes, libs avatar/cloud) =
> **à faire au démarrage** — elles bougent vite, les figer maintenant serait périmé (leçon Cross-Project).

### B8 — Kit de marque + propagation · Standard · 🟢
- **Objectif** : kit de marque (F-004, F-072) propagé aux overlays/clips/posts/miniatures.
- **Approche** : kit = **donnée JSON**, source unique consommée partout. Frontend + data.
- **Fichiers** : `src/features/brand/*` · `src-tauri/src/brand.rs`. **Tests** : `should_propagate_brand_to_all_surfaces`.
- **Vérité externe** : logique de propagation (déterministe, testable), pas d'API externe. 🟢.

### B11 — Marqueurs + clips + replay + sous-titres · Standard/Sensible · 🟢 (sous-titres 🟡→B0.1)
- **Objectif** : marqueurs → clips, replay instantané, chapitres, sous-titres live (F-040→F-045).
- **Approche** : marqueurs horodatés → **FFmpeg** (découpe) ; replay = **tampon circulaire libobs** (`replay_buffer`, **prouvé présent** : `libobs-simple/output/replay.rs`) ; sous-titres live = whisper.cpp (**spike B0.1**).
- **Fichiers** : `src-tauri/crates/engine/src/replay.rs` · `src-tauri/src/editing/{markers,clips,ffmpeg}.rs` · `src/features/editing/*`.
- **Tests** : `should_cut_clip_from_marker` · `should_replay_instantly` · assertion §5 (borne début < fin).
- **Vérité externe** : API `replay_buffer` (dépôt libobs) + FFmpeg (officiel). 🟢 · sous-titres 🟡 (B0.1).

### B12 — Publication native + planning + miniatures + pont Kobo · Sensible · 🟡 (API plateformes)
- **Objectif** : publier + planifier + miniatures + infos diffusion + pont Kobo (F-050→F-054).
- **Approche** : upload via API **officielles** (YouTube Data, Twitch) ; OAuth **réutilisé de B2** ; jeton relu frais à chaque publication (assertion). Pied de description constant par marque.
- **Fichiers** : `src-tauri/src/publish/*` · `src/features/publish/*`. **Tests** : `should_refresh_token_before_publish` · `should_target_correct_platform`.
- **Vérité externe** : API upload **officielles** — **veille au démarrage** (quotas, scopes). 🟡.

### B13 — Avatar VRM étape 1 (Spout2) · Standard · 🟡 (source Spout2)
- **Objectif** : avatar VRM via source externe (Spout2).
- **Approche** : source Spout2 en entrée du moteur (création de source générique par id, mécanisme vérifié).
- **Fichiers** : `src-tauri/crates/engine/src/spout.rs` · `src/features/avatar/*`. **Tests** : `should_capture_spout_source`.
- **Vérité externe** : id/plugin Spout2 pour OBS — **veille au démarrage**. 🟡.

### B14 — Avatar VRM étape 2 (MediaPipe + three-vrm) · Standard · 🟡 (libs)
- **Objectif** : avatar natif (MediaPipe → mapper maison → three-vrm ; Kalidokit déprécié).
- **Approche** : webcam → MediaPipe (blendshapes) → three-vrm dans le front (3D, expertise Takumi).
- **Fichiers** : `src/features/avatar-native/*`. **Tests** : rendu + mapping (visuel).
- **Vérité externe** : versions MediaPipe / three-vrm — **veille au démarrage**. 🟡.

### B15 — Morphique + palette Ctrl+K + WCAG · Standard · 🟢 (réutilise)
- **Objectif** : morphique (densité/police/langue/contraste) + palette Ctrl+K + WCAG 2.2 AA + widget feedback (F-006, F-070, F-105, F-107→109).
- **Approche** : **réutilise le Module Morphique** de l'écosystème (ADR-006, jamais réécrit) ; palette = index d'actions/écrans filtrable.
- **Fichiers** : `src/features/morphic/*` (import) · `src/features/command-palette/*`. **Tests** : `should_persist_preference` · `should_reach_action_from_palette` · axe-core 0 violation.
- **Vérité externe** : le Module Morphique existant (Lego) + axe-core. 🟢.

### B16 — Contrôles rapides + caméra virtuelle + don · Standard · 🟢
- **Objectif** : mute micro · confidentialité écran · silence alertes 1 clic (toujours visible) · caméra virtuelle · co-stream · don discret (F-028, F-046, F-090→093).
- **Approche** : caméra virtuelle = **sortie virtualcam** de libobs (output générique, API prouvée) ; le reste = frontend + commandes moteur.
- **Fichiers** : `src/features/quick-controls/*` · `src-tauri/crates/engine/src/virtualcam.rs`. **Tests** : `should_mute_mic_when_toggled` · `should_silence_all_alerts_in_one_click`.
- **Vérité externe** : API output libobs (prouvée) + logique frontend. 🟢.

### B-dash — Dashboard d'accueil · Standard · 🟢
- **Objectif** : chiffres clés + derniers streams + à venir (F-102). Frontend, lit B-stats.
- **Fichiers** : `src/features/dashboard/*`. **Tests** : `should_show_kpis_and_recent_streams`. **Vérité externe** : données locales. 🟢.

### B-settings — Écran Paramètres unifié · Sensible · 🟢
- **Objectif** : onglets comptes/périph/encodage/deck+appairage/marque/stockage/à-propos (F-103).
- **Fichiers** : `src/features/settings/*`. **Tests** : réglages persistés. **Vérité externe** : `plugin-store` (local). 🟢.

### B-cloud — Espace cloud utilisateur + archivage · Sensible · 🟡 (OAuth fournisseurs)
- **Objectif** : Drive/Dropbox/OneDrive/S3-WebDAV ; archivage post-live vers le dossier **de l'utilisateur** (Hikari n'héberge rien, ADR-007).
- **Approche** : rclone (ou équiv.) ; OAuth par fournisseur ; assertion (fournisseur ∈ liste · jeton non expiré).
- **Fichiers** : `src-tauri/src/cloud/*` · `src/features/cloud/*`. **Tests** : `should_archive_to_user_folder`.
- **Vérité externe** : API OAuth par fournisseur — **veille au démarrage**. 🟡.

### B-stats — Écran Suivi · Standard · 🟢 (viewers 🟡)
- **Objectif** : stats lives/clips + stabilité & débit + compteur viewers (F-060→062).
- **Approche** : débit/stabilité **lus du moteur** (source unique, prouvé) ; stats persistées localement ; viewers via API plateformes (dégradation propre si indispo — jamais un zéro trompeur).
- **Fichiers** : `src/features/tracking/*` · `src-tauri/src/stats.rs`. **Tests** : `should_report_bitrate_from_engine` · `should_degrade_gracefully_when_platform_down`.
- **Vérité externe** : stats moteur (prouvées) 🟢 · compteur viewers = API plateformes 🟡 (veille).

### B-pack — Installation unique · Sensible · 🟡-léger (bundling + ex-épreuve e)
- **Objectif** : empaquetage Tauri + moteur OBS embarqué (`libobs-bootstrapper`) + somme de contrôle + 1ère ouverture sur machine vierge (F-001).
- **Approche** : bundler Tauri (Windows d'abord) ; stratégie embarqué vs téléchargé **tranchée à l'ex-épreuve B0.0(e)** (à faire) ; somme de contrôle **avant** d'exécuter un binaire téléchargé (assertion).
- **Fichiers** : `src-tauri/tauri.conf.json` (bundle) · `src-tauri/src/bootstrap.rs`. **Tests** : machine vierge sans OBS → install → 1ère ouverture réussie.
- **Vérité externe** : bundler Tauri (officiel) + crate `libobs-bootstrapper`. 🟡-léger.

### Toutes les briques de production sont détaillées
Les **25 briques de production** ont désormais une fiche à qualité autonome (🟢) ou un cadrage honnête (🟡 + veille au démarrage). Le PET est **exécutable de bout en bout**.

### Références d'approche (héritées — désormais couvertes par les fiches ci-dessus)
- Scope, approche, tests et critères **cadrés** par le CDC (§3 fonctions, §7 risques, §8 FMEA) et la roadmap §6.
- **Détail exhaustif figé quand leur vague approche** — le figer maintenant = deviner sur des décisions que la construction des vagues 1-2 va trancher (ADR-004, anti-sur-ingénierie).
- Approches déjà décidées, indépendantes du moteur :
- Approches déjà décidées, indépendantes du moteur :
  - **B4/B5 deck** : Phoenix côté pont VPS, protocole websocket, permissions rôle fail-closed (refus par défaut), chemin local prioritaire sans serveur.
  - **B8 marque** : kit stocké en donnée structurée (JSON) = source unique consommée par overlays/clips/posts/miniatures.
  - **B11 édition** : marqueurs (auto + manuels) horodatés → FFmpeg pour la découpe ; replay = tampon circulaire.
  - **B12 publication** : jeton OAuth relu frais en base à chaque publication (jamais figé au boot) ; pied de description constant par marque.
  - **B13/B14 avatar** : étape 1 = Spout2 comme source ; étape 2 = MediaPipe → mapper maison → three-vrm (Kalidokit déprécié).
  - **B-shell coque** : dockview-react (React 19) ; dispositions sérialisées `toJSON`/`fromJSON` → presets Préparation/Live + presets utilisateur (persistés via `plugin-store`) ; **détachement 2ᵉ écran** = `WebviewWindow` Tauri + sync `emit`/`listen` (jamais `BroadcastChannel`), ré-intégration auto à la fermeture ; empaqueté en **Lego `@shinkofa/ui`**. Dérisqué par B0.4.
  - **B-settings** : écran à onglets, réglages persistés localement ; l'onglet Deck porte l'appairage (QR) + droits par appareil.
  - **B-cloud** : rclone (ou équiv.) ; OAuth par fournisseur ; l'archivage post-live copie le VOD vers le **dossier cloud de l'utilisateur** — Hikari n'héberge rien (CDC §4).
  - **B15 morphique** : réutilise le **Module Morphique de l'écosystème** (jamais réécrit) ; palette Ctrl+K = index d'actions/écrans filtrable.
  - **B-auto moteur d'automations** *(ajouté 2026-07-16)* : automation = **donnée structurée** (déclencheur → conditions → séquence d'actions), **jamais du code utilisateur exécuté** — c'est ce qui sépare Hikari d'un Streamer.bot scriptable (CDC §13 anti-pattern #4). Moteur d'évaluation **pur et testable** (mêmes entrées → même décision), donc soumis au test par propriétés (couche 1 anti-circulaire). Exécution des actions **hors du fil de l'interface**, une automation par tâche isolée (« Let It Crash », CDC §4) : une automation qui plante n'emporte ni le live ni les autres. Détection de cycle **à l'enregistrement** (le graphe est connu d'avance), pas à l'exécution. Refus **fermé par défaut** sur condition non évaluable. Tourne **sans réseau** (dépend de B4, jamais de B5).
  - **B-auto × B4 — le déclencheur est un attribut, pas une nature** *(ajouté 2026-07-16, ADR-011)*. Le modèle :

    ```
    automation = { nom, déclencheur, conditions[], actions[], actif }
    déclencheur = bouton | commande chat | événement | minuteur
    ```

    Conséquence, **une seule règle** au lieu de deux modèles :

    | Déclencheur | Sur le deck ? | Pourquoi |
    |---|---|---|
    | **bouton** | **oui — automatiquement** | le bouton EST le déclencheur ; la touche est proposée à l'assignation |
    | commande chat · événement · minuteur | non par défaut | quelqu'un/quelque chose d'autre déclenche |

    L'automation **ignore qui l'a déclenchée** — elle lit seulement les arguments déposés. Modèle vérifié par rétro-ingénierie de Streamer.bot (`refs-concurrence/Analyse-Streamerbot-TouchPortal.md` §2), qui l'applique sur ~350 types de déclencheurs. **Option explicite** : une automation non-manuelle peut être exposée au deck (case « aussi sur le deck ») — elle gagne alors un 2ᵉ déclencheur, sans changer de nature.
    **Test qui garde la règle** (Beyoncé rule) : une automation à déclencheur « événement » ne doit **jamais** apparaître d'office dans les touches assignables.
  - **B-stats suivi** *(ajouté 2026-07-16)* : débit et stabilité (F-061) **lus depuis le moteur**, jamais recalculés ailleurs (source unique) ; compteur viewers (F-062) via les interfaces officielles des plateformes, dégradation propre si une plateforme ne répond pas (afficher « indisponible », jamais un zéro trompeur) ; stats lives/clips (F-060) persistées localement. **Recoupe F-106** (centre de santé, B-shell) : F-106 = état *par plateforme* dans la coque ; B-stats = l'écran Suivi qui historise. Une seule source de mesure alimente les deux.
  - **B-pack installation** *(ajouté 2026-07-16)* : empaquetage Tauri (installeur Windows d'abord, Linux ensuite — CDC §6 portabilité). Stratégie moteur embarqué vs téléchargé **tranchée en B0.0(e)**. **Somme de contrôle obligatoire avant d'exécuter tout binaire téléchargé** (FMEA CDC §8). Test d'acceptation = **machine vierge sans OBS installé** → installation → première ouverture réussie (la promesse F-001 « zéro logiciel tiers » se prouve là, jamais sur la machine de dev).

## 8. Détection PII (données personnelles)

- **Outils** : Gitleaks (secrets) + revue manuelle sur logs et exports.
- **Portée** : jetons OAuth (coffre système, jamais loggés) · widget feedback (zéro PII) · config exportable (aucune donnée identifiante).
- **Auto vs manuel** : Gitleaks pré-commit (auto) ; revue humaine sur tout nouveau log/export (manuel).
- **Règle absolue** : aucune donnée personnelle écrite dans un fichier, log, commit ou artefact (Confidentiality.md).

## 9. Portes de qualité pré-commit (par brique)

**Régime normal — toute brique de production** :

- [ ] Couverture atteinte (80/90/95 selon niveau CDC §7)
- [ ] Lint zéro erreur (Biome TS · Clippy Rust · Credo Elixir)
- [ ] Tests verts (commande réelle, exit 0)
- [ ] Sécurité : zéro secret, jetons au coffre, permissions testées
- [ ] Accessibilité : 0 violation axe-core (UI), reduced-motion respecté
- [ ] Cross-OS (Windows d'abord, Linux ensuite)
- [ ] Veille émise (versions re-vérifiées le jour du dev)
- [ ] Confidentialité : zéro donnée personnelle dans le diff

### 9bis. Régime SPIKE — briques B0.x uniquement *(ajouté 2026-07-16)*

**Pourquoi ce régime existe.** Les briques B0.0/B0.1/B0.2/B0.4 sont des **spikes de dérisquage** :
du code **jetable**, écrit pour **répondre à une question**, jamais pour être livré. Le régime normal
leur est inapplicable, et le prouver est simple : B0.0 est classé **Critique** (parce que le *moteur*
l'est), ce qui exigerait 95 % de couverture et zéro violation d'accessibilité **sur un banc d'essai
qu'on jette le lendemain**. Appliquer ça ne produirait pas de la qualité — ça produirait du
contournement, ou pire, un spike qu'on garde « parce qu'il est testé ».

| Règle normale | Statut sur un spike | Pourquoi |
|---|---|---|
| Tests AVANT le code (TDG, §1) | **suspendue** | Un spike explore une question ouverte : on ne peut pas écrire le test d'une réponse inconnue. Les **critères d'acceptation chiffrés** (§7) jouent ce rôle — écrits **avant**, et mesurables. |
| Couverture 80/90/95 (§9) | **suspendue** | Code jetable. Aucun chiffre de couverture ne rend un spike plus concluant. |
| Accessibilité axe-core | **sans objet** | Pas d'interface utilisateur dans un spike moteur. |
| Cross-OS | **sans objet** | Le spike tourne sur la machine cible (§7 prérequis), c'est le but. |
| Lint zéro erreur | **allégée** → avertissements tolérés | Le lint sert la maintenance ; un spike n'est pas maintenu. |
| Veille émise | **MAINTENUE** 🔒 | La version est **l'objet même** du spike (leçon ADR-010). |
| Sécurité : zéro secret | **MAINTENUE** 🔒 | Un secret commité est définitif, même dans du jetable. |
| Confidentialité | **MAINTENUE** 🔒 | Absolue, sans exception (Confidentiality.md). |

**Ce que le régime spike EXIGE en échange (non négociable)** :

- [ ] **Critères d'acceptation chiffrés écrits AVANT** de coder (§7) — ils remplacent les tests.
- [ ] **Mesures brutes conservées** (logs, relevés, captures) — le go/no-go se prouve, ne s'affirme pas (Monozukuri #5).
- [ ] **Verdict écrit** dans la fiche de la brique (§7) : go / no-go + **le chiffre qui tranche**.
- [ ] **Durée bornée respectée** ou arrêt + escalade à Jay (un spike qui déborde EST un signal).
- [ ] **Le code du spike ne devient jamais du code de production** — il est archivé, jamais promu. S'il s'avère bon, il est **réécrit** sous régime normal.

> **Frontière stricte** : le régime spike s'arrête à B0.x. **B0.3 (scaffold) est déjà du régime
> normal** — c'est le socle de l'application, il est gardé.

## 10. Vérification post-déploiement

- Feu vert pré-vol fonctionnel (checks auto → Go Live).
- Deck local joignable sans réseau · deck distant via pont VPS + permissions respectées.
- Multistream : chaque plateforme cible atteinte (N/N), pas d'échec silencieux.
- Reconnexion auto testée (coupure réseau simulée).
- Widget feedback opérationnel (2 clics, contexte auto, zéro PII).
- Session longue : mémoire/CPU stables.

## 11. Risques rencontrés en exécution

*(À remplir au fil du travail — distincts de la FMEA prévisionnelle du CDC §8.)*

## 12. Décisions architecturales (ADR-light)

- **ADR-001 (2026-07-11)** : Tauri + Rust pour l'**isolation des pannes** (raison fondatrice Jay) — un bug n'immobilise plus l'utilisateur. Electron écarté sauf en repli moteur.
- **ADR-002 (2026-07-11)** : Deck mobile à **deux chemins** — local (défaut, sans serveur) + distant (pont VPS optionnel). Le local marche toujours seul.
- **ADR-003 (2026-07-11)** : Édition **essentielle native**, avancée via pont Kobo.
- **ADR-004 (2026-07-11)** : PET raffiné en version exhaustive **après** le go/no-go du spike moteur (les deux branches pré-décidées en attendant).
- **ADR-005 (2026-07-12)** : Cockpit bâti sur **dockview-react** (lib de dock mature), jamais un moteur de dock maison — l'ancien Hikari avait codé ~6720 lignes de dock jamais branchées. Empaqueté en Lego `@shinkofa/ui`.
- **ADR-006 (2026-07-12)** : **Module Morphique réutilisé** de l'écosystème (brique partagée), jamais réécrit — densité/sensoriel/thème/police/langue.
- **ADR-007 (2026-07-12)** : Archivage vers le **cloud de l'utilisateur** (Drive/Dropbox/OneDrive/S3-WebDAV) — Hikari orchestre, n'héberge rien.
- **ADR-008 (2026-07-16)** : **Une automation est une donnée structurée, jamais du code exécuté.** Déclencheur → conditions → séquence, décrits en données. Pourquoi : un moteur de script utilisateur ouvre une surface d'exécution impossible à borner et reproduit la fragilité de Streamer.bot (la douleur fondatrice, CDC §4). En données, le graphe est connu d'avance → cycles détectables à l'enregistrement, moteur d'évaluation pur et testable par propriétés. Conséquence : F-023 classée **Critique** (CDC §7).
- **ADR-009 (2026-07-16)** : **Stratégie d'installation tranchée au spike B0.0, pas en fin de route.** Embarquer OBS dans l'installeur ou le télécharger à la première ouverture (`libobs-bootstrapper`) change la taille du paquet et la surface de sécurité. B0.0 mesure déjà la taille du bundle → la question s'y décide au moindre coût. Un binaire téléchargé exige une **somme de contrôle vérifiée avant exécution** ; si le bootstrapper n'en expose pas, l'embarqué devient obligatoire.
- **ADR-010 (2026-07-16)** : **La source de vérité d'une version est l'API du registre** (crates.io, npm), jamais un site de documentation. Pourquoi : la veille du 2026-07-11 a lu docs.rs, gelé sur `libobs-wrapper` 3.0.3 (ses builds récents échouent), et a fait entrer dans le CDC un chiffre **faux de 6 versions majeures** — non détecté 5 jours, sur le composant même du go/no-go. Vaut pour toute veille du projet.
- **ADR-011 (2026-07-16)** : **Le moteur expose une interface interne stable ; le deck n'est qu'un client.** Le moteur d'automations offre trois opérations — *lister les automations exposables · en lancer une (avec arguments) · s'abonner aux événements*. Le **deck local** (B4) et le **deck distant** (B5) sont deux clients de cette même interface. **Pourquoi** : (1) zéro logique dupliquée entre local et distant — donc zéro dérive entre les deux ; (2) c'est le modèle prouvé de Streamer.bot, dont le deck officiel et les greffons tiers passent tous par la même interface (analyse concurrence §2, §6) ; (3) ça rend le deck remplaçable sans toucher au moteur. **Corollaire (CDC §13 anti-pattern #4)** : cette interface vit **dans l'application**, jamais derrière le pont VPS — le deck local doit marcher sans réseau. Le pont distant est un client de plus, pas un passage obligé.
- **ADR-012 (2026-07-16)** : **Le déclencheur est un attribut de l'automation, pas une nature.** Un clic de bouton, une commande de chat, un événement et un minuteur sont le même mécanisme ; l'automation ignore qui l'a déclenchée. **Pourquoi** : sans ça, « les automations » et « les boutons du deck » deviennent deux modèles à maintenir en parallèle, avec deux endroits où corriger un bug. Vérifié par rétro-ingénierie (le fichier de données réel de Streamer.bot stocke `triggers[]` comme un simple attribut de l'action). **Conséquence produit** : une automation à déclencheur « bouton » apparaît **d'office** comme touche assignable ; les autres non, sauf demande explicite.
- **ADR-013 (2026-07-17)** : **Le moteur vidéo tourne dans un PROCESSUS SÉPARÉ, jamais dans l'application.** L'app lui parle par un tuyau. **Pourquoi** : (1) **c'est prouvé** — `league_record` le fait depuis mars 2022 (Tauri + Rust + moteur d'OBS, application livrée, binaires téléchargés) via ses modules `intprocess-recorder` + `ipc-link` + le binaire `extprocess_recorder` ; (2) ça **contourne** la friction async au lieu de la combattre — un moteur qui ne partage pas notre fil ne peut pas geler notre interface, et le README du pont dit noir sur blanc que « la fonctionnalité async a été retirée à cause de toutes sortes de problèmes » ; (3) **c'est l'ADR-001 rendu réel** — la raison fondatrice de Jay était d'isoler les pannes ; un processus séparé est l'isolation la plus forte qui existe : le moteur peut mourir, l'app survit et le relance. **Conséquence** : le spike B0.0 teste cette forme, il ne la découvre pas. **Coût connu** : un tuyau à maintenir, et la latence qu'il ajoute (à mesurer).
- **ADR-014 (2026-07-17)** : **Le plancher matériel d'Hikari = plancher publié d'OBS + notre surcoût mesuré.** **Pourquoi** (correction de cadrage de Jay) : mesurer « ça marche sur la machine de Jay » ne sert presque à rien — Hikari doit tourner chez n'importe qui, et une machine est **un point**, jamais une courbe. En revanche, **le surcoût par rapport à OBS nu est transférable** : si on coûte X % de plus qu'OBS à travail égal, ce X vaut sur toutes les machines. OBS publie ses exigences et a dix ans de terrain → on **hérite** de son plancher, on mesure seulement ce qu'on **ajoute**. **Conséquences** : (1) toute épreuve de performance exige une **mesure de référence sur OBS nu**, sinon elle ne parle que de la machine de test ; (2) le code **détecte** la capacité matérielle à l'exécution, il ne la **présume** jamais (F-003) ; (3) la vraie matrice matérielle (AMD, Intel, sans encodeur) vient des **premiers utilisateurs**, jamais d'un spike. **Amendement 2026-07-17 (Jay)** : la mesure du surcoût vs OBS se fait sur l'**application finie**, jamais sur un spike nu — le coût d'un spike n'est pas le coût du produit. B0.0 a mesuré le coût *absolu* d'Hikari (faible) et prouvé la faisabilité ; la comparaison vs OBS est reportée à la fin du développement.

## 13. Déviations vs CDC

*(Suivies ici ; si permanentes → mettre à jour le CDC.)*

| Date | Déviation | Statut |
|---|---|---|
| 2026-07-17 | **Surcoût vs OBS nu (c) mesuré en fin de développement**, pas au spike — le coût pertinent est celui de l'app finie, pas d'un spike nu (décision Jay). Amende la méthode de l'ADR-014. | actif |
| 2026-07-17 | **Seuil « surcoût < 20 % CPU » à revoir** : avec NVENC le coût est sur le GPU, le CPU est quasi nul. Le juge sera GPU/encodeur, pas le seul CPU. | à trancher (fin de dev) |
| 2026-07-17 | Épreuves (a) sceau 5 min/Twitch, (d) double encodage, (e) taille d'install **différées** à leur brique (d↔B3, e↔B-pack). | différé |

## 14. Journal de session

| Date | Session | Scope |
|---|---|---|
| 2026-07-11 | Takumi 002 | `/concevoir Hikari Stream` — CDC + PET créés (conception complète). Exhaustivité PET à finaliser post-spike B0.0. |
| 2026-07-12 | Takumi 001 (suite) | Prototype visuel (`Mockup-Hikari-Stream.html`) construit et validé → CDC v1.1.0 + **PET v1.1.0** synchronisé : traçabilité F-100→109, briques B0.4/B-shell/B-dash/B-settings/B-cloud, assertions cloud+détachement, ADR-005→007. |
| 2026-07-16 | Takumi 002 | **Audit avant dev + passe de correction → CDC v1.2.0 + PET v1.2.0.** Contrôle croisé des 64 fonctions → **7 orphelines** rattachées (3 briques neuves : **B-auto** Critique, **B-stats**, **B-pack** ; 4 rattachements : F-005→B9, F-027→B-shell, F-028→B16, F-037→B6). **Veille refaite** : `libobs-wrapper` 3.0.3 → **9.0.4+32.0.2** (chiffre faux lu sur docs.rs) ; 5 autres lignes re-contrôlées exactes. Risque moteur réévalué sur faits datés (vrai risque = **dépendance à un seul auteur**, pas l'immaturité). CDC §7 (2 modules classés) + §8 (2 analyses de pannes) complétés. ADR-008→010. |
| 2026-07-16 | Takumi 002 (suite) | **Lien automation ↔ deck posé → PET v1.3.0.** Nourri par une analyse concurrence (recherche datée + **rétro-ingénierie du fichier de données réel de Streamer.bot**) → `refs-concurrence/Analyse-Streamerbot-TouchPortal.md`. **ADR-011** (le moteur expose une interface, le deck en est un client) + **ADR-012** (le déclencheur est un attribut, pas une nature). Sens de la dépendance **corrigé** : B-auto avant B4, et non l'inverse. Assertion ajoutée (type de déclencheur ∈ ensemble fermé). Origine : question de Jay — « certaines automations ont besoin d'un bouton, d'autres non ». |
| 2026-07-17 | Takumi 002 (suite) | 🔄 **Le pari technique tombe → PET v1.4.0.** Recherche de contre-exemple **demandée par Jay** : `league_record` (Rust + Tauri + moteur d'OBS, **livré depuis mars 2022**) + Cap + 4 autres. « Aucune app en production » = **faux, jamais vérifié**. Leur architecture = **moteur en processus séparé** (`ipc-link` + `extprocess_recorder`) → **ADR-013** : ça contourne la friction async **et** réalise l'isolation des pannes de l'ADR-001. **B0.0 réécrit** : de « go/no-go » à « mesure », 2 j → 1 j, épreuve reine = **la diffusion en direct** (seul inconnu : personne n'a croisé Rust + diffusion). **Correction de cadrage de Jay** : un spike sur sa machine ne sert pas les autres → **ADR-014**, on mesure le **surcoût vs OBS nu** (transférable), plancher = celui d'OBS + surcoût, et la matrice matérielle viendra des utilisateurs. `Veille-Technique.md` marqué **périmé** (source de l'erreur 3.0.3 + « aucune app en prod » + « réutiliser l'ancien repo »). Mémoire Shinzo : `rare-n-est-pas-impossible`. |
| 2026-07-16 | Takumi 002 (suite) | **Écran Automations maquetté** (`Mockup-Hikari-Stream.html`) — le trou relevé à l'audit : F-023 était le différenciateur du projet sans aucun écran. Livré : entrée de menu (groupe Produire, collée au Deck), liste des automations, chaîne **Quand → Si → Alors** lisible en français, bandeau des 4 garde-fous, 3 langues. La maquette **applique ADR-008** : les automations y sont une donnée que l'écran lit et dessine (`AUTOS`), jamais du balisage figé. Vérifié au navigateur : 5 automations, bascule au clic, 0 erreur. Reste à valider par Jay (placement dans le menu). |
| 2026-07-18 | Takumi (session dév) | 🧱 **B0.3 LIVRÉ (`fc1b278`, sur `main`).** Scaffold Tauri 2.11 + React 19.2 + Vite 7 + TS 5.8 strict + Tailwind 4.3 + Biome 2.5 + Vitest 4.1 ; socle pur ; tous verts (front + `cargo build`/`clippy`). Combo stable (Vite 8/TS 7 reportés). Dette : jsdom+RTL retirés (incompat `act` React 19.2) → test interactif recâblé en B1. Prochain brique autonome : B1a. |
| 2026-07-17 | Takumi (session dév) | **Passe d'exhaustivité TERMINÉE (§7quinquies) + veille libobs.** 12 dernières briques détaillées (B8, B11-B16, B-dash/settings/cloud/stats/pack). Veille pont : source générique + filtres + replay buffer → B6/B-cam/B7-mouvements → 🟢. Les 25 briques de prod ont une fiche autonome ou un cadrage 🟡. PET exécutable de bout en bout. Version 1.7.0 → 1.8.0. |
| 2026-07-17 | Takumi (session dév) | **Passe d'exhaustivité vagues 2 & 3 (§7ter, §7quater).** B-shell/B-auto/B4/B5 (cockpit) + B6/B7/B-cam/B9/B10 (live riche). Drapeaux honnêtes : vague 3 majoritairement 🟡 (API libobs audio/transitions/caméra non prouvée au spike → à confirmer par veille). Version 1.6.0 → 1.7.0. |
| 2026-07-17 | Takumi (session dév) | **Passe d'exhaustivité vague 1 (§7bis).** Fiches autonomes B0.3/B1/B2/B3 (7 champs + vérité externe). **B1 scindé** B1a/B1b (aperçu cross-process = mini-spike). Le PET devient exécutable en autonome, brique par brique, sur le chemin critique. Version 1.5.0 → 1.6.0. |
| 2026-07-17 | Takumi (session dév) | 🧱 **B0.0 EXÉCUTÉ → GO branche A.** Scaffold workspace 2 processus (Rust **stable**, nightly écarté). **(a)** diffusion RTMP NVENC prouvée (reçue par MediaMTX) · **(b)** survie + relance du moteur prouvée des 2 côtés · **(c)** coût Hikari mesuré (CPU 0,8 % / GPU 27 % / RAM 487 Mo). Comparaison vs OBS + (d)/(e) **différées fin de dev** (décision Jay). Commits `78bde90`→`eb08e3e`. Preuves : `spikes/b0.0-libobs/mesures/`. |
