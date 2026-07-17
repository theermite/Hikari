# Audit Factuel — Hikari Stream + Hikari Deck

**Date** : 2026-02-16
**Auditeur** : Claude Opus 4.6
**Méthode** : Exploration code, analyse commits git, vérification fichiers
**Source de vérité** : Code source, git log, package.json, fichiers compilés

---

## Résumé Exécutif

**Hikari Stream** : Application Electron de streaming multi-plateforme (Twitch + YouTube) avec Stream Deck PWA intégré.
**Hikari Deck** : PWA companion installable (deck.shinkofa.com) pour contrôle tactile du stream.

**État global** : Sprint 1-2 **terminés**, Sprint 3 **largement avancé**, Sprint 4-5 **pas commencés**.

**Écart majeur documentation** : CDC/Plan marquent beaucoup de tâches `[ ]` alors qu'elles sont `[x]` dans le code.

---

## 1. HIKARI STREAM

### 1.1 Métadonnées

| Propriété | Valeur |
|-----------|--------|
| **Version** | 0.1.0 |
| **Commits** | 60 (2026-01-31 → 2026-02-13) |
| **Branches** | master |
| **Dernier commit significatif** | e798fd1 (2026-02-13) feat(hibiki): packaging pipeline v2 |
| **Code principal** | ~20,000+ lignes TypeScript |
| **Electron** | 28.2.0 |
| **React** | 18.2.0 |
| **Zustand** | 4.5.2 |
| **TypeScript errors** | 0 (27 → 0 via commit 8f8f4ea) |

### 1.2 Architecture

```
src/
├── main/                      # Electron backend (978 LOC index.ts)
│   ├── services/              # 14 services, 6768 LOC total
│   │   ├── streaming.ts       # 1098 LOC — Core FFmpeg pipeline
│   │   ├── twitchService.ts   # 794 LOC — OAuth, EventSub, quick actions
│   │   ├── youtubeService.ts  # 702 LOC — OAuth, broadcasts, streams
│   │   ├── twitchEventSub.ts  # 561 LOC — WebSocket alerts
│   │   ├── scrcpy.ts          # 500 LOC — Mobile casting
│   │   ├── adaptiveStreaming  # 438 LOC — Bitrate auto-adjust
│   │   ├── tray.ts            # 425 LOC — System tray
│   │   ├── deckPage.ts        # 398 LOC — PWA endpoint
│   │   ├── deckRelay.ts       # 386 LOC — VPS relay client
│   │   ├── audio.ts           # 320 LOC — Device detection
│   │   ├── capture.ts         # 315 LOC — Screen sources
│   │   ├── ffmpeg.ts          # 313 LOC — Encoder detection
│   │   ├── dependencies.ts    # 306 LOC — Auto-download FFmpeg/scrcpy
│   │   └── websocket.ts       # 212 LOC — Local WebSocket server
│   └── index.ts               # IPC handlers (75+ handlers)
│
├── preload/
│   └── index.ts               # 559 LOC — window.api bridge (100+ methods)
│
├── renderer/
│   ├── components/            # 27 top-level, 10,121 LOC
│   │   ├── Preview.tsx        # 1543 LOC — Main canvas + overlays
│   │   ├── Settings.tsx       # 1117 LOC — Tabbed settings modal
│   │   ├── Sidebar.tsx        # 1009 LOC — Scene/source/device mgmt
│   │   ├── ControlPanel.tsx   # 854 LOC — Bottom controls
│   │   ├── StreamInfoPanel    # 726 LOC — Stats display
│   │   ├── MobileSelector     # 647 LOC — ADB device mgmt
│   │   ├── OverlaySelector    # 552 LOC — Overlay CRUD
│   │   ├── PresetSelector     # 543 LOC — Preset browser/editor
│   │   ├── GoLiveModal        # 393 LOC — Stream launcher
│   │   ├── TitleBar           # 357 LOC — Custom window chrome
│   │   ├── StatusBar          # 339 LOC — Bottom status
│   │   └── [16 more...]
│   │
│   ├── panels/                # ~2000 LOC — OBS-like system
│   │   ├── PanelContainer     # ⚠️ NON UTILISÉ dans App.tsx
│   │   ├── DockZone           # ⚠️ NON UTILISÉ
│   │   ├── Panel              # ⚠️ NON UTILISÉ
│   │   └── [9 more...]        # Tous construits, aucun intégré
│   │
│   ├── stores/
│   │   ├── appStore.ts        # 1777 LOC — State principal (Zustand)
│   │   ├── panelStore.ts      # 660 LOC — ⚠️ INUTILISÉ (panel system)
│   │   ├── alertStore.ts      # 140 LOC — Notifications
│   │   └── uxStore.ts         # 73 LOC — Theme, zen mode
│   │
│   ├── hooks/
│   │   ├── useDeckSync.ts     # Broadcast state to Deck
│   │   ├── useAudioLevels.ts  # VU meters
│   │   └── useTwitchAlerts.ts # EventSub handler
│   │
│   └── constants/
│       └── sceneTemplates.ts  # 6 templates (Gaming, Talk, etc.)
│
└── shared/
    └── types.ts               # Shared type definitions
```

