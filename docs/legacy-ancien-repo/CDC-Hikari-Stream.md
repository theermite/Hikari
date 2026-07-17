# Cahier des Charges — Hikari Stream

> Application de streaming et enregistrement video, maillon d'entree du pipeline contenu Shinkofa.
> Kanji : 光 (Hikari — Lumiere)

---

## 1. Contexte

Hikari Stream est une application Electron de streaming live (Twitch, YouTube) avec gestion de scenes, sources, webcam, audio et overlays — le remplacant OBS pour l'ecosysteme Shinkofa.

**Position dans le pipeline** :
```
Hikari Stream (capture) → Sakusei (post-prod) → Publication (multi-plateforme)
```

Hikari capture le contenu brut (stream live + enregistrement local). Sakusei le transforme (montage, sous-titres, multi-format). La publication distribue sur les plateformes.

---

## 2. Audit de l'existant

### 2.1 Chiffres

| Metrique | Valeur |
|----------|--------|
| **Version** | 0.1.0 |
| **LOC** | ~22,000 (70 fichiers TS/TSX, ~2,660 LOC code mort) |
| **Electron** | 28.2.0 (latest : 40.4.1) |
| **React** | 18.2.0 |
| **Tailwind** | 3.4.1 |
| **Build tool** | electron-vite 2.0.0 |
| **State** | Zustand 4.5.2 |
| **TypeScript** | 5.3.3, passe sans erreur |

### 2.2 Architecture

```
src/
├── main/                     # Process principal Electron
│   ├── index.ts              # Entrypoint, IPC handlers (~978 LOC)
│   └── services/             # 14 modules (~6,768 LOC)
│       ├── ffmpeg.ts          # FFmpeg wrapper, encodeurs HW (313 LOC)
│       ├── streaming.ts       # Pipeline stream/record (~1,098 LOC)
│       ├── capture.ts         # Screen/window capture (315 LOC)
│       ├── audio.ts           # Audio mixing, devices dshow (320 LOC)
│       ├── twitchService.ts   # OAuth, API Twitch (794 LOC)
│       ├── twitchEventSub.ts  # EventSub WebSocket (561 LOC)
│       ├── youtubeService.ts  # OAuth, broadcast creation (702 LOC)
│       ├── adaptiveStreaming.ts # QoS adaptive (438 LOC)
│       ├── dependencies.ts    # Auto-download FFmpeg/scrcpy (306 LOC)
│       ├── scrcpy.ts          # Capture ecran mobile (500 LOC)
│       ├── deckPage.ts        # Stream Deck HTML page (398 LOC)
│       ├── deckRelay.ts       # Stream Deck WebSocket relay (386 LOC)
│       ├── tray.ts            # System tray (425 LOC)
│       └── websocket.ts       # WS server pour mobile deck (212 LOC)
├── preload/
│   └── index.ts              # Bridge IPC securise (559 LOC)
├── renderer/src/
│   ├── App.tsx               # Layout principal, panels OBS-like
│   ├── stores/
│   │   └── appStore.ts       # Store Zustand (~1,800 LOC)
│   └── components/
│       ├── panels/           # Systeme de panneaux dockables (NON INTEGRE, ~2,000 LOC)
│       ├── GoLiveModal.tsx
│       ├── ControlPanel.tsx
│       ├── AlertOverlay.tsx
│       ├── BackgroundSelector.tsx
│       ├── OverlaySelector.tsx
│       ├── MobileSelector.tsx
│       ├── DeckQRCode.tsx
│       └── MarkerPanel.tsx
└── shared/                   # Types partages main/renderer
```

### 2.3 Features fonctionnelles

| Feature | Status | Details |
|---------|--------|---------|
| **FFmpeg pipeline** | FONCTIONNE | Multi-input, encodeurs HW (NVENC, AMF, QSV, x264) |
| **Streaming Twitch** | FONCTIONNE | OAuth, RTMP, clips, markers, raids, EventSub |
| **Streaming YouTube** | FONCTIONNE | OAuth, broadcast creation, transitions |
| **Scenes** | FONCTIONNE | 6 templates, presets, transitions, macros |
| **Sources** | FONCTIONNE | Screen, window, webcam (dshow), mobile (scrcpy) |
| **Audio** | FONCTIONNE | Detection dshow, mixing, volume per-source |
| **Overlays** | FONCTIONNE | Image/HTML/browser source, position, resize |
| **Backgrounds** | FONCTIONNE | Color, image, video backgrounds |
| **Adaptive streaming** | FONCTIONNE | Auto-ajustement bitrate/FPS/resolution selon QoS |
| **Mobile deck** | FONCTIONNE | QR code → controle via mobile (WebSocket) |
| **Stream Deck** | FONCTIONNE | HTML page + WebSocket relay |
| **Markers** | FONCTIONNE | Marqueurs temporels pendant le stream |
| **System tray** | FONCTIONNE | Minimise dans le tray |
| **Panneaux dockables** | CONSTRUIT | Layout OBS-like, detachable — PAS integre dans App.tsx |

