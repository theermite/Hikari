---
title: Hikari Stream — Veille technique (2026-07-11) — PARTIELLEMENT PÉRIMÉE
created: 2026-07-11
updated: 2026-07-17
status: superseded-partial
type: veille
---

# Hikari Stream — Veille technique (2026-07-11)

> ## 🛑 LIRE CECI AVANT LE RESTE (ajouté 2026-07-17)
>
> **Ce document est un instantané daté du 2026-07-11. Sa Veille 2 (moteur) contient des faits FAUX
> ou périmés qui ont contaminé le CDC pendant 5 jours.** Il est conservé comme trace historique —
> jamais comme référence.
>
> **La référence à jour est** : `CDC.md` §4 + §5 · `PET.md` B0.0 · `refs-concurrence/Analyse-Streamerbot-TouchPortal.md`.
>
> | Ce que dit la Veille 2 ci-dessous | Réalité vérifiée le 2026-07-16/17 |
> |---|---|
> | `libobs-wrapper` **3.0.3** | ❌ **FAUX** — c'est **9.0.4+32.0.2**. Six versions majeures d'écart. Cause : lecture de **docs.rs** (gelé, ses builds récents échouent) au lieu de **crates.io**. → **ADR-010** : la source de vérité d'une version est l'API du registre, jamais un site de documentation. |
> | « Usage en production : **aucune app connue** » | ❌ **FAUX, et jamais vérifié.** `FFFFFFFXXXXXXX/league_record` est **livré depuis mars 2022** (Rust + Tauri + moteur d'OBS, enregistre League of Legends, binaires téléchargés, poussé 2026-05). Plus **Cap** et 4 autres projets. → mémoire `rare-n-est-pas-impossible`. |
> | « **1 mainteneur principal** » | 🟠 **vrai mais mal cadré** — c'est le **vrai** risque (bus factor 1 : 477 contributions sur ~600), pas l'immaturité. Le dépôt est vivant, l'écosystème outillé (`libobs-sources`, `libobs-bootstrapper`, `cargo-obs-build`). |
> | « API async retirée (blocking only) — friction avec Tauri » | ✅ **toujours vrai** (README confirmé le 2026-07-16). **Mais la conclusion a changé** : la friction ne se combat pas, elle se **contourne** — le moteur va dans un **processus séparé** (**ADR-013**), architecture prouvée par `league_record`. Nuance ratée à l'époque : l'option `no_blocking_drops` existe. |
> | « Repli `obs-studio-node` (mature) » | 🟠 **vrai sur le fond, faux sur le chemin.** Le paquet **npm date de décembre 2020** (« Experimental ») ; le vrai projet est chez **Streamlabs**, poussé en 2026. **Et sa licence est GPL-2.0**, pas GPL-3.0 → un repli oblige à re-trancher la licence du dépôt public. |
> | Synthèse §4 : « **Réutiliser** l'UX + intégrations de **l'ancien repo** » | ❌ **Décision inverse prise le 2026-07-16** : dépôt **neuf** (`theermite/Hikari`, public, GPL-3.0), **zéro réutilisation**. L'ancien réécrivait un moteur maison = l'anti-pattern #10 du CDC. Il est archivé en `shinkofa/Hikari-Stream-Legacy`. |
>
> **Ce qui reste valable** : la **Veille 1** (embarquer vs orchestrer, comparatif des voies, licence
> GPL, canvas multiples OBS 30+) et la **Veille 3** (avatar VRM, pièges de licence Live2D) n'ont pas
> été infirmées. Elles restent à re-vérifier au moment du dev, comme toute veille.

> Faits vérifiés par recherche web (sources datées) pour éclairer le `/concevoir`.
> 3 veilles : moteur vidéo · maturité `libobs-rs` · faisabilité avatar VTuber.
> ⚠️ Toute version/CVE/best-practice est à re-vérifier au moment du dev (dataset présumé daté).

---

## Veille 1 — Moteur vidéo : embarquer vs orchestrer

**Question** : comment faire du stream fiable (scènes, encodage matériel, RTMP/SRT)
sans réécrire OBS ?

**Constat clé** : les apps fiables (Streamlabs Desktop) **ne réécrivent pas** le moteur
d'OBS — elles réutilisent `libobs` (le cœur capture/compositing/encodage d'OBS packagé
en bibliothèque) et posent leur propre UI. Streamlabs = Electron + `obs-studio-node`.
Twitch Studio = **abandonné** le 2024-05-30 (Twitch renvoie vers OBS/Streamlabs).

