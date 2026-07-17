# Sprint Plan — Hikari Stream (光)

**Version** : 1.0.0
**Date** : 2026-02-27
**Référence architecture** : `docs/Architecture-Vision.md`
**Référence CDC** : `docs/CDC-Hikari-Stream.md`

> Document vivant. Mettre à jour après chaque sprint.
> Consulter `Architecture-Vision.md` avant toute décision d'implémentation.

---

## État Actuel (après session 2026-02-27)

### Ce qui fonctionne
- Pipeline streaming : NVENC, reconnect auto, circuit breaker ✅
- OAuth Twitch + YouTube : tokens chiffrés ✅
- EventSub Twitch : alerts temps réel ✅
- Stream Deck : relay VPS, QR pairing, heartbeat ✅
- Panel system : intégré dans App.tsx ✅
- Dock zones : dock-left (Scènes/Sources), dock-right (StreamInfo/Chat) ✅
- Panels détachables : Chat, StreamInfo ✅
- Persist key : v3 (localStorage) ✅

### Ce qui est cassé / à corriger immédiatement
- `dock-bottom` contient AudioPanel → **redondant** avec ControlPanel Audio tab
- `audio.detachable = false` → déjà corrigé mais dock-bottom doit être supprimé
- ControlPanel (750 LOC) : tabs Scènes/Sources/Overlays/Audio/Markers/Monitor → anti-pattern UX
- ControlPanel occupe 140px (15-20% écran) pour peu d'info → à réduire

### Scores audit (2026-02-26)
| Domaine | Score | Cible |
|---------|-------|-------|
| Architecture | 42/100 | 80+ |
| UX / Accessibilité | 38/100 | 80+ |
| Qualité code | 22/100 | 85+ |
| Features CDC | 52/100 | 90+ |
| Sécurité Electron | 58/100 | 85+ |
| **Global** | **52/100** | **95+** |

---

## Sprint 0 — Hotfix dock-bottom (IMMÉDIAT — 30 min)

**Objectif** : Supprimer la redondance audio créée en session 2026-02-27.

**Fichier** : `src/renderer/src/stores/panelStore.ts`

### Tâches
- [ ] Retirer `dock-bottom` des `defaultDockZones` (ligne ~56-60)
- [ ] Bumper `persist key` : `hikari-stream-panels-v3` → `hikari-stream-panels-v4`
- [ ] Vérifier que l'app démarre proprement sans dock-bottom

### Acceptance criteria
- App démarre sans dock en bas
- Zones dock-left et dock-right présentes avec leurs panels
- Aucune duplication audio visible
- localStorage v4 (reset propre depuis v3)

### Fichiers touchés
- `panelStore.ts` (1 fichier, 2 changements)

---

## Sprint 1 — Extraction useStreamController (1 session, ~2-3h)

**Objectif** : Séparer la business logic de ControlPanel.tsx de son UI.
C'est le pré-requis pour refactorer l'UI sans casser le streaming.

**Problème actuel** : ControlPanel.tsx (~750 LOC) mélange :
- `handleStartStream`, `handleStopStream`, `handleStartRecording` (business logic)
- `useEffect` pour `stream:state`, `stream:stats`, `stream:duration` (IPC listeners)
- Polling Twitch toutes les 30s (business logic)
- UI tabs : Scènes, Sources, Overlays, Audio, Markers, Monitor

### Tâches
- [ ] Créer `src/renderer/src/hooks/useStreamController.ts`
- [ ] Y déplacer : `handleStartStream`, `handleStopStream`, `handleStartRecording`
- [ ] Y déplacer : IPC listeners `stream:state`, `stream:stats`, `stream:duration`, `stream:error`
- [ ] Y déplacer : polling Twitch viewers
- [ ] ControlPanel.tsx importe `useStreamController` → UI uniquement
- [ ] Vérifier : stream fonctionne toujours, stats visibles, Twitch polling actif

### Acceptance criteria
- `useStreamController.ts` < 200 LOC
- `ControlPanel.tsx` réduit à ~400 LOC (UI seulement)
- Go Live fonctionne
- Stats (bitrate, FPS, viewers) s'affichent correctement
- Refactoring transparent pour l'utilisateur

### Fichiers touchés (max 3 par commit)
1. `src/renderer/src/hooks/useStreamController.ts` (nouveau)
2. `src/renderer/src/components/ControlPanel.tsx` (modifié — import hook)
3. Types si nécessaires

---

## Sprint 2 — Redesign AudioPanel horizontal compact (~2h)

**Objectif** : Préparer AudioPanel pour un dock horizontal OBS-style.

**Problème actuel** : AudioPanel rend des cards verticales (`p-3 space-y-4`) → inadapté dock horizontal.

**Layout cible** :
```
│ 🎤 Micro │ 🖥️ PC │ 📱 Phone │ 🎵 Musique │
│ ─────── │ ──── │ ──────── │ ─────────  │
│   VU    │  VU  │    VU    │    VU      │
│ 🔊 ─── │ ─── │   ───    │   ───      │
│ [Mute]  │[Mute]│  [Mute]  │  [Mute]    │
```

