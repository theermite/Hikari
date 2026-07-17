# Plan d'Implementation — Hikari Stream v2.0

> Decoupage technique base sur le CDC v2.0 valide + audit veille 2026-02-11.

**Date** : 2026-02-11
**Statut** : Valide
**Approche** : Sprints incrementaux alignes sur les priorites de Jay

---

## Priorites Jay (explicites)

1. **Qualite, fluidite des streams**
2. **Mise en place des scenes rapide, efficace, solide et robuste**
3. **Stream Deck stable et fiable**
4. **Overlays controlables depuis le Deck**
5. **Multi-stream**
6. **Post-production IA : video longue + clips courts prets a publier** (v2.0)

---

## Etat Actuel (audit 2026-02-16)

### Ce qui fonctionne

| Feature | Status | Details |
|---------|--------|---------|
| Structure Electron + React | OK | electron-vite, Zustand persist |
| Capture ecran PC | OK | FFmpeg + desktopCapturer |
| Multi-webcam | OK | Drag/resize, hover controls |
| Cast mobile scrcpy | OK | USB + Wi-Fi, audio forwarding |
| Encodage NVENC/x264 | OK | Detection GPU, fallback, B-frames |
| Streaming RTMP Twitch | OK | Reconnexion auto + circuit breaker |
| Mixer audio | OK | 5 pistes (mic, desktop, phone, music, alert) |
| Scenes + templates | OK | 6 templates, switch, transitions |
| Source styling | OK | 5 presets, 6 sliders |
| Overlays (img/txt/vid/browser) | OK | Auto-hide UI |
| Twitch backend complet | OK | OAuth, EventSub, clips, raids, markers |
| YouTube backend | OK | OAuth, broadcasts, streams, categories |
| safeStorage tokens | OK | Commit 8f8f4ea (2026-02-11) |
| Path traversal fix | OK | Commit 8f8f4ea |
| 0 erreurs TypeScript | OK | 27 → 0 (commit 8f8f4ea) |
| Adaptive bitrate + UI | OK | Quality score 0-100, indicateurs |
| NVENC B-frames optimize | OK | -bf 2 -b_ref_mode middle |
| Presets sessions | OK | Save/load/delete/duplicate |
| Macros (BRB + Back) | OK | Execution sequentielle |
| Deck PWA | OK | Deploye deck.shinkofa.com |
| Deck relay VPS | OK | Heartbeat 30s, reconnect, orphan recovery |
| QR Code connexion | OK | BarcodeDetector API |
| System tray | OK | Quick actions |
| Go Live modal | OK | Platform selection workflow |
| Session tracking + markers | OK | Epic/Fail/Clip/Bug/Info/Custom |

### Problemes restants

| Probleme | Severite | Sprint |
|----------|----------|--------|
| appStore.ts 1777 lignes (god store) | Haute | 4 |
| Preview.tsx 1543 lignes (god component) | Haute | 4 |
| Panel system ~2000 LOC NON integre | Haute | 4 (supprimer ou integrer) |
| panelStore.ts 660 LOC inutilise | Moyenne | 4 |
| Legacy code duplique (webcam/phone) | Moyenne | 4 |
| Aucun test (0 fichiers test) | Haute | 4 |
| Electron 28 (cible 33+) | Moyenne | 4 |
| Zustand 4 (cible 5) | Moyenne | 4 |
| electron-vite 2 (cible 5) | Moyenne | 4 |
| Multi-RTMP simultane non verifie | Moyenne | 2 (restant) |
| npm audit (vulnerabilites) | Moyenne | 1 (restant) |
| Build script desactive (no-op) | Faible | 4 |

### Veille technologique (2026-02-16)

| Dependance | Actuel | Cible | Ecart | Sprint |
|------------|--------|-------|-------|--------|
| Electron | 28.2.0 | 33+ | 5 majeures | 4 |
| Zustand | 4.5.2 | 5.0.10 | 1 majeure | 4 |
| electron-vite | 2.0.0 | 5.0 | 3 majeures | 4 |
| FFmpeg | NVENC B-frames | 7.1.1 | OK | - |
| scrcpy | bundled | 2.6+ | Audio natif | OK |
| React | 18.2.0 | 19.2.4 | 1 majeure | Reporte |
| Tailwind | 3.4.1 | 4.1 | 1 majeure | Reporte |

---

## Sprint 1 — Fondations Solides

**Objectif** : Assainir la base technique. Pre-requis a tout le reste.
**Effort** : ~1 session
**Risque** : Faible (fixes cibles)