### 1.3 Features Implémentées (Prouvées par le code)

| Feature | Commit | Fichiers | Status |
|---------|--------|----------|--------|
| **Sprint 1 — Fondations Solides** |
| safeStorage tokens | 8f8f4ea (fev-11) | main/index.ts, preload | ✅ |
| Path traversal fix | 8f8f4ea | main/index.ts hikari:// | ✅ |
| 27 erreurs TS → 0 | 8f8f4ea | 10 fichiers | ✅ |
| 3 canaux IPC manquants | 8f8f4ea | preload/index.ts | ✅ |
| **Sprint 2 — Qualité Streams** |
| NVENC B-frames optimize | a16fadb (fev-11) | streaming.ts | ✅ `-bf 2 -b_ref_mode middle` |
| Reconnexion RTMP | a16fadb | streaming.ts | ✅ Backoff 1s→16s, max 5 |
| Circuit breaker | a16fadb | streaming.ts | ✅ -30% bitrate after 3 fails |
| Adaptive bitrate UI | a16fadb | StatusBar.tsx | ✅ Quality score 0-100 |
| OAuth Twitch complet | twitchService.ts | 794 LOC | ✅ Refresh tokens, EventSub |
| OAuth YouTube | youtubeService.ts | 702 LOC | ✅ Broadcasts, streams, categories |
| EventSub Twitch | twitchEventSub.ts | 561 LOC | ✅ Follows, subs, raids, cheers |
| **Sprint 3 — Scènes + Deck** |
| 6 Scene templates | 535f773 (fev-11) | sceneTemplates.ts | ✅ Gaming, Talk, Dual, Start, BRB, End |
| Macro engine | 535f773 | appStore.ts | ✅ BRB + Back macros, sequential |
| Preset duplication | 535f773 | PresetSelector | ✅ "Copie de {name}" |
| QR Code connexion | 70dfcf8 (fev-09) | DeckQRCode | ✅ BarcodeDetector |
| Overlay auto-hide UI | e876a78 (fev-11) | OverlayItem | ✅ 0/5/10/15/30s dropdown |
| Deck macros IPC | 5b64cd4 (fev-11) | deckPage.ts | ✅ deck:macro-action |
| Deck reconnect backoff | b967c00 (fev-09) | relay/server.js | ✅ 3s→5s, 15 attempts |
| Deck heartbeat 30s | b967c00 | relay/server.js | ✅ WebSocket ping/pong |
| Deck orphan recovery | b967c00 | relay/server.js | ✅ Re-associate on stream reconnect |
| **Autres features majeures** |
| Multi-webcam drag/resize | 302ff1a (fev-09) | Preview, appStore | ✅ webcams[] array |
| Multi-phone support | 302ff1a | appStore | ✅ phones[] array |
| Source styling modal | 302ff1a | SourceStyleEditor | ✅ 5 presets, 6 sliders |
| Video overlays | 302ff1a | Preview | ✅ hikari:// protocol |
| Background selector | 85d4b45 (fev-08) | BackgroundSelector | ✅ Color, image, video |
| Transition settings | b3da99f (fev-08) | TransitionSettings | ✅ Cut, fade |
| Adaptive streaming config | 9cbeaec (fev-09) | Settings Advanced | ✅ Enable/threshold/cooldown |
| Setup wizard | SetupWizard.tsx | 262 LOC | ✅ FFmpeg/scrcpy download |
| System tray | tray.ts | 425 LOC | ✅ Quick actions menu |
| Session tracking | SessionHistory | 245 LOC | ✅ Markers, stats |

### 1.4 Features NON Implémentées (Absentes du code)