Hauteur cible du dock-bottom audio : **80-100px** (actuellement ~300px en cards vertical).

### Tâches
- [ ] Créer `AudioTrackColumn` component (fader vertical compact, VU meter, mute)
- [ ] `AudioPanel` : mode `orientation="horizontal"` → `flex-row gap-2`
- [ ] VU meters : rotate 90° (vertical → horizontal columns)
- [ ] Test : volume, mute, VU meters actifs
- [ ] Réintroduire `dock-bottom` avec audio dans `defaultDockZones` (après ce sprint)

### Acceptance criteria
- dock-bottom height : 80-100px
- 4 tracks visibles simultanément en colonnes
- VU meters actifs pendant le stream
- Mute/unmute fonctionnels
- Compatible avec Panel orientation="horizontal"

### Note importante
Après ce sprint, réintroduire `dock-bottom` dans `defaultDockZones` (Sprint 0 l'avait supprimé).
Le dock-bottom audio avec le nouveau layout sera non-redondant (OBS-style, visible simultanément aux autres panels).

---

## Sprint 3 — ControlPanel → Action Bar + panels dans dock (~3-4h)

**Objectif** : Compléter la migration vers le panel system.
ControlPanel passe de 750 LOC tabs → 50px Action Bar.

**Layout cible post-sprint** :
```
┌────────────────────────────────────────────────────────────┐
│  TitleBar                                                  │
├──────────┬───────────────────────────────┬─────────────────┤
│  SCÈNES  │           PREVIEW             │  STREAM INFO    │
│  SOURCES │                               │  CHAT           │
├──────────┴───────────────────────────────┴─────────────────┤
│ AUDIO  (dock-bottom horizontal, OBS-style, 80-100px)       │
├────────────────────────────────────────────────────────────┤
│ ⚡ [● GO LIVE] [⏺ REC] [◆ MARKER] [PRESET ▼]  ← ~50px   │
└────────────────────────────────────────────────────────────┘
```

### Tâches
- [ ] Supprimer les onglets de ControlPanel.tsx (Scènes, Sources, Overlays, Audio, Markers, Monitor)
- [ ] ControlPanel devient `ActionBar.tsx` : seulement Go Live, Rec, Markers, Preset
- [ ] Déplacer Markers → `MarkersPanel` dans dock (déjà exist dans `panels/content/`)
- [ ] Overlay toggle → dans dock-left Sources panel
- [ ] Vérifier : tous les panels dockés fonctionnent
- [ ] Tester : stream complet depuis panel system

### Acceptance criteria
- ActionBar height : 40-50px (cible)
- Tous les panels contenu visibles dans le dock
- Go Live fonctionne depuis ActionBar
- Markers enregistrés correctement
- ControlPanel.tsx renommé ActionBar.tsx (ou réduit à ~100 LOC)
- Aucune perte de fonctionnalité

---

## Sprint 4 — Stream Deck expansion (~2-3h)

**Objectif** : Stream Deck devient un compagnon live complet.
La philosophie Desktop/Deck ne fonctionne que si le Deck est suffisamment puissant.

### Features manquantes (identifiées dans audit + session)
- [ ] **Overlay toggle depuis Deck** : handler `action:overlay` dans `deckPage.ts`
- [ ] **Audio controls depuis Deck** : mute/unmute + volume slider par piste
- [ ] **Stats temps réel sur Deck** : bitrate, FPS, viewers, durée stream
- [ ] **Markers depuis Deck** : bouton marker rapide (Epic, Fail, Clip)

### Tâches
- [ ] `deckPage.ts` : ajouter `action:overlay`, `action:audio:mute`, `action:audio:volume`
- [ ] `websocket.ts` : broadcaster les stats toutes les 5s
- [ ] Deck PWA (`deck.shinkofa.com`) : ajouter section Audio + Section Stats
- [ ] Tester : depuis téléphone, muter micro, changer scène, voir bitrate

### Acceptance criteria
- Overlay toggle : ON/OFF visible en temps réel sur Deck
- Mute micro depuis Deck : fonctionnel
- Stats sur Deck : bitrate, viewers, durée (mise à jour <10s)
- Marker depuis Deck : enregistré avec timestamp correct

---

## Sprint 5 — Polish, Keyboard shortcuts, Go Live flow (~2h)

**Objectif** : Finir le Sprint 3 original (Session-Plan-2026-02-27).

### Tâches
- [ ] **Raccourcis clavier** : F1-F4 (scènes), Ctrl+G (go live), Ctrl+R (rec), M (mute micro), Space (marker Epic)
- [ ] **Modal raccourcis** : `?` ou dans Settings → liste des shortcuts
- [ ] **Go Live flow** : preset → live en < 1 minute. Si preset chargé = 2 clics max
- [ ] **GoLiveModal** : sélection preset pré-remplit titre/catégorie/plateforme

### Acceptance criteria
- F1-F4 changent de scène sans délai visible
- Ctrl+G lance le stream sans ouvrir le modal si preset prêt
- Modal `?` liste tous les raccourcis
- Nouveau stream depuis preset : < 60 secondes

---

## Sprints Futurs (CDC phases 2-5)

### Sprint 6 — Recording simultané (CDC Phase 2)
- Dual output FFmpeg (RTMP + fichier MKV crash-tolerant)
- UI recording (bouton indépendant du Go Live)
- Settings recording (dossier, qualité, codec)
- Auto-save markers dans `metadata.json`

### Sprint 7 — Refactoring God Objects (CDC Sprint 4)
**Pré-requis** : Tests en place avant de toucher appStore/Preview
- Extraire `streamStore.ts`, `sceneStore.ts`, `audioStore.ts`
- Découper `Preview.tsx` : SourceLayer, useDragResize, OverlayRenderer
- Setup Vitest + tests stores critiques

### Sprint 8 — Tests & Qualité ✅ TERMINÉ (2026-02-28)

**Résultats** : 296 tests verts, coverage > 80% global, 0 erreur TS/lint

| Store | Coverage lines | Coverage functions |
|-------|---------------|-------------------|
| audioSlice | 100% | 100% |
| streamSlice | 94.49% | 82.75% |
| sceneSlice | 71.56% | 100% |
| sourceSlice | 84.22% | 70.58% |
| alertStore | 100% | 100% |
| panelStore | 86.72% | 81.25% |
| uxStore | 100% | 100% |
| **Global** | **87.34%** ✅ | **81.29%** ✅ |

**Livrés** :
- Vitest 3 + setup.ts (window.api mock + localStorage mock)
- 296 tests en 7 fichiers (audioSlice, streamSlice, sceneSlice, sourceSlice, alertStore, panelStore, uxStore)
- Seuils : lines 80%, functions 80%, branches 75% — tous passés
- `appStore.ts` exclu du scope (Electron-dépendant, testé en sprint intégration)
- `console.warn/error` dans App.tsx wrappés dans `NODE_ENV === 'development'`

### Sprint 9 — Post-production IA (CDC Phase 4-5)
**Pré-requis** : Sprint 6 (recording) terminé
- Transcription Groq Whisper
- Analyse DeepSeek moments forts
- Export Sakusei (`~/Hikari-Exports/`)
- Dashboard post-stream

---

## Règles du Sprint

### Avant de coder
1. Lire `Architecture-Vision.md`
2. Vérifier que la tâche est dans le sprint actif
3. Lire les fichiers concernés AVANT de coder

### Pendant le sprint
- Max 3 fichiers par commit (WF-016)
- Un commit par sous-tâche
- Tester manuellement après chaque commit

### Après le sprint
- Mettre à jour ce document (Sprint N → Completed)
- Documenter les découvertes dans `Architecture-Vision.md` si architectural
- Bumper persist key si defaultDockZones change

### Règle critique
> Si une tâche révèle un problème architectural non prévu → STOP.
> Documenter dans Architecture-Vision.md, discuter avec Jay, puis décider.
> Ne jamais "continuer quand même" sur un problème fondamental.

---

## Historique Sprints

| Sprint | Date | Statut | Résultat |
|--------|------|--------|---------|
| Panel System Integration (Session-Plan-2026-02-27) | 2026-02-27 | ✅ Partiel | Panel system intégré, dock-bottom problème identifié |
| **Sprint 0** | 2026-02-27 | ✅ Terminé | dock-bottom supprimé, persist key v4 |
| **Sprint 1** | 2026-02-28 | ✅ Terminé | useStreamController extrait, ControlPanel ~500 LOC |
| **Sprint 2** | 2026-02-28 | ✅ Terminé | AudioPanel horizontal compact, dock-bottom v5 |
| **Sprint 3** | 2026-02-28 | ✅ Terminé | ControlPanel → slim ActionBar 48px, resize supprimé |
| **Sprint 4** | 2026-02-28 | ✅ Terminé | Stats 5s forcées, audio/overlay/markers Deck déjà intégrés |
| **Sprint 5** | 2026-02-28 | ✅ Terminé | Raccourcis F1-F4/Ctrl+G/Ctrl+R/M/Space/?, modal shortcuts, Go Live instant |
| **Sprint 6** | 2026-03-01 | ✅ Terminé | Dual output FFmpeg (tee muxer RTMP+MKV), dualRecord toggle Settings, auto-save metadata.json |
| **Sprint 7** | 2026-03-01 | ✅ Terminé | appStore 1822 LOC → 4 slices Zustand (audioSlice 60L, streamSlice 434L, sceneSlice 274L, sourceSlice 442L) + appStore.types.ts 483L + appStore.ts 174L composition |

---

**Auteur** : Takumi (Claude Sonnet 4.6) — session 2026-02-27/28/03-01
**Prochaine action** : Sprint 8 — Tests & Qualité (Vitest stores, IPC mocking, coverage > 60% chemins critiques)