### 1.1 Securite safeStorage

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 1.1.1 | Implementer safeStorage pour tokens OAuth | Modere | main/index.ts |
| 1.1.2 | Migrer cles RTMP vers safeStorage | Simple | main/index.ts, appStore.ts |
| 1.1.3 | IPC handlers encrypt/decrypt | Simple | preload/index.ts |

### 1.2 Securite path traversal

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 1.2.1 | Whitelist repertoires protocole hikari:// | Simple | main/index.ts |
| 1.2.2 | Validation path (pas de .., pas de drive letter) | Simple | main/index.ts |

### 1.3 TypeScript + IPC

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 1.3.1 | Fix 27 erreurs TypeScript | Modere | ~10 fichiers |
| 1.3.2 | Ajouter 3 canaux IPC manquants | Simple | preload/index.ts |
| 1.3.3 | npm audit fix (non-breaking) | Simple | package.json |
| 1.3.4 | Ajouter "type": "module" | Simple | package.json |

**Checkpoint S1** : ~~Zero erreur TypeScript. Zero vulnerabilite critique. Tokens chiffres.~~ **ATTEINT** (2026-02-11, commit 8f8f4ea). Reste : npm audit fix.

---

## Sprint 2 — Qualite & Fluidite Streams

**Objectif** : Streams stables, fluides, qualite pro. Multi-plateforme.
**Effort** : ~2-3 sessions
**Risque** : Modere (optimisation pipeline existant)
**Prerequis** : Sprint 1

### 2.1 Optimisation FFmpeg

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 2.1.1 | NVENC B-frames (-b_ref_mode middle) | Modere | streaming.ts |
| 2.1.2 | CBR 6000kbps Twitch / 8000kbps YouTube | Simple | streaming.ts |
| 2.1.3 | GOP optimal (2 x fps) | Simple | streaming.ts |
| 2.1.4 | Preset -p4 -tune ll (low latency) | Simple | streaming.ts |

### 2.2 Stabilite & Reconnexion

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 2.2.1 | Adaptive bitrate : connecter 3 canaux IPC a l'UI | Modere | adaptiveStreaming.ts, StatusBar.tsx |
| 2.2.2 | Reconnexion auto RTMP (backoff exponentiel) | Modere | streaming.ts |
| 2.2.3 | Circuit breaker (stop attempts apres N echecs) | Simple | streaming.ts |
| 2.2.4 | Indicateurs par plateforme (bitrate, latence, drops) | Modere | StatusBar.tsx |

### 2.3 Multi-stream

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 2.3.1 | Output RTMP YouTube | Simple | streaming.ts |
| 2.3.2 | Multi-output simultane (1 process par plateforme) | Modere | streaming.ts |
| 2.3.3 | Monitoring independant par sortie | Modere | streaming.ts, appStore.ts |

### 2.4 Auth OAuth

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 2.4.1 | OAuth Twitch (flow complet + refresh) | Modere | twitchService.ts |
| 2.4.2 | OAuth YouTube | Modere | nouveau youtubeService.ts |
| 2.4.3 | Persistance tokens via safeStorage | Simple | main/index.ts |
| 2.4.4 | Config titre/categorie par plateforme | Simple | Settings.tsx, appStore.ts |

**Checkpoint S2** : ~~Multi-stream Twitch + YouTube, reconnexion auto, indicateurs temps reel.~~ **LARGEMENT ATTEINT** (2026-02-11, commit a16fadb). Reste : verification multi-RTMP simultane.

**Best practices veille** :
- FFmpeg 7.1.1 : `-b_ref_mode middle` (20-30% meilleure qualite/bitrate)
- Twitch max 6000kbps CBR, YouTube max 8000kbps CBR
- Upload minimum 12+ Mbps pour 2+ plateformes
- GOP = 2 x framerate (120 frames pour 60fps)

---

## Sprint 3 — Scenes Rapides + Stream Deck Fiable

**Objectif** : Setup < 1 minute. Deck stable et reactif.
**Effort** : ~3-4 sessions
**Risque** : Modere-haut (fonctionnalites nouvelles)
**Prerequis** : Sprint 2

### 3.1 Presets

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 3.1.1 | Schema preset JSON (nom, plateformes, titre, scene, audio, layout) | Simple | types, appStore.ts |
| 3.1.2 | CRUD presets (create, read, update, delete) | Simple | appStore.ts |
| 3.1.3 | Application preset (1 clic = tout configure) | Modere | appStore.ts |
| 3.1.4 | UI selecteur presets (page accueil) | Modere | nouveau PresetSelector.tsx |
| 3.1.5 | Duplication preset | Simple | appStore.ts |