### 2.4 Features manquantes ou cassees

| Feature | Status | Impact |
|---------|--------|--------|
| **Build script** | CASSE | `"echo 'Build skipped'"` — pas de distributable |
| **Enregistrement local** | TEST ONLY | Fonctionne en mode test, pas en simultane avec stream |
| **Post-processing** | INEXISTANT | Aucune capacite de montage post-stream |
| **Multi-plateforme simultane** | PARTIEL | Code present mais non teste a fond |
| **Auto-download deps** | A VERIFIER | FFmpeg/scrcpy auto-download (dependencies.ts) |
| **Electron version** | OBSOLETE | v28.2.0 → v40.4.1 (12 versions majeures de retard) |
| **Tests** | INEXISTANT | 0 fichiers de test |

---

## 3. Vision cible

### 3.1 Pipeline contenu complet

```
┌─────────────────────────────────────────────────────────┐
│                    HIKARI STREAM                         │
│                                                          │
│  LIVE                        RECORD                      │
│  ┌──────────┐               ┌──────────┐                │
│  │ Twitch   │               │ Local    │                │
│  │ YouTube  │  SIMULTANE    │ .mkv     │                │
│  │ (RTMP)   │◄────────────►│ (lossless│                │
│  └──────────┘               │  ou HQ)  │                │
│                              └────┬─────┘                │
│                                   │                      │
│  MARKERS ──────────────────►  metadata.json              │
│  (timestamps + notes)        (debut, fin, markers,       │
│                               scenes, plateforme)        │
└───────────────────────────────────┬──────────────────────┘
                                    │
                          export vers Sakusei
                          (dossier partage ou API)
```

### 3.2 Objectifs

1. **Streaming live** : Twitch + YouTube simultanement (deja fonctionnel)
2. **Enregistrement local simultane** : Capturer le flux en parallele du stream
3. **Metadata riche** : Markers, scenes utilisees, timestamps, pour Sakusei
4. **Export propre** : Fichier video + metadata JSON pour le pipeline
5. **Mise a jour technique** : Electron 28 → 40, fix build script

---

## 4. Phases de developpement

### Phase 1 : Stabilisation (P0)

**Objectif** : Rendre Hikari Stream distribuable et stable.

| Tache | Details | Effort |
|-------|---------|--------|
| Fix build script | Remplacer `echo skip` par `electron-vite build` | 30min |
| Upgrade Electron | 28.2.0 → 40.x (breaking changes a verifier) | 2-4h |
| Upgrade deps | React 18→19, Tailwind 3→4, electron-builder 24→26 | 2h |
| Test enregistrement local | Valider recording local mode non-test | 1h |
| Build distributable Windows | `.exe` fonctionnel avec toutes les deps | 1h |
| Smoke test complet | Scenes, streaming test, recording, overlays | 1h |

**Livrable** : Hikari Stream v0.2.0 installable, fonctionnel en streaming + recording.

### Phase 2 : Recording simultane (P0)

**Objectif** : Enregistrer localement pendant le stream live.

| Tache | Details | Effort |
|-------|---------|--------|
| Mode dual output | FFmpeg tee muxer : RTMP + fichier local simultane | 4h |
| Format recording | MKV (container tolerant aux crashes) ou MP4 avec moov atom recovery | 1h |
| UI recording | Bouton record independant du bouton stream, indicateur rouge | 2h |
| Settings recording | Dossier de sortie, qualite (lossless/HQ/compressed), codec | 1h |
| Auto-save markers | Sauvegarder markers dans fichier metadata JSON a cote de la video | 2h |

**Architecture FFmpeg dual** :
```
ffmpeg -f gdigrab -i ... \
  -f dshow -i audio:... \
  -map 0:v -map 1:a \
  -c:v h264_nvenc -b:v 6000k \
  -f tee "[f=flv]rtmp://twitch...|[f=matroska]recording.mkv"
```

**Livrable** : Stream + record simultane, fichier MKV + metadata.json par session.

### Phase 3 : Export Sakusei (P1)

**Objectif** : Creer le pont vers Sakusei pour le post-traitement.

| Tache | Details | Effort |
|-------|---------|--------|
| Metadata JSON | Schema standardise : markers, scenes, sources, timestamps, plateforme | 2h |
| Dossier de sortie structure | `~/Hikari-Exports/{date}-{titre}/video.mkv + metadata.json` | 1h |
| Bouton "Envoyer a Sakusei" | Copie dans dossier surveille par Sakusei (ou API call) | 2h |
| Integration future API | Placeholder pour appel API Sakusei quand deploye | 1h |

