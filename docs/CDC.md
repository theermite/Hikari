---
title: Hikari Stream — CDC (Cahier des charges)
created: 2026-07-11
updated: 2026-07-16
status: validated
type: cdc
version: 1.3.0
project: Hikari Stream
---

# Hikari Stream — CDC (intention)

> **Intention figée.** Conçu via `/concevoir` le 2026-07-11 (session Takumi), section par
> section, validé par Jay. L'exécution vivante est dans `PET.md` (le CDC ne référence pas le PET).
> Sources amont : `Vision-Cadrage.md`, `Veille-Technique.md`, `README.md` + 5 regards experts
> (base de connaissances, UX ND, réalité streamer, identité de marque, veille oublis 2026-07-11).
>
> **v1.1.0 (2026-07-12)** : enrichi par le prototype visuel `Mockup-Hikari-Stream.html` — désormais
> **référence de charte graphique** (thème sombre, accent ambre `#f5b642`, hairlines, panneaux flottants
> arrondis façon Telegram/Discord 2026, typo Inter). Le prototype a fait émerger : routing audio par piste,
> modèle de deck détaillé, cockpit réorganisable + multi-écran + modes de disposition, écran Paramètres
> unifié, connexion cloud utilisateur, palette de commandes, centre de santé du stream, morphique
> (police/langue/contraste). Sources veille : Streamer.bot + TouchPortal (2026-07-11), navigation UI 2026,
> dockview-react.
>
> **v1.2.0 (2026-07-16)** : passe d'audit avant lancement du dev (session Takumi 2026-07-16-002).
> Corrections : veille moteur refaite (`libobs-wrapper` 3.0.3 → **9.0.4+32.0.2** — le 3.0.3 venait d'une
> page docs.rs périmée, jamais de crates.io) · risque moteur réévalué sur faits datés ·
> `libobs-bootstrapper` ajouté (sert F-001) · **automations (F-023) classées Critique** + analyse de
> pannes ajoutée (§7, §8) — déclarées en §3 mais absentes de la classification et de l'analyse ·
> installation (F-001) classée Sensible. **Aucune fonction ajoutée ni retirée.**

---

## §1 — POUR QUOI (les 3 couches)

**L3 — La vision (le pourquoi profond)**
Hikari sert la voie Shinkofa : le numérique qui s'adapte à l'humain. Il incarne « code
invisible, impact réel » — la complexité pro d'un stream cachée sous une interface limpide,
adaptée au cerveau de chacun (dont neuro-atypique). Il libère le créateur de la charge mentale
qui l'épuise, pour qu'il **streame l'esprit tranquille**.

**L2 — La visibilité (comment ça attire)**
Positionnement magnétique : « le seul cockpit qui couvre tout le parcours — du premier clic au
clip publié — pensé pour ne jamais t'épuiser. » Preuve sociale = Jay l'utilise en public (The
Ermite), open-source, gratuit. Découverte **passive** (voir §12), jamais de campagne poussée.

**L1 — La première action**
Écrire le CDC + le PET, puis le **spike de dérisquage** (1-2 j) sur le pont moteur `libobs-rs`
**avant** toute décision de dev. Rien n'est codé avant que le moteur soit prouvé.

---

## §2 — Utilisateurs cibles

**Cible principale : Jay lui-même** (D12 « build for me first »). Streame LoL / Dofus sur Twitch
+ YouTube, marque « The Ermite ». Profil neuro-atypique — l'app doit tenir pour SON cerveau d'abord.

**Cible élargie : grand public de streamers**, du débutant à l'expert.

| Persona | Qui | Douleur principale | Ce que Hikari lui garantit |
|---|---|---|---|
| **Léa la débutante** | Jamais touché OBS, peur de mal faire | Canvas vide, jargon, peur du direct raté | Wizard rassurant, réglage sûr par défaut, feu vert |
| **Marc le confirmé** | OBS + 4 outils, épuisé par le jonglage | Fatigue outils, burnout, tout refaire à la main | Un seul cockpit, du live au clip publié |
| **Sam l'expert ND** | Veut tout personnaliser, surchargé | Surcharge sensorielle + cognitive en direct | Densité qui se déplie, contrôle sensoriel total |

**Persona neuro-atypique = transversal**, pas une case. Les garde-fous (charge cognitive,
contrôle sensoriel, prévisibilité, feu vert) servent tout le monde — ils calment ceux qui en ont
besoin sans brider les autres.

**Le viewer** = utilisateur indirect, juge final : reçoit un contenu de qualité, aligné, jamais
traité comme un produit (Dignité).

---

## §3 — Fonctionnalités

Organisées selon le parcours 0→6 + boucle. Identifiants `F-XXX`.