### 3.2 Templates

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 3.2.1 | Systeme de templates (HTML5/CSS layouts) | Modere | nouveau templates/ |
| 3.2.2 | Template Gaming | Simple | templates/ |
| 3.2.3 | Template Minimal | Simple | templates/ |
| 3.2.4 | Template IRL/Talk | Simple | templates/ |
| 3.2.5 | Template Starting Soon | Simple | templates/ |
| 3.2.6 | Template Pause (BRB) | Simple | templates/ |
| 3.2.7 | Template Ending | Simple | templates/ |
| 3.2.8 | Personnalisation (couleurs, logo, textes) | Modere | templates/ |
| 3.2.9 | Transitions entre scenes (cut, fade) | Modere | appStore.ts, Preview.tsx |

### 3.3 Stream Deck Hardening

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 3.3.1 | Heartbeat ping/pong (30s interval, 5s timeout) | Simple | deckRelay.ts |
| 3.3.2 | Auto-reconnect (backoff 1→2→4→8→16s, reset on success) | Modere | deck PWA |
| 3.3.3 | Sub-10ms latency monitoring | Simple | deckRelay.ts |
| 3.3.4 | QR Code connexion + mDNS discovery | Modere | main/index.ts, deckPage.ts |

### 3.4 Deck Actions

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 3.4.1 | Toggle overlay depuis Deck | Simple | deckPage.ts |
| 3.4.2 | Move handle position depuis Deck | Modere | deckPage.ts |
| 3.4.3 | Macro actions (chainer scene + mute + overlay) | Modere | nouveau macroEngine.ts |
| 3.4.4 | Overlay auto-hide avec countdown | Modere | appStore.ts, Preview.tsx |

**Checkpoint S3** : ~~Preset "Office HoK" → Go Live en < 1 min. Deck stable. Overlays controlables.~~ **PARTIELLEMENT ATTEINT** (2026-02-11, commits 535f773 + 5b64cd4 + b967c00). Templates, macros, QR, deck stable. Reste : flow Go Live optimise, overlay toggle Deck.

**Best practices veille** :
- WebSocket heartbeat : ping 30s, pong timeout 5s → reconnect
- Auto-reconnect : 1s → 2s → 4s → 8s → 16s (max), reset on success
- Sub-10ms latency sur reseau local avec WebSocket natif

---

## Sprint 4 — Refactoring Architectural + Deps

**Objectif** : Dette technique zero. Architecture extensible pour Sprint 5.
**Effort** : ~3-4 sessions
**Risque** : Modere (max 3 fichiers par commit, WF-016)
**Prerequis** : Sprint 3

### 4.1 Decoupage Stores

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 4.1.1 | Extraire streamStore (RTMP, encoding, status) | Modere | appStore.ts → streamStore.ts |
| 4.1.2 | Extraire sceneStore (scenes, sources, overlays) | Modere | appStore.ts → sceneStore.ts |
| 4.1.3 | Extraire deckStore (deck state, actions, macros) | Simple | appStore.ts → deckStore.ts |
| 4.1.4 | Extraire audioStore (pistes, mixer, VU) | Simple | appStore.ts → audioStore.ts |
| 4.1.5 | Extraire settingsStore (config, presets) | Simple | appStore.ts → settingsStore.ts |
| 4.1.6 | Extraire recordingStore (enregistrement, post-prod) | Simple | nouveau recordingStore.ts |

### 4.2 Decoupage Composants

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 4.2.1 | Extraire SourceLayer (rendu individuel source) | Modere | Preview.tsx → SourceLayer.tsx |
| 4.2.2 | Extraire DragHandler (logique drag/resize) | Modere | Preview.tsx → useDragResize.ts |
| 4.2.3 | Extraire OverlayRenderer | Simple | Preview.tsx → OverlayRenderer.tsx |
| 4.2.4 | Extraire PreviewCanvas (conteneur principal) | Simple | Preview.tsx → PreviewCanvas.tsx |

### 4.3 Upgrades Dependances

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 4.3.1 | Upgrade Electron 28 → 33 | Complexe | package.json, main/ |
| 4.3.2 | Upgrade Zustand 4 → 5 (persist API change) | Modere | tous les stores |
| 4.3.3 | Upgrade electron-vite 2 → 5 | Modere | vite configs |
| 4.3.4 | Code splitting automatique | Simple | vite config |