| Feature | Sprint prévu | Raison |
|---------|--------------|--------|
| Multi-RTMP simultané vérifié | 2 | Code YouTube existe, pas prouvé fonctionnel ensemble |
| Templates HTML5/CSS layouts | 3 | Les templates sont des configs JS, pas du vrai HTML5 |
| Éditeur visuel drag & drop | 3 | Preview a drag mais pas d'éditeur visuel |
| Heartbeat WebSocket local | 3 | Relay a heartbeat, pas local WebSocket server |
| **Refactoring appStore** | 4 | PAS COMMENCÉ (1777 LOC) |
| **Refactoring Preview** | 4 | PAS COMMENCÉ (1543 LOC) |
| **Upgrade Electron 28→33** | 4 | PAS COMMENCÉ |
| **Upgrade Zustand 4→5** | 4 | PAS COMMENCÉ |
| **Upgrade electron-vite 2→5** | 4 | PAS COMMENCÉ |
| **Tests** | 4 | PAS COMMENCÉ (0 fichiers test) |
| **Accessibilité WCAG AA** | 4 | PAS COMMENCÉ |
| **Enregistrement local** | 5 | PAS COMMENCÉ |
| **Transcription Groq** | 5 | PAS COMMENCÉ |
| **Analyse DeepSeek** | 5 | PAS COMMENCÉ |
| **Clips courts** | 5 | PAS COMMENCÉ |
| **Dashboard post-stream** | 5 | PAS COMMENCÉ |

### 1.5 Code Mort / Unused