**Schema metadata.json** :
```json
{
  "version": "1.0",
  "source": "hikari-stream",
  "recording": {
    "file": "recording.mkv",
    "duration": 3600,
    "resolution": "1920x1080",
    "fps": 30,
    "codec": "h264_nvenc",
    "startedAt": "2026-02-16T14:00:00Z",
    "endedAt": "2026-02-16T15:00:00Z"
  },
  "stream": {
    "platforms": ["twitch", "youtube"],
    "twitchChannel": "theermite",
    "youtubeVideoId": "abc123"
  },
  "markers": [
    { "time": 120, "label": "Intro terminee", "type": "chapter" },
    { "time": 450, "label": "Moment fort", "type": "highlight" },
    { "time": 3200, "label": "Conclusion", "type": "chapter" }
  ],
  "scenes": [
    { "name": "Camera seule", "from": 0, "to": 120 },
    { "name": "Screen + cam", "from": 120, "to": 3200 },
    { "name": "Outro", "from": 3200, "to": 3600 }
  ]
}
```

**Livrable** : Export structure pour Sakusei, metadata riche pour montage automatise.

### Phase 4 : Podcast extraction (P2)

**Objectif** : Extraire la piste audio pour creer un podcast automatiquement.

| Tache | Details | Effort |
|-------|---------|--------|
| Extract audio | FFmpeg : `ffmpeg -i video.mkv -vn -acodec libmp3lame -q:a 2 podcast.mp3` | 1h |
| Bouton "Extraire podcast" | Post-recording, extraction audio one-click | 2h |
| Metadata podcast | Titre, description, chapitres (depuis markers) | 1h |
| Format chapitres | ID3 chapters (MP3) ou Podlove Simple Chapters | 1h |

**Livrable** : Extraction audio avec chapitres, pret pour upload podcast.

### Phase 5 : Ameliorations UX (P2)

| Tache | Details | Effort |
|-------|---------|--------|
| Themes Shinkofa | Dark navy (#0f1729), couleurs The Ermite | 2h |
| Presets de scene | Templates pre-configures : "Gaming", "IRL", "Podcast", "Tutorial" | 2h |
| Raccourcis clavier | Start/stop stream, start/stop record, scene switch | 1h |
| Notifications | Toast pour events Twitch (follow, sub, raid) | 1h |
| Multi-monitor | Support ecrans multiples pour preview + panneaux | 2h |

---

## 5. Stack technique cible

| Composant | Actuel | Cible | Raison |
|-----------|--------|-------|--------|
| Electron | 28.2.0 | 40.x | Securite, performance, APIs modernes |
| React | 18.2.0 | 19.x | Concurrent features, transitions |
| Tailwind | 3.4.1 | 4.x | Nouveau moteur CSS, performance |
| electron-builder | 24.9.1 | 26.x | Meilleur support Windows ARM |
| Zustand | 4.5.2 | 5.x | Breaking changes mineurs |
| FFmpeg | externe | externe | Pas de changement, auto-download |

---

## 6. Integration Sakusei

### Option A : Dossier partage (MVP — Phase 3)

```
Hikari Stream exporte dans ~/Hikari-Exports/
Sakusei surveille ce dossier (file watcher)
Quand nouveau fichier → import automatique dans la media library
```

**Avantages** : Simple, fonctionne meme hors-ligne, pas de dep reseau.
**Inconvenients** : Pas de feedback temps reel, necessite meme machine ou partage reseau.

### Option B : API Sakusei (long terme)

```
Hikari Stream appelle POST /api/import avec video + metadata
Sakusei recoit, stocke, lance le pipeline
Hikari recoit un ID de suivi
```

**Decision** : Option A d'abord (Phase 3), Option B quand Sakusei sera deploye.

---

## 7. Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Electron 28→40 breaking changes | Eleve | Tester incrementalement, lire changelogs |
| FFmpeg dual output instabilite | Moyen | Tester tee muxer avec differents encodeurs |
| Performance recording + streaming | Moyen | GPU encoding obligatoire, monitoring CPU/GPU |
| Taille fichiers MKV | Faible | Compression HQ par defaut, option lossless |

---

## 8. Metriques de succes

| Metrique | Seuil |
|----------|-------|
| Build Windows fonctionnel | Oui/Non |
| Stream Twitch + record simultane | Stable >1h sans crash |
| Export metadata JSON | Schema complet, parseable par Sakusei |
| Latence stream | <3s (identique a OBS) |
| CPU usage (recording + stream) | <50% avec GPU encoding |

---

## 9. Planning estime

| Phase | Effort | Priorite |
|-------|--------|----------|
| Phase 1 : Stabilisation | 1 session | P0 |
| Phase 2 : Recording simultane | 1 session | P0 |
| Phase 3 : Export Sakusei | 1 session | P1 |
| Phase 4 : Podcast extraction | 0.5 session | P2 |
| Phase 5 : UX polish | 1 session | P2 |
| **Total** | **~4-5 sessions** | |

---

**Version** : 1.0.0 | **Date** : 2026-02-16 | **Auteur** : Jay & Takumi