### 4.4 Tests + Accessibilite

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 4.4.1 | Setup Jest/Vitest | Simple | config |
| 4.4.2 | Tests stores (stream, scene, deck) | Modere | tests/ |
| 4.4.3 | Tests streaming pipeline | Modere | tests/ |
| 4.4.4 | Tests WebSocket (Deck) | Simple | tests/ |
| 4.4.5 | Navigation clavier complete | Modere | composants UI |
| 4.4.6 | ARIA labels + focus visible | Simple | composants UI |
| 4.4.7 | Contraste WCAG AA | Simple | tailwind config |

**Checkpoint S4** : Stores < 400 lignes chacun. Preview < 300 lignes. Tests verts. Deps a jour.

**Strategie upgrades** :
- Electron : 28 → 33 (palier sur, ASAR fix). 33 → 40 reporte.
- React 18 → 19 : Reporte (breaking changes, peu de gain en Electron)
- Tailwind 3 → 4 : Reporte (breaking change CSS-first, risque eleve)

---

## Sprint 5 — Pipeline Post-Production IA

**Objectif** : Du stream termine au contenu pret a publier en < 5 minutes.
**Effort** : ~4-5 sessions
**Risque** : Modere (APIs externes, mais FFmpeg local pour le gros)
**Prerequis** : Sprint 4 (architecture extensible, recordingStore pret)

### 5.1 Enregistrement Local

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.1.1 | Dual output FFmpeg (RTMP + fichier local) | Modere | streaming.ts |
| 5.1.2 | Mode "Recording only" (sans RTMP) | Simple | streaming.ts |
| 5.1.3 | Options enregistrement (resolution, codec, dossier) | Simple | settingsStore.ts |
| 5.1.4 | Indicateur recording (point rouge + timer + taille) | Simple | StatusBar.tsx |
| 5.1.5 | Audio multi-piste (micro separe) | Modere | streaming.ts |
| 5.1.6 | Segmentation auto si > 4Go | Simple | streaming.ts |

### 5.2 Transcription (Groq Whisper)

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.2.1 | Service Groq API (auth, upload audio) | Modere | nouveau groqService.ts |
| 5.2.2 | Extraction audio depuis enregistrement (FFmpeg) | Simple | ffmpeg utils |
| 5.2.3 | Transcription → SRT/VTT | Modere | groqService.ts |
| 5.2.4 | Decoupage par segments (phrases naturelles) | Simple | groqService.ts |
| 5.2.5 | UI progression transcription | Simple | PostStreamDashboard.tsx |

### 5.3 Analyse IA (DeepSeek)

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.3.1 | Service DeepSeek API (auth, chat completions) | Modere | nouveau deepseekService.ts |
| 5.3.2 | Analyse transcription → moments forts | Modere | deepseekService.ts |
| 5.3.3 | Croisement : marqueurs + transcription + chat activity | Modere | nouveau clipAnalyzer.ts |
| 5.3.4 | Generation titres/descriptions/hashtags par plateforme | Simple | deepseekService.ts |
| 5.3.5 | Score engagement par segment | Simple | clipAnalyzer.ts |

### 5.4 Generation Video Longue

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.4.1 | Bruler sous-titres SRT dans video (FFmpeg) | Modere | nouveau postProduction.ts |
| 5.4.2 | Style sous-titres personnalisable | Simple | postProduction.ts |
| 5.4.3 | Appliquer intro/outro template | Modere | postProduction.ts |
| 5.4.4 | Transitions entre segments (fade, cut) | Simple | postProduction.ts |
| 5.4.5 | Export MP4 YouTube-ready | Simple | postProduction.ts |

### 5.5 Generation Clips Courts

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.5.1 | Decoupe clips (30-90s) bases sur analyse IA | Modere | nouveau clipGenerator.ts |
| 5.5.2 | Reformatage 9:16 vertical (TikTok, Reels, Shorts) | Modere | clipGenerator.ts |
| 5.5.3 | Reformatage 1:1 carre (Instagram feed) | Simple | clipGenerator.ts |
| 5.5.4 | Sous-titres stylises (gros texte anime) | Modere | clipGenerator.ts |
| 5.5.5 | Hook texte overlay (phrase IA) | Simple | clipGenerator.ts |
| 5.5.6 | Branding createur (logo, pseudo, couleurs) | Simple | clipGenerator.ts |

### 5.6 Dashboard Post-Stream