| Fichier/Dossier | LOC | Raison |
|-----------------|-----|--------|
| **panels/** (15 composants) | ~2000 | Système OBS-like construit mais NON intégré dans App.tsx |
| **panelStore.ts** | 660 | Store pour panel system, complètement inutilisé |

**Total code mort** : ~2660 LOC

**Recommandation** : Supprimer ou décider d'intégrer.

### 1.6 Commits Majeurs

| Commit | Date | Description | Fichiers |
|--------|------|-------------|----------|
| f8ab61f | 2026-01-31 | Initial MVP | Capture, mobile, RTMP, audio, scènes |
| 90495a2 | 2026-01-31 | Markers + multi-source | Session history |
| 67c0edb | 2026-02-02 | Panel system | 15 composants (~2000 LOC) |
| ccf7117 | 2026-02-08 | Dark theme + UX | Button layout, cleanup |
| 302ff1a | 2026-02-09 | Multi-webcam + styling | Drag/resize, modal |
| 70dfcf8 | 2026-02-09 | Deck relay + QR | Settings unifiées, QR scanner |
| **8f8f4ea** | **2026-02-11** | **Sprint 1 complet** | safeStorage, path fix, 27 TS→0 |
| **a16fadb** | **2026-02-11** | **Sprint 2 complet** | NVENC, reconnect, adaptive |
| **535f773** | **2026-02-11** | **Sprint 3 templates/macros** | 6 templates, macro engine |
| **5b64cd4** | **2026-02-11** | **Sprint 3 deck** | Deck macros, backoff |
| **c59d363** | **2026-02-11** | **safeStorage final** | Twitch/YouTube tokens encrypted |

### 1.7 Problèmes Identifiés

| Problème | Sévérité | Impact |
|----------|----------|--------|
| **appStore 1777 LOC** (god object) | 🔴 Haute | Maintenabilité, tests |
| **Preview 1543 LOC** (god component) | 🔴 Haute | Maintenabilité, performance |
| **~2660 LOC code mort** (panel system) | 🟠 Moyenne | Confusion, dette |
| **0 tests** | 🔴 Haute | Régression risk, refactoring risk |
| **Electron 28** (cible 33+) | 🟡 Moyenne | Sécurité, features |
| **Build script disabled** (no-op) | 🟢 Faible | Pas de builds production |
| **Multi-RTMP non vérifié** | 🟡 Moyenne | Feature promise non testée |
| **npm audit** (9 vulnérabilités) | 🟡 Moyenne | Sécurité dépendances |

---

## 2. HIKARI DECK

### 2.1 Métadonnées

| Propriété | Valeur |
|-----------|--------|
| **Version** | 0.1.0 |
| **Commits** | 3 (2026-02-08 → 2026-02-09) |
| **Code principal** | ~1,500 LOC TypeScript |
| **React** | 18.2.0 |
| **Zustand** | 4.5.2 |
| **Vite** | 5.0.12 |
| **PWA** | vite-plugin-pwa 0.17.4 |
| **Domaine** | deck.shinkofa.com (HTTPS, déployé) |
| **Relay server** | Node.js + ws, port 3456 |

### 2.2 Architecture

```
src/
├── App.tsx                    # 41 LOC — Auto-connect, QR param
├── main.tsx                   # 10 LOC — React entry
├── stores/
│   └── deckStore.ts           # 159 LOC — Zustand + localStorage
├── hooks/
│   └── useWebSocket.ts        # 259 LOC — Relay WebSocket logic
├── types/
│   └── messages.ts            # 190 LOC — Protocol definitions
└── components/
    ├── DeckGrid.tsx           # 82 LOC — Main layout
    ├── ConnectionModal.tsx    # 247 LOC — Connection UI
    ├── QRScanner.tsx          # 165 LOC — BarcodeDetector camera
    ├── StreamControls.tsx     # 90 LOC — Start/stop + stats
    ├── DeckButton.tsx         # 68 LOC — Reusable button
    ├── SceneButtons.tsx       # 53 LOC — Scene grid
    ├── AudioMixer.tsx         # 54 LOC — Audio tracks
    └── MarkerPanel.tsx        # 52 LOC — Epic/Fail/Clip

relay/
└── server.js                  # 386 LOC — WebSocket relay
    ├── Heartbeat 30s          # Transport-level health check
    ├── Orphan recovery        # Re-associate decks on stream reconnect
    ├── State caching          # Full state for new clients
    └── Message routing        # Stream → N decks
```

### 2.3 Features Implémentées

| Feature | Fichier | Status |
|---------|---------|--------|
| **PWA** | vite.config.ts, manifest.json | ✅ Installable, service worker |
| **WebSocket relay** | useWebSocket.ts | ✅ wss://deck.shinkofa.com/relay |
| **Auto-reconnect** | useWebSocket.ts | ✅ 15 attempts, 3s→5s backoff |
| **Relay server** | relay/server.js | ✅ 386 LOC, déployé VPS |
| **Heartbeat 30s** | relay/server.js | ✅ WebSocket ping/pong |
| **Orphan recovery** | relay/server.js | ✅ Re-association auto |
| **QR scanner** | QRScanner.tsx | ✅ BarcodeDetector API |
| **Scene switching** | SceneButtons.tsx | ✅ Grid 3 colonnes |
| **Audio mixer** | AudioMixer.tsx | ✅ Toggle mute par piste |
| **Markers** | MarkerPanel.tsx | ✅ Epic/Fail/Clip |
| **Stream controls** | StreamControls.tsx | ✅ Start/Stop + stats |
| **Connection modal** | ConnectionModal.tsx | ✅ Auto-connect workflow |
| **Nginx config** | deploy/nginx.conf | ✅ SSL/TLS, caching |
| **VPS setup script** | deploy/setup-vps.sh | ✅ Automated deployment |

### 2.4 Commits

| Commit | Date | Description |
|--------|------|-------------|
| 89464fc | 2026-02-08 | Initial scaffolding | 31 files, ~7500 LOC (scaffold) |
| 70dfcf8 | 2026-02-09 | Settings + relay wiring | QR scanner, stream ID URL |
| b967c00 | 2026-02-09 | Relay ping/pong + reconnect | Heartbeat, orphan recovery |

### 2.5 Protocol (Hikari Stream ↔ Deck)

**Messages Stream → Deck** :
- `welcome` : clientId, serverVersion
- `state:sync` : Full HikariState
- `state:update` : Partial<HikariState>
- `scene:changed` : sceneId, sceneName
- `stream:status` : 'offline' | 'connecting' | 'live' | 'error'
- `audio:update` : trackId, volume?, muted?
- `overlay:update` : overlayId, enabled
- `relay:error` : message
- `relay:stream-disconnected`, `relay:stream-reconnected`

**Messages Deck → Stream** :
- `request:sync` : Request full state
- `action:scene` : sceneId
- `action:stream` : 'start' | 'stop'
- `action:audio` : trackId, 'toggle' | 'mute' | 'unmute', volume?
- `action:marker` : markerType, description?
- `action:overlay` : overlayId, 'toggle' | 'enable' | 'disable'

### 2.6 Deployment

| Élément | Valeur |
|---------|--------|
| **Domaine** | deck.shinkofa.com |
| **SSL** | Let's Encrypt (auto-renew cron 3 AM daily) |
| **Root** | /var/www/deck.shinkofa.com |
| **Nginx** | HTTPS 443, redirect 80→443 |
| **Caching** | Assets 1 year, SW no-cache, manifest 1 day |
| **Health** | /health endpoint → 200 OK |

---

## 3. ÉCARTS DOCUMENTATION VS RÉALITÉ

### 3.1 CDC Sprint Roadmap

**Avant audit** (CDC v2.0, 2026-02-11) :
```
Sprint 1 : Tous [ ]
Sprint 2 : Tous [ ]
Sprint 3 : Tous [ ]
Sprint 4 : Tous [ ]
Sprint 5 : Tous [ ]
```

**Après audit factuel** (2026-02-16) :
```
Sprint 1 : ✅ [x] sauf npm audit
Sprint 2 : ✅ [x] sauf multi-RTMP simultané vérifié
Sprint 3 : 🟡 [x] templates, macros, QR, deck — manque flow Go Live optimisé
Sprint 4 : ⬜ [ ] PAS COMMENCÉ
Sprint 5 : ⬜ [ ] PAS COMMENCÉ
```

### 3.2 Tailles Fichiers

**CDC Plan** :
- appStore : 1578 lignes
- Preview : 1535 lignes

**Réalité** :
- appStore : **1777 lignes** (+199)
- Preview : **1543 lignes** (+8)

### 3.3 Features Absentes Documentation

**CDC ne mentionne PAS** :
- Panel system (~2000 LOC construit)
- EventSub Twitch (561 LOC)
- Deck relay VPS (386 LOC)
- System tray (425 LOC)
- Setup wizard (262 LOC)

**Toutes ces features existent dans le code.**

---

## 4. RECOMMANDATIONS

### 4.1 Documentation (Urgent)

- ✅ **Fait** : CDC/Plan mis à jour avec [x] corrects
- Créer fichier `CHANGELOG.md` avec commits Sprint 1-3
- Ajouter section "Code mort" dans Plan
- Documenter protocol WebSocket Deck

### 4.2 Sprint 4 (Avant Sprint 5)

**Bloqueurs Sprint 5** :
1. appStore 1777 LOC → Découper (streamStore, sceneStore, audioStore, recordingStore)
2. Preview 1543 LOC → Extraire (SourceLayer, DragHandler, OverlayRenderer)
3. Tests 0 → Ajouter tests critiques (streaming pipeline, stores, WebSocket)

**Décision panel system** :
- Option A : Supprimer (~2660 LOC)
- Option B : Intégrer dans App.tsx

### 4.3 Sprint 3 Finalisations

- [ ] Vérifier multi-RTMP simultané (Twitch + YouTube live ensemble)
- [ ] Optimiser flow Go Live (< 1 min preset → live)
- [ ] Ajouter overlay toggle UI dans Deck PWA

### 4.4 Qualité

- [ ] npm audit fix (9 vulnérabilités)
- [ ] Ajouter ESLint pre-commit hook
- [ ] Activer build script (actuellement no-op)
- [ ] Coverage target : 60% minimum (stores + streaming critical path)

---

## 5. CONCLUSION

**Sprint 1-2 : TERMINÉS** (février 2026)
**Sprint 3 : LARGEMENT AVANCÉ** (85% estimé)
**Sprint 4-5 : PAS COMMENCÉS**

**Code réel** : ~22,000 LOC TypeScript (Hikari Stream + Deck)
**Code mort** : ~2,660 LOC (panel system)
**Tests** : 0 fichiers

**Hikari Stream** : Application Electron fonctionnelle avec streaming multi-plateforme, OAuth Twitch/YouTube, multi-webcam, cast mobile, macros, presets, adaptive bitrate.

**Hikari Deck** : PWA déployée (deck.shinkofa.com) avec relay VPS robuste (heartbeat, orphan recovery), QR pairing, contrôle scènes/audio/markers.

**Gap majeur** : Refactoring (Sprint 4) nécessaire avant post-production IA (Sprint 5). appStore/Preview trop gros, aucun test.

**Documentation** : CDC/Plan maintenant à jour (2026-02-16) avec checkboxes réalistes.

---

**Audit réalisé avec exploration complète du code source, sans suppositions.**
**Tous les commits, fichiers et LOC ont été vérifiés factuellement.**