### Étape 0 — Socle (une fois)
| ID | Fonction |
|---|---|
| F-001 | Installation unique (moteur d'OBS embarqué, zéro logiciel tiers) |
| F-002 | Wizard d'accueil (confort sensoriel avant identité, sortie possible à tout moment) |
| F-003 | Détection matériel + réglage sûr par défaut |
| F-004 | Kit de marque (palette, typo, logo, signature de mouvement, ton verbal — source unique) |
| F-005 | Presets de scènes (modifiables, jamais un mur) |
| F-006 | Collections de scènes (« setup LoL », « setup interview » basculables d'1 clic) |
| F-006b | Sauvegarde / export de la config (portabilité + filet anti-crash) |

### Étape 1 — Pré-vol (chaque live)
| ID | Fonction |
|---|---|
| F-010 | Vérifications auto (micro, caméra, connexion, encodage) |
| F-011 | Test privé (aperçu réel sans diffuser) |
| F-012 | Feu vert (« Go Live » bloqué tant que tout n'est pas vert, raison affichée) |

### Étape 2 — Live
| ID | Fonction |
|---|---|
| F-020 | Scènes & sources (sur le moteur d'OBS) |
| F-021 | Mixage audio : volumes, filtres micro, changeur de voix, suppression de bruit + **routage par piste (écoute seule / diffusé / les deux)** — entendre une source sans la diffuser (ex. musique protégée) |
| F-022 | Deck de contrôle (local-first, robuste) — **modèle détaillé en §3bis** |
| F-023 | Automations : enchaînements de scènes/actions **avec logique** (condition, délai, variables, séquence), sans script externe |
| F-024 | Caméra mobile (téléphone comme source, QR) |
| F-025 | Multistream (Twitch + YouTube + autres) |
| F-026 | Vertical simultané (shorts en direct) |
| F-027 | Mode focus live (masque le superflu sous stress) |
| F-028 | Silence alertes en 1 clic (toujours visible) |
| F-029 | Réglage des transitions entre scènes + mouvements de sources |
| F-036 | Personnalisation caméra (masques, forme cercle, cadrage, design, **fond sans écran vert**) |
| F-037 | Waveforms audio (retour visuel du son) |
| F-038 | Déplacement auto de sources au changement de scène |
| F-039 | Baisse auto du son du jeu quand on parle (audio ducking) |

### Étape 3 — Interaction
| ID | Fonction |
|---|---|
| F-030 | Chat intégré (multi-plateforme) + **modération auto** (spam, liens, mots interdits) + **actions inline** (timeout / ban / épingler au survol d'un message) |
| F-031 | Alertes follow / sub / don (fines, non intrusives par défaut) |
| F-032 | Événements automatiques (au degré voulu) |
| F-033 | Médias pop-up (émotes, gifs, petites vidéos qui apparaissent puis disparaissent) |
| F-034 | Bandeaux d'information (notifications qui apparaissent puis disparaissent) |
| F-035 | Objectifs & notes du créateur, modifiables, affichés sur le stream |

### Étape 4 — Édition (chemin critique visibilité)
| ID | Fonction |
|---|---|
| F-040 | Marqueurs live (auto + manuels) — la clé du parcours |
| F-041 | Clips & highlights (depuis les marqueurs) |
| F-042 | Sous-titres auto (post-live) |
| F-043 | Découpe en chapitres |
| F-044 | Replay instantané (capture les 30-120 dernières s en 1 touche) |

### Étape 5 — Publication
| ID | Fonction |
|---|---|
| F-050 | Publication réseaux native (marque appliquée automatiquement) |
| F-051 | Planification (calendrier, régularité) |
| F-052 | Miniatures brandées |
| F-053 | Pont Kobo optionnel (bascule vers le pipeline avancé) |
| F-054 | Changement rapide des infos de diffusion (titre, catégorie, notif) multi-plateforme |

### Contrôles rapides & confidentialité
| ID | Fonction |
|---|---|
| F-090 | Mute micro rapide |
| F-091 | Confidentialité écran (cacher/flouter l'écran instantanément) |

### Deck mobile (besoin immédiat de Jay)
| ID | Fonction |
|---|---|
| F-047 | Deck mobile à distance (robuste, local-first ; pont VPS optionnel pour le distant) |
| F-048 | Deck partagé à distance avec niveaux d'accès (ex. modérateur limité) |

### Sous-titres direct & accessibilité viewer
| ID | Fonction |
|---|---|
| F-045 | Sous-titres en direct pour le viewer (accessibilité + obligation légale à venir) |

### Suivi / boucle
| ID | Fonction |
|---|---|
| F-060 | Statistiques (lives et clips, nourrissent la régularité) |
| F-061 | Stabilité + débit du stream visibles dans l'app |
| F-062 | Compteur de viewers en direct, dans l'app |

### Transversal
| ID | Fonction |
|---|---|
| F-070 | Adaptation morphique (densité + sensoriel, ajustables à tout moment) |
| F-071 | Avatar VRM (2 étapes : source externe puis natif) |
| F-072 | Propagation de marque (live → clip → post → miniature, sans refaire) |
| F-046 | Inviter un co-streamer / invité en direct |
| F-092 | Sortie caméra virtuelle (utiliser sa scène dans Zoom/Teams/autre logiciel) |
| F-093 | Bouton discret « soutenir Hikari » (don projet ; discret, sans harcèlement) |

**Niveau d'édition natif (tranché)** : Hikari fait l'**essentiel** (marqueurs, clips simples,
sous-titres, découpe) ; le montage **avancé** (multi-pistes, montage fin) passe par le pont Kobo
(F-053).

### §3bis — Modèle de deck (F-022 détaillé)

Issu de la veille Streamer.bot + TouchPortal (2026-07-11) et validé au prototype.

**4 types de touches** :
| Type | Rôle |
|---|---|
| Action | 1 clic → 1 ou plusieurs actions enchaînées |
| Bascule à état | ON/OFF avec retour visuel coloré (ex. LIVE, Micro) |
| Valeur live | une donnée affichée sur la touche (viewers, débit, titre en cours) |
| Curseur | slider / molette (volume, intensité de filtre) |

**Palette d'actions déclenchables (cœur v1)** :
| Famille | Actions |
|---|---|
| Scènes / sources / filtres / transitions | changer, montrer/cacher, appliquer |
| Audio | mute, volume, **routage écoute/diffusion** |
| Direct Twitch/YouTube | clip, marqueur, titre+catégorie, **pub, sondage, prédiction, récompense, annonce** |
| Modération | timeout, ban, VIP, **shoutout**, clear chat, mode followers/emotes |
| Médias | émotes, gifs, **soundboard**, pop-ups, TTS |
| Système | hotkey clavier, lancer une app, requête HTTP/webhook |
| Logique | condition (si…), délai, variables, séquence |

**Organisation** : multi-**boards** (ex. Principal / Recording / Émotes) + pagination + dossiers.
**Déclencheurs** (au-delà du clic) : commande chat, hotkey clavier, événement (follow/sub/raid), timer.

**Deck et automations = les mêmes objets (ajouté 2026-07-16)**. Une touche ne porte pas de logique :
elle **déclenche**. Le clic est un déclencheur parmi d'autres, au même titre qu'une commande de chat
ou un événement. Conséquence directe :

| Déclencheur de l'automation (F-023) | Apparaît sur le deck ? |
|---|---|
| **Bouton** (manuel) | **Oui, d'office** — le bouton EST le déclencheur |
| Commande chat · événement · minuteur | Non — quelqu'un/quelque chose d'autre déclenche (option « aussi sur le deck » possible) |

Une touche peut donc lancer une action simple **ou une automation entière**. **Pourquoi cette
unité** : sans elle, « les boutons » et « les automations » deviennent deux systèmes parallèles à
maintenir — et deux endroits où corriger le même bug. Modèle vérifié chez la concurrence
(`refs-concurrence/Analyse-Streamerbot-TouchPortal.md` §2). Exécution : PET ADR-011 + ADR-012.
**Backlog deck** : MIDI, création de récompenses à la volée, intégrations tierces (Discord, VTube Studio) via webhooks.

### §3ter — Fonctionnalités ajoutées au prototype (2026-07-12)

| ID | Fonction |
|---|---|
| F-100 | **Cockpit réorganisable** : panneaux déplaçables, redimensionnables, **détachables sur un 2ᵉ écran** (multi-fenêtre) |
| F-101 | **Modes de disposition** : Préparation ≠ Live (les colonnes ne changent pas de place, seul le contenu change) + presets de layout enregistrables |
| F-102 | **Dashboard d'accueil** (pleine largeur) : chiffres clés + derniers streams + à venir/à faire |
| F-103 | **Écran Paramètres unifié** : comptes, périphériques, encodage, deck & appairage, kit de marque, stockage, à propos |
| F-104 | **Connexion espace cloud utilisateur** (Google Drive / Dropbox / OneDrive / S3-WebDAV) — cible de l'archivage auto ; l'utilisateur fournit son cloud |
| F-105 | **Palette de commandes** (Ctrl+K) : accès rapide à toute action/écran (fort pour profil ND) |
| F-106 | **Centre de santé du stream** : état par plateforme (stable / reconnexion / non connecté) |
| F-107 | **Sélecteur de langue** (drapeaux FR/EN/ES) — facette morphique de F-070 |
| F-108 | **Choix de police** dont option lisibilité (Atkinson Hyperlegible) — facette morphique de F-070 |
| F-109 | **Thème contraste élevé** (en plus de sombre/clair) — accessibilité, facette de F-070 |

> Rappel : F-045 (sous-titres live), F-026 (vertical/shorts), F-092 (caméra virtuelle), F-046
> (co-streamer), F-093 (soutenir Hikari) existaient déjà — le prototype les a rendus visibles, sans nouvel ID.

---

## §4 — Architecture

**Les 3 principes**
| Principe | Signification |
|---|---|
| **Tout en local** | L'app tourne sur la machine, sans dépendre d'un service externe fragile. Le deck local parle à l'app directement. |
| **Pannes isolées (« Let It Crash »)** | Un module qui plante est relancé seul, sans faire tomber le live. |
| **Cœur robuste en Rust** | Modules critiques (moteur, deck, encodage) en Rust — empêche des classes entières de bugs. |

> Raison fondatrice (Jay) : le choix Tauri + Rust vise précisément à **isoler les pannes** pour
> qu'un bug ne propage plus l'immobilisation vécue avec Streamer.bot. C'est l'angle que personne n'offre.

**Les couches**
| Couche | Rôle | Techno |
|---|---|---|
| Coquille app | Fenêtre, squelette, robustesse | Tauri 2.x (Rust) |
| Moteur vidéo | Capture, scènes, encodage, diffusion | `libobs` via `libobs-rs` — **à prouver au spike** |
| Modules métier | Deck · audio · marque · clips · publication · stats · avatar | Rust (critique) + logique app |
| Interface | Ce que l'utilisateur voit/clique, adapté au profil | Web (React) dans Tauri + couche morphique |
| Intégrations | Twitch, YouTube, réseaux sociaux | Interfaces officielles de chaque plateforme |

**Deck mobile — deux chemins (garde-fou de fiabilité)**
| Chemin | Quand | Dépend du VPS ? |
|---|---|---|
| **Local (défaut)** | Tablette/téléphone sur le même WiFi que le PC | Non — marche toujours, seul |
| **Distant (option)** | Téléphone en 4G / hors réseau, ou modérateur distant | Oui — pont VPS (Phoenix) + QR code |

Principe garde-fou : le chemin local marche **toujours**, sans serveur. Le pont VPS n'est qu'un
confort pour l'accès distant et le deck délégué (F-048). Si le VPS tombe, le deck local continue.

**Point à risque assumé** : le pont `libobs-rs` reste à prouver → **spike 1-2 j obligatoire avant dev** ;
repli `obs-studio-node` (Electron, mature) — la conception ne change pas, seul le moteur interne change.

État réel du pont, mesuré le **2026-07-16** (remplace l'appréciation « peu mûr, jamais en prod » de v1.0,
qui reposait sur une lecture périmée) :

| Signal | Fait daté | Lecture |
|---|---|---|
| Activité | dernier envoi de code 2026-05-31, dépôt non archivé | Vivant |
| Communauté | 39 étoiles · 7 contributeurs | Petite, réelle |
| **Dépendance à une personne** | sshcrack = 477 contributions sur ~600 | ⚠️ **le vrai risque** — si l'auteur s'arrête, le pont s'arrête |
| Publications | dernière version 2026-01-07 · **6 mois sans publication** | ⚠️ signal à surveiller au spike |
| Écosystème | `libobs-sources` · `libobs-bootstrapper` · `cargo-obs-build` | Plus outillé qu'estimé |

**Lecture par la trajectoire (Honesty.md, Opportunity Lens)** : le risque n'est pas l'immaturité du code
— c'est la **dépendance à un seul auteur**. Cette distance-là se ferme par nous (le pont est ouvert,
sous licence GPL-3.0 : on peut le corriger, le figer sur une version, le forker si besoin), jamais par
l'attente. Le repli `obs-studio-node` reste le filet si le spike échoue.

**Avatar VRM** = module séparé et optionnel, ne touche jamais le cœur ; livré en 2 étapes.

**Cockpit — système de panneaux (dockview)**
Le cockpit repose sur une **librairie de docking mature** (dockview-react), jamais un moteur maison
(l'ancien Hikari avait codé ~6720 lignes de dock jamais branchées — piège à éviter). Panneaux
déplaçables, redimensionnables, fusionnables en onglets ; dispositions sérialisées (`toJSON`/`fromJSON`)
→ presets **Préparation / Live** + presets utilisateur. **Détachement sur 2ᵉ écran** = module Tauri
sur-mesure (fenêtre native `WebviewWindow`, synchro par `emit`/`listen`) — **à dérisquer au spike**
(l'API popout web de dockview ne cible pas Tauri). Empaqueté en **brique Lego `@shinkofa/ui`**.

**Module morphique** : réutilise le **Module Morphique de l'écosystème** (brique partagée), jamais
réécrit — densité, sensoriel, thème (dont **contraste élevé**), **police** (dont lisibilité), **langue**.

**Stockage** : Hikari **n'héberge rien**. L'archivage automatique cible l'**espace cloud de
l'utilisateur** (Google Drive / Dropbox / OneDrive / S3-WebDAV), connecté par OAuth — Hikari orchestre,
ne stocke pas.

---

## §5 — Stack technique

```
[VEILLE] libobs-wrapper@9.0.4+32.0.2 · libobs-bootstrapper@0.4.0 · libobs-sources@3.3.1+32.0.2 ·
tauri@2.11.5 · react@19.2.7 · tailwindcss@4.3.2 · dockview-react@7.0.2 · @pixiv/three-vrm@3.5.5
— vérifié 2026-07-16 via crates.io + registry.npmjs.org (API des registres, jamais docs.rs)
[VEILLE] Tauri@2.x · Rust · libobs-wrapper@3.0.3 · React@19 · TailwindCSS@4 · three-vrm@3.5.5 ·
MediaPipe Face Landmarker · Phoenix (pont VPS) — vérifié 2026-07-11 via web ⚠️ PÉRIMÉ, voir ci-dessous
[SKB] consulté : Eichi Stream-Deck-OBS-Alternatives-Exhaustive-Veille.md (2026-07-10)
```

> 📖 **Précision de nommage (2026-07-16)** — les deux noms qui circulent dans ce CDC désignent deux
> choses distinctes ; l'ambiguïté n'était pas levée :
> - **`libobs-rs`** = le **projet** (l'organisation GitHub, licence GPL-3.0) — c'est ce qu'on désigne
>   en parlant du « pont moteur » et de son niveau de maturité.
> - **`libobs-wrapper`** = la **caisse Rust** qu'on installe et qu'on épingle — **c'est elle qui porte
>   un numéro de version** (9.0.4+32.0.2). Une version ne s'écrit jamais sur `libobs-rs`.
>
> ⚠️ **Correction de veille (2026-07-16)** — la ligne du 2026-07-11 annonçait `libobs-wrapper@3.0.3`.
> Le réel est **9.0.4+32.0.2** : **six versions majeures d'écart**. Cause racine : docs.rs affiche encore
> 3.0.3 comme « latest » (ses builds récents échouent) — la veille avait lu docs.rs au lieu de crates.io.
> **Leçon** : pour une version, la source de vérité est **l'API du registre** (crates.io / npm), jamais un
> site de documentation qui peut geler sur une version dont le build a cassé. Les 5 autres lignes du
> 2026-07-11 ont été re-contrôlées et sont **exactes**.

| Composant | Rôle | Vérifié le | Note |
|---|---|---|---|
| Tauri 2.11.5 | Coquille de l'app | **2026-07-16** | Léger, natif, convention écosystème |
| Rust | Cœur + modules critiques | 2026-07-11 | Empêche des classes de bugs |
| `libobs-wrapper` **9.0.4+32.0.2** | Moteur vidéo (OBS embarqué) — cible OBS 32.0.2 | **2026-07-16** | ⚠️ **spike obligatoire** ; repli `obs-studio-node`. Licence GPL-3.0 |
| `libobs-sources` 3.3.1+32.0.2 | Aide à la création de sources OBS | **2026-07-16** | Même famille que le moteur |
| `libobs-bootstrapper` 0.4.0 | **Télécharge les binaires OBS à l'exécution** | **2026-07-16** | Sert **F-001** (installation unique, zéro logiciel tiers). ⚠️ télécharge un binaire → somme de contrôle obligatoire (voir PET §5) |
| React 19.2.7 + TypeScript | Interface visible | **2026-07-16** | Dans la fenêtre Tauri |
| TailwindCSS 4.3.2 | Habillage de l'interface | **2026-07-16** | Convention Shinkofa |
| FFmpeg | Découpe clips / édition essentielle | 2026-07-11 | Brique secondaire |
| Spout2 | Avatar étape 1 (source externe) | 2026-07-11 | Windows, même machine |
| MediaPipe + three-vrm 3.5.5 | Avatar étape 2 (natif) | **2026-07-16** | Licences ouvertes (MIT/Apache) ; three-vrm exige three ≥ 0.137 |
| Phoenix (Elixir) | Pont VPS deck distant | 2026-07-11 | Websockets robustes ; convention backend |
| Sous-titres live (à confirmer) | Transcription temps réel locale | 2026-07-11 | ⚠️ **à dérisquer** — modèle local (type whisper.cpp) vs service |
| dockview-react 7.0.2 | Système de panneaux du cockpit (dock / onglets / détacher) | **2026-07-16** | ✅ maintenu ; React 19 déclaré en dépendance de pair ; détachement Tauri = module custom au spike |
| Atkinson Hyperlegible | Police option lisibilité (morphique) | 2026-07-12 | Licence ouverte (Braille Institute) |
| Module Morphique (écosystème) | Densité / sensoriel / thème / police / langue | 2026-07-12 | Brique partagée réutilisée, non réécrite |
| rclone (ou équiv.) | Connexion cloud utilisateur (Drive/Dropbox/OneDrive/S3-WebDAV) | 2026-07-12 | Archivage vers le cloud de l'utilisateur, jamais un stockage fourni |

Toute version sera **re-vérifiée au moment du dev** (jeu de connaissances présumé daté). Cette règle
vient d'être prouvée utile : la veille du 2026-07-11 s'est révélée fausse sur le moteur en 5 jours
(voir l'encadré ci-dessus). **Vérifier via l'API du registre**, jamais via un site de documentation.

**Trois dérisquages** (détail en PET §6, phase P0) : moteur `libobs-wrapper` (prioritaire, B0.0) ·
détachement de panneau sur Tauri (B0.4) · sous-titres live locaux (secondaire, B0.1).

---

## §6 — Exigences non-fonctionnelles

| Axe | Exigence | Pourquoi |
|---|---|---|
| **Fiabilité** (priorité #1) | Zéro immobilisation : module isolé + relancé, deck local toujours dispo, reconnexion auto | La douleur actuelle de Jay — jamais otage d'un bug |
| **Performance** | Interface < 100 ms · double encodage (H+V) fluide · sessions longues stables | Un live ne rame pas, ne fuit pas |
| **Adaptation matérielle** | Détecte la machine, réglage sûr par défaut, zone sûre | L'app s'adapte à la machine |
| **Accessibilité** (ND-first) | WCAG 2.2 AA sur l'UI · mouvement réductible · contrôle sensoriel · charge cognitive maîtrisée · **thème contraste élevé** · **police lisibilité** · **palette de commandes** (accès rapide) | Le cerveau de Jay d'abord ; aucun streamer laissé de côté |
| **Personnalisation du poste** | Cockpit réorganisable · panneaux détachables **multi-écran** · dispositions Préparation/Live enregistrables | Chaque streamer a son installation et ses écrans |
| **Sécurité** | Jetons dans le coffre du système · pont VPS authentifié + permissions par rôle · zéro secret en clair | Comptes protégés ; modérateur limité |
| **Endurance** | Tient à 6 mois / 2 ans · code tracé et maintenable | Règle Monozukuri |
| **Portabilité** | Windows d'abord, Linux ensuite · config exportable | macOS différé conditionnel (moteur limité) |
| **Ouverture** | Open-source (moteur GPL), code accessible | L'alternative que personne n'offre |

**Cibles chiffrées à valider au spike** : double encodage RTX 3060 (1080p H + vertical) sans chute
d'image · latence deck local < 100 ms.

---

## §7 — Classification des risques

| Niveau | Couverture tests | Modules |
|---|---|---|
| **Critique** | 95 % | Moteur vidéo · encodage + diffusion multistream · deck local + pont distant + permissions rôle · connexion comptes (Twitch/YouTube) · **moteur d'automations (F-023)** |
| **Sensible** | 90 % | Publication réseaux · sous-titres en direct · modération chat · détection matériel + réglage sûr · sauvegarde/export config · **installation + moteur embarqué (F-001)** |
| **Standard** | 80 % | Kit de marque · clips/édition/marqueurs · avatar · alertes/pop-up/bandeaux/objectifs · stats · wizard · adaptation morphique |
| **Outillage** | 60 % | Scripts internes, presets d'exemple |

Justifications clés : deck en critique (douleur Jay + accès modérateur = sécurité) · moteur + diffusion
en critique (si ça casse, plus de live) · détection matériel en sensible (mauvais réglage = crash machine)
· sous-titres live en sensible (accessibilité + légal).

**Ajouts 2026-07-16 (audit)** — deux modules étaient décrits en §3 mais absents de ce tableau :

| Module | Niveau | Pourquoi ce niveau |
|---|---|---|
| **Moteur d'automations (F-023)** | **Critique** | 3 raisons cumulées : (1) il **exécute des actions système** — lancer une application, requête réseau sortante (§3bis famille « Système ») = surface d'exécution à protéger ; (2) il est **déclenché par le deck**, déjà Critique — même chaîne de confiance ; (3) sa panne **EST la douleur fondatrice** (§4 : ne plus subir l'immobilisation Streamer.bot). Un moteur d'automations qui boucle ou plante en direct = le problème qu'on prétend résoudre. |
| **Installation + moteur embarqué (F-001)** | **Sensible** | `libobs-bootstrapper` **télécharge un binaire OBS puis l'exécute** → chaîne d'approvisionnement à vérifier (somme de contrôle). Une installation ratée = zéro utilisateur, mais aucun live en cours perdu → Sensible, pas Critique. |

> **Arbitrage ouvert (Jay décide, Quality.md)** : le Critique sur les automations coûte 95 % de couverture
> + MC/DC. Le repli défendable est Sensible (90 %) **si** la famille « Système » (lancer une application,
> requête réseau) est retirée du périmètre v1. Tant qu'elle y est, Critique est le seul choix cohérent.

---

## §8 — Analyse de pannes (FMEA modules critiques)

**Moteur vidéo**
| Panne | Effet | Parade |
|---|---|---|
| Le pont `libobs-rs` bloque/plante | Écran figé, live perdu | Spike préalable + repli `obs-studio-node` + relance auto isolée |
| Fuite mémoire sur session longue | Crash après quelques heures | Test session longue au spike + surveillance mémoire + watchdog |
| Conflit d'affichage avec Tauri | Rendu figé | Fil de rendu dédié isolé, validé au spike |

**Encodage + diffusion multistream**
| Panne | Effet | Parade |
|---|---|---|
| Double encodage sature la RTX 3060 | Images qui sautent | Réglages plafonnés selon la machine + alerte avant Go Live |
| Perte réseau en direct | Stream coupé | Reconnexion auto + tampon (bascule secours en backlog) |
| Une plateforme rejette le flux | Multistream partiel silencieux | Suivi par plateforme + alerte visible immédiate |

**Deck local + pont distant + permissions**
| Panne | Effet | Parade |
|---|---|---|
| Le pont VPS tombe | Deck distant coupé | Chemin local indépendant toujours actif (garde-fou décidé) |
| Un modérateur dépasse ses droits | Action non autorisée (couper le stream) | Permissions strictes côté serveur, refus par défaut, test qui vérifie le blocage |
| Latence deck trop haute | Double-clic panique | Cible < 100 ms local + retour visuel immédiat + actions idempotentes |

**Connexion aux comptes (Twitch/YouTube)**
| Panne | Effet | Parade |
|---|---|---|
| Jeton expiré non rafraîchi | Diffusion/publication échoue | Rafraîchissement auto + lecture du jeton frais (jamais figé) |
| Jeton qui fuite | Compte compromis | Coffre du système, jamais en clair, jamais loggé |
| Révocation côté plateforme | Échec silencieux | Détection + invitation claire à re-autoriser |

**Moteur d'automations (F-023)** — *ajouté 2026-07-16, module passé en Critique (§7)*
| Panne | Effet | Parade |
|---|---|---|
| Automation qui boucle (une action se re-déclenche elle-même) | App figée **en direct** = la douleur Streamer.bot reproduite | Profondeur de séquence **bornée** + détection de cycle au moment où l'utilisateur enregistre + coupe-circuit qui désarme l'automation fautive **sans toucher au live** |
| Une action lente bloque la chaîne (requête réseau qui pend) | Le deck ne répond plus, double-clic panique | Exécution **hors du fil de l'interface** + délai maximum par action + retour visuel « en cours » |
| Automation exécutée avec un déclencheur du chat non filtré | Un viewer déclenche une action non prévue | Liste blanche des commandes exposées au chat + droits par déclencheur, refus par défaut |
| Requête réseau sortante vers une cible arbitraire | Fuite de données / usage détourné | Cible explicitement saisie par l'utilisateur, jamais dérivée d'un message ; aucun jeton injecté automatiquement |
| Lancement d'application avec un chemin non maîtrisé | Exécution de code involontaire | Chemin choisi par l'utilisateur (sélecteur de fichier), jamais une chaîne construite depuis un événement |
| Variable absente au moment d'évaluer une condition | Action déclenchée à tort en direct | Évaluation **fermée par défaut** : condition non évaluable → l'action **ne part pas**, et le fait est journalisé |

**Installation + moteur embarqué (F-001)** — *ajouté 2026-07-16, module Sensible (§7)*
| Panne | Effet | Parade |
|---|---|---|
| Binaire OBS téléchargé corrompu ou substitué | Exécution de code non fiable sur la machine | **Somme de contrôle vérifiée avant exécution** + origine en HTTPS épinglée |
| Téléchargement impossible (hors ligne, indisponible) | Première ouverture échoue, utilisateur bloqué | Message clair + reprise possible + option d'installation hors ligne documentée |
| Version OBS récupérée hors de la plage supportée | Moteur instable en silence | Plage de versions déclarée + refus explicite si hors plage |

---

## §9 — Portes de qualité humaine

| Porte | Engagement concret |
|---|---|
| **Charge mentale** | Cockpit replié par défaut, une action = un geste, 4-5 zones fixes. L'expert déplie, le débutant n'est pas noyé. **Palette de commandes (Ctrl+K)** pour atteindre toute action sans chercher. |
| **Confort sensoriel** | Mouvement réductible partout · silence alertes en 1 clic · zéro son/animation surprise non consenti |
| **Tolérance à l'erreur** | Wizard sauvegardé à chaque étape · annulation des actions non-catastrophiques en live · feu vert pré-vol · sauvegarde config |
| **Adaptation** | Densité, thème (dont **contraste élevé**), mouvement, **police**, **langue** (FR/EN/ES) mémorisés entre sessions · se souvient des panneaux dépliés et de la disposition |
| **Dignité** | Zéro « mode débutant » étiqueté · zéro dark pattern · chaque donnée explique son utilité · sortie/désinstall sans culpabilisation |

**Widget de retour** (obligatoire écosystème) : 2 clics, contexte joint automatiquement, **zéro donnée
personnelle**.

**Garde-fou anti-étiquette** : jamais d'interrupteur visible « débutant/expert ». Le niveau se devine
en douceur au wizard, jamais affiché comme un jugement.

---

## §10 — Hors scope explicite

| Hors scope | Pourquoi / où ça va |
|---|---|
| Montage vidéo avancé (multi-pistes, montage fin) | Via le pont Kobo — Hikari fait l'essentiel |
| Compte Hikari (inscription, profil) | L'app est autonome, sans compte |
| Réseau social / hébergement de VOD | Hikari publie vers les plateformes, n'en héberge aucune |
| Monétisation viewer maison (dons/tips) | Renvoi aux systèmes des plateformes (≠ don projet F-093) |
| Création de modèles VRM (type VRoid) | On consomme un avatar, on ne le sculpte pas |
| App de streaming mobile | Rôle de Hoso ; ici le mobile = deck de contrôle, pas la diffusion |
| **macOS complet** | **Différé conditionnel** — si financement suffisant (pas une porte fermée) |

**Reporté au backlog** (pas abandonné) : stream de secours (redondance) · contrôleur MIDI ·
enregistrement local en qualité master · personnalisation avancée des sous-titres côté viewer.

**Écarts vs check-list universelle** (documentés) :
- « Mobile-first » : sans objet pour l'app desktop, mais le deck mobile (F-047) est responsive.
- Trilingue FR/EN/ES : maintenu — Hikari vise le grand public.

---

## §11 — Métriques de succès

**Succès n°1 — pour Jay (D12)**
| Repère | Cible |
|---|---|
| Hikari remplace la stack actuelle | 100 % (OBS + Streamer.bot + deck + scrcpy + Aitum + monitoring) |
| Zéro immobilisation du deck | 0 blocage sur 4 semaines de stream réel |
| Jay streame en public avec | Régulièrement |

**Succès n°2 — fiabilité (« sérénité »)**
| Repère | Cible |
|---|---|
| Temps sans crash en direct | Sessions longues stables |
| Reconnexions réussies | La coupure réseau ne coupe pas le live |

**Succès n°3 — adoption publique**
| Repère | Cible |
|---|---|
| Rétention à 3 mois | Les gens ne retournent pas à OBS (seuil documenté) |
| Parcours complet vécu | % d'utilisateurs qui vont jusqu'à publier un clip |
| Satisfaction profils atypiques | Retours positifs via le widget |

**Succès n°4 — visibilité (L2)** : le « making of » open-source devient un contenu qui attire —
preuve vivante du savoir-faire.

**Repère le plus parlant** : le **taux de parcours complet** (du live au clip publié).

---

## §12 — Visibilité (découverte passive)

**Principe** : aucune campagne active. Hikari se découvre par lui-même, comme preuve vivante.

| Voie de propagation | Comment |
|---|---|
| Tes sites internet | Hikari présenté et téléchargeable depuis The Ermite |
| Ta bibliothèque d'applications | Le catalogue qui référence ton travail — Hikari y figure |
| Bouche à oreille | Ceux qui en entendent parler, sans démarchage |
| GitHub (open-source) | Présence naturelle ; qui cherche une alternative OBS peut tomber dessus |

**Seule exigence** : que la fiche descriptive (sites + catalogue) soit claire — comprendre et avoir
envie, sans qu'on vende quoi que ce soit.

**Ce qu'on ne fait PAS** : pas de campagne, pas de contenu en série, pas de référencement actif. La
matière reste disponible si Jay change d'avis, mais ce n'est pas une charge.

---

## §13 — Anti-patterns projet

| # | Piège | Pourquoi c'est fatal ici |
|---|---|---|
| 1 | Devenir un clone d'OBS de plus (s'arrêter au live) | Le seul vrai différenciateur = le parcours entier |
| 2 | Un interrupteur « débutant/expert » étiqueté | Juger l'utilisateur = violer la Dignité |
| 3 | Réabsorber tout Kobo dans l'édition | Hikari fait l'essentiel ; l'avancé reste à Kobo |
| 4 | Un pont externe comme seul chemin du deck | C'est la panne actuelle ; le local doit toujours marcher seul |
| 5 | Coder avant le spike moteur | `libobs-rs` non éprouvé — bâtir dessus sans preuve = tout refaire. ✅ **Levé le 2026-07-17** : B0.0 fait, pile prouvée (PET §7). |
| 6 | Livrer « à fond » par défaut | La sur-configuration épuise le débutant |
| 7 | Des kits de marque génériques | « Renvoyer l'âme » ne se fait pas avec des templates figés |
| 8 | Dons / notifications envahissants | Dark pattern interdit — le bouton de don reste discret |
| 9 | Ton condescendant ou dénigrer OBS | Respecter l'intelligence de l'utilisateur, et le concurrent |
| 10 | Réécrire un moteur vidéo maison | L'erreur historique de l'ancien Hikari |

---

**CDC écrit dans `docs/hikari-stream/CDC.md`** (espace brainstorm Takumi ; migrera au repo dédié Hikari Stream).