| ID | Tache | Complexite | Fichiers |
|----|-------|------------|----------|
| 5.6.1 | Dashboard "Votre stream est termine" | Modere | nouveau PostStreamDashboard.tsx |
| 5.6.2 | Resume stats (duree, viewers, messages) | Simple | PostStreamDashboard.tsx |
| 5.6.3 | Timeline moments forts | Modere | nouveau TimelineView.tsx |
| 5.6.4 | Apercu clips inline (play/pause) | Modere | nouveau ClipPreview.tsx |
| 5.6.5 | Boutons Valider / Ajuster / Regenerer | Simple | PostStreamDashboard.tsx |
| 5.6.6 | Export batch 1 clic | Simple | PostStreamDashboard.tsx |
| 5.6.7 | Settings API keys (Groq, DeepSeek) | Simple | Settings.tsx |

**Checkpoint S5** : Stream → enregistrement → transcription → clips IA → export. < 5 min total.

---

## Ordre d'Execution (mis a jour 2026-02-16)

```
Sprint 1 (Fondations)           ~1 session       ✅ FAIT (2026-02-11)
  ✅ 1.1 safeStorage
  ✅ 1.2 Path traversal fix
  ✅ 1.3 TS errors + IPC
  ⬜ 1.3.3 npm audit fix (restant)

Sprint 2 (Qualite Streams)      ~2-3 sessions    ✅ QUASI-FAIT (2026-02-11)
  ✅ 2.1 FFmpeg NVENC B-frames
  ✅ 2.2 Reconnexion + adaptive
  ⬜ 2.3 Multi-RTMP simultane (a verifier)
  ✅ 2.4 OAuth + config plateforme

Sprint 3 (Scenes + Deck)        ~3-4 sessions    🟡 PARTIELLEMENT FAIT (2026-02-11)
  ✅ 3.1 Presets (save/load/delete/duplicate)
  ✅ 3.2 Templates (6 templates)
  ✅ 3.3 Deck hardening (heartbeat, reconnect, orphan recovery)
  ✅ 3.4 Macros (BRB + Back) + QR Code
  ⬜ 3.x Flow Go Live optimise (< 1 min)
  ⬜ 3.x Overlay toggle depuis Deck UI

Sprint 4 (Refactoring)          ~3-4 sessions    ⬜ PAS COMMENCE
  4.1 Decoupage stores (appStore 1777 LOC)
  4.2 Decoupage composants (Preview 1543 LOC)
  4.3 Upgrades deps (Electron 28→33, Zustand 4→5, electron-vite 2→5)
  4.4 Tests + accessibilite
  4.x Supprimer ou integrer panel system (~2660 LOC unused)

Sprint 5 (Post-Production IA)   ~4-5 sessions    ⬜ PAS COMMENCE
  5.1 Enregistrement local
  5.2 Transcription Groq
  5.3 Analyse DeepSeek
  5.4 Video longue
  5.5 Clips courts
  5.6 Dashboard post-stream
```

---

## Risques et Mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| APIs IA indisponibles/lentes | Post-prod bloquee | Fallback : decoupe manuelle sans IA |
| Groq rate limits | Transcription lente | Chunking audio, queue de processing |
| DeepSeek qualite variable | Clips non pertinents | Review humain obligatoire, regeneration |
| Electron 33 breaking changes | App cassee | Upgrade progressif, tests avant/apres |
| FFmpeg B-frames incompatibles | Encodage degr. | Fallback sans B-frames |
| WebSocket deconnexion | Deck inutilisable | Heartbeat + reconnect auto |
| Fichier local > 4Go | Corruption | Segmentation auto |
| Upload insuffisant multi-stream | Qualite degradee | Adaptive bitrate par plateforme |

---

## Fichiers Critiques

| Fichier | Sprints |
|---------|---------|
| `src/main/index.ts` | 1, 2 |
| `src/preload/index.ts` | 1 |
| `src/main/services/streaming.ts` | 2, 5 |
| `src/main/services/twitchService.ts` | 2 |
| `src/renderer/src/stores/appStore.ts` (1777 LOC) | 1, 2, 3, 4 |
| `src/renderer/src/components/Preview.tsx` (1543 LOC) | 3, 4 |
| `src/renderer/src/components/Settings.tsx` | 2, 5 |
| `src/renderer/src/components/StatusBar.tsx` | 2, 5 |
| `src/main/services/deckPage.ts` | 3 |
| `src/main/services/deckRelay.ts` | 3 |
| Nouveaux : groqService.ts, deepseekService.ts | 5 |
| Nouveaux : postProduction.ts, clipGenerator.ts | 5 |
| Nouveau : PostStreamDashboard.tsx | 5 |

---

**Version** : 2.1.0 | **Date** : 2026-02-16 | **Approche** : Sprint-based, priorites Jay | **Audit** : Checkboxes mis a jour selon commits reels