### Comparatif des voies

| Voie | Une app ? | Fiabilité | Licence | Verdict |
|---|---|---|---|---|
| **Embarquer `libobs`** | ✅ Oui | Haute (moteur de prod) | GPL → open-source si distribué | ✅ Retenu (Jay assume l'open-source) |
| Piloter un OBS externe (obs-websocket v5) | ❌ Non (OBS + app) | Haute | Aucune contrainte | Repli / fallback |
| GStreamer pipeline custom | ✅ | Haute si maîtrisé | Libre | ⚠️ Gros chantier de fiabilisation |
| FFmpeg pipeline custom | ✅ | Moyen (pas pensé live compositing) | Libre | ⚠️ Bon en brique secondaire seulement |
| WebRTC (mediasoup/LiveKit/WHIP) | — | Bonne si infra dédiée | Libre | 🔴 Mauvais fit (exige infra serveur) |

**Licence (point tranché)** : `libobs` est GPLv2. Distribuer un binaire qui l'embarque
oblige à distribuer l'ensemble sous GPL (code source accessible). **Non bloquant** ici :
Jay assume l'open-source. Sinon la seule échappatoire aurait été « piloter un OBS externe ».

**Sortie verticale simultanée** (équivalent Aitum Vertical) : système de **canvas
multiples natif depuis OBS Studio 30** (« Dual Output ») ; le canvas vertical partage
les mêmes sources capturées (pas de 2ᵉ capture), seul l'**encodage** est dupliqué.
⚠️ 2 encodages simultanés = point de vigilance NVENC sur RTX 3060 (à valider).

**Sources** : [obs-websocket](https://github.com/obsproject/obs-websocket) ·
[OBS COPYING GPLv2](https://github.com/obsproject/obs-studio/blob/master/COPYING) ·
[Aitum/obs-vertical-canvas](https://github.com/Aitum/obs-vertical-canvas) ·
[streamlabs/obs-studio-node](https://github.com/streamlabs/obs-studio-node)

---

## Veille 2 — Maturité de `libobs-rs` (pont Rust ↔ moteur OBS)

**Question** : peut-on bâtir Hikari sur Tauri + `libobs-rs` en confiance ?

**Verdict** : **utilisable avec réserves** — pas « trop jeune », mais **pas
production-ready en solo**. Dérisquage par spike (1-2 j) obligatoire avant de s'engager.

### Faits vérifiés

| Métrique | Constat |
|---|---|
| Dernière version | ~~`libobs-wrapper` 3.0.3~~ 🛑 **FAUX → 9.0.4+32.0.2** (lu sur docs.rs gelé, voir l'encadré en tête) |
| Maintenance | ~10 commits/mois, **1 mainteneur principal**, petit projet 🟠 *c'est LE vrai risque, cf. encadré* |
| Couverture | scènes, sources, filtres, transitions, encodage (NVENC via libobs), RTMP/SRT, audio, recording ✅ |
| API async | ❌ **retirée** (blocking only) — friction avec Tauri (Tokio async) |
| Plateformes | Windows ✅ · Linux ✅ · macOS ⚠️ incomplet |
| Compatibilité OBS | OBS 30+ (prod = 32.x) ✅ |
| Usage en production | ~~❌ aucune app connue~~ 🛑 **FAUX → `league_record` est livré depuis mars 2022** (+ Cap, + 4 autres). Jamais vérifié à l'époque. Voir l'encadré en tête. |
| Stabilité API | ⚠️ README : « unstable, will have breaking revisions » |

**Risques hauts identifiés** : (1) décalage async/blocking avec Tauri ; (2) threading GPU
(libobs veut un thread de rendu dédié, Tauri gère déjà le renderer WebView).

**Repli** : `obs-studio-node` (Electron, maintenu par Streamlabs, mature) — la conception
ne change pas, seul le moteur interne change. Ou FFI Rust minimal maison (~5-7 j).

**Spike recommandé (1-2 j)** : (a) scène + source capture d'écran ; (b) encodage NVENC ;
(c) build Windows + taille du bundle ; (d) session longue (mémoire/CPU). Go/no-go après (a)+(b).

**Sources** : [libobs-rs](https://github.com/libobs-rs/libobs-rs) ·
[libobs-wrapper @ crates.io](https://crates.io/crates/libobs-wrapper) ·
[streamlabs/obs-studio-node](https://github.com/streamlabs/obs-studio-node) ·
[Tauri v2](https://v2.tauri.app/)

---

## Veille 3 — Faisabilité avatar VTuber (2 étapes)

**Question** : permettre un avatar animé à la place de la webcam (type Animaze).

**Verdict** : **faisable, 2 étapes, stack 100 % open-source possible**. Choix de format
verrouillé : **VRM (3D, ouvert)**, pas Live2D (piège de licence).

### Panorama des outils (Windows, 2026)

| Outil | Tech | Open-source | Sortie vers stream |
|---|---|---|---|
| VTube Studio | Live2D 2D | ❌ | Spout2 |
| Animaze | VRM/Live2D/3D | ❌ | Caméra virtuelle |
| VSeeFace | VRM 3D | ⚠️ wrapper | Caméra virtuelle |
| Warudo | VRM 3D | ❌ | Spout2 natif |
| VMagicMirror | VRM 3D | ✅ | Capture fenêtre |
| VNyan | VRM 3D | ✅ (plugins) | Caméra virtuelle |

### Étape 1 — consommer un avatar tiers comme source (~2-4 j, risque faible)

Meilleure voie : **Spout2** (partage de texture GPU, latence ≈ 0). L'outil tiers
(Warudo/Animaze) sort en Spout2 → `libobs` le consomme comme source.
⚠️ Spout2 = Windows, même machine. ⚠️ l'utilisateur doit lancer l'app tierce d'abord.
Alternative plus simple : capture de fenêtre (~1-2 j, latence 30-45 ms).

### Étape 2 — avatar natif intégré (~8-12 j, risque moyen)

Chaîne : **MediaPipe Face Landmarker** (WASM, Apache 2.0) → mapper → **three-vrm** (MIT,
v3.5.5 2026-07-09) rend le modèle VRM → source `libobs`.
⚠️ **Tauri WebGL context-lost** = instabilité connue → **plan B : OpenSeeFace natif Rust**
(MIT, CPU-only, robuste). ⚠️ **Kalidokit deprecated** → écrire un mapper MediaPipe→VRM maison.

### Pièges de licence (critique)

| Élément | Piège | Mitigation |
|---|---|---|
| **Live2D Cubism SDK** | Licence payante au-delà d'un seuil de revenu | **Éviter** ; VRM 3D, ou Inochi Creator (2D open) plus tard |
| Modèles `.vrm` individuels | Licence par fichier (CC0 → restrictif) | Vérifier la licence embarquée avant usage commercial |
| MediaPipe / three-vrm / OpenSeeFace / Spout2 | Aucun (Apache 2.0 / MIT) | ✅ OK commercial |

**Modèles VRM gratuits/open** : VRoid Studio (création libre), registre communautaire
(ToxSam/open-source-avatars).

**Sources** : [three-vrm](https://github.com/pixiv/three-vrm) ·
[MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker) ·
[OpenSeeFace](https://github.com/emilianavt/OpenSeeFace) ·
[obs-spout2-plugin](https://github.com/Off-World-Live/obs-spout2-plugin) ·
[Live2D Cubism License](https://www.live2d.com/en/sdk/license/) ·
[VRM Public License 1.0](https://vrm.dev/en/licenses/1.0/)

---

## Synthèse pour le `/concevoir`

1. **Moteur** : embarquer `libobs`, app unique, Tauri 2.x — **spike avant dev**, repli
   `obs-studio-node`. 🟠 *Toujours valable, mais le spike a changé de nature (mesure, plus pari) et
   le moteur va dans un **processus séparé** — voir PET ADR-013.*
2. **Vertical** : canvas multiple OBS 30+, valider double encodage RTX 3060. 🟢 *Valable — et la
   limite de 2 encodages simultanés sur cartes grand public **n'existe plus** (8+ aujourd'hui).*
3. **Avatar** : 2 étapes (Spout2 tiers d'abord, natif VRM ensuite), jamais Live2D. 🟢 *Valable.*
4. ~~**Réutiliser** l'UX + intégrations de l'ancien repo ; remplacer moteur + couche Electron.~~
   🛑 **DÉCISION INVERSE (2026-07-16)** : dépôt **neuf** `theermite/Hikari` (public, GPL-3.0), **zéro
   réutilisation**. L'ancien réécrivait un moteur maison = anti-pattern #10 du CDC. Archivé en
   `shinkofa/Hikari-Stream-Legacy`.
