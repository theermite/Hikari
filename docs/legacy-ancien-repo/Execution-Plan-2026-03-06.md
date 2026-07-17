# Plan d'Exécution — Hikari Stream Revival

**Date** : 2026-03-06
**Objectif** : Rendre Hikari Stream fonctionnel pour streamer quotidiennement sur Twitch
**Philosophie** : SRE (Simple, Rapide, Efficace) — seul le résultat compte

---

## Contexte

L'architecture CanvasCompositor (Option 3) est **déjà le pipeline actif**. Ce n'est pas du code déconnecté à brancher — c'est le chemin principal dans `handleStartStream()`. La question est : **pourquoi ça ne fonctionne pas en pratique ?**

### Pipeline actuel (déjà câblé)

```
handleStartStream() (useStreamController.ts:~150)
  1. AudioMixer.start()          → Web Audio API → PCM s16le → TCP localhost → FFmpeg
  2. window.api.startCanvasStream()  → FFmpeg spawn (mux-only, pipe:0 IVF + TCP audio)
  3. 300ms yield                 → React relâche les MediaStreams
  4. canvasCompositor.start()    → OffscreenCanvas + VP9 WebCodecs → IVF chunks → IPC → FFmpeg stdin
```

### Ce qui fonctionne (vérifié dans le code)

- CanvasCompositor : composition multi-sources sur OffscreenCanvas (**src/renderer/src/services/CanvasCompositor.ts**)
- VP9 encoding avec level dynamique (`getVP9Level()`)
- IVF muxer custom (32B header + 12B frame headers)
- Scene switching instantané via `updateConfig()` (pas de restart FFmpeg)
- Audio mute/volume instantané via AudioMixer GainNodes
- FFmpeg mux-only (`-f ivf -i pipe:0` + TCP audio → RTMP output)
- Dual output (tee muxer : RTMP + MKV local)
- 380 tests, 87% coverage, build OK

### Ce qui est reporté cassé par Jay

1. Preview ≠ stream output
2. Sources qui cassent entre scènes
3. Impossible de modifier pendant le live
4. Audio routing cassé
5. Pas de custom RTMP keys
6. Pas de streaming vertical
7. Pas de support TikTok

---

## Phase 0 — Diagnostic (session courante)

**Objectif** : Identifier les vrais blockers en lançant l'app et en testant

### Actions

| # | Action | Vérification |
|---|--------|-------------|
| 0.1 | Fixer 2 tests en échec (sceneSlice overlay, streamSlice markdown) | `pnpm test:run` → 380/380 |
| 0.2 | Commit les changements non-commités de `streaming.ts` | `git diff --stat` → clean |
| 0.3 | `pnpm dev` → lancer l'app | Fenêtre Electron s'ouvre |
| 0.4 | Créer une scène basique (screen capture) | Preview affiche le bureau |
| 0.5 | Test Stream 10s (bouton StatusBar) | Vérifier fichier MP4 généré |
| 0.6 | Go Live test (Twitch ou RTMP local) | Stream visible sur la plateforme |
| 0.7 | Documenter CHAQUE erreur (logs main + renderer console) | Liste des blockers réels |

### Diagnostic ciblé

Si le test stream échoue, vérifier dans cet ordre :
1. **FFmpeg installé ?** → `dependencies.ts` installe automatiquement, vérifier via logs
2. **VP9 encoder output ?** → Regarder `queueSize` dans les logs compositor. Si queueSize monte sans output = VP9 level bug
3. **IPC chunks arrivent ?** → Logs main process `writeVideoChunk` appelé ?
4. **Audio TCP connecté ?** → Logs `audioMixer` TCP connection established ?
5. **RTMP handshake ?** → FFmpeg stderr logs, chercher `Output #0`

---

## Phase 1 — Fixes critiques (post-diagnostic)

À adapter selon les résultats de Phase 0. Actions probables :

| # | Action | Estimation |
|---|--------|-----------|
| 1.1 | Fix VP9 encoding si level incorrect | 1-2h |
| 1.2 | Fix IPC video chunks (backpressure, timing) | 1-2h |
| 1.3 | Fix audio TCP routing | 1h |
| 1.4 | Ajouter custom RTMP key support | 1h |
| 1.5 | Ajouter streaming vertical (portrait mode) | 2h |
| 1.6 | Fix scene switching en live | 1h |

---

## Phase 2 — Stream quotidien (objectif final)

| # | Action | Estimation |
|---|--------|-----------|
| 2.1 | Test stream 30min sur Twitch | 1 session |
| 2.2 | Fix tout ce qui casse pendant le test 30min | variable |
| 2.3 | Ajouter TikTok RTMP (custom RTMP = automatique) | 30min |
| 2.4 | Valider dual recording (stream + local MKV) | 30min |

---

## Veille technique confirmée (2026-03-06)

| Technologie | Version actuelle | Hikari utilise | Action |
|-------------|-----------------|----------------|--------|
| Electron | 40.8.0 (Chromium 144, Node 24) | ^40.0.0 | OK, à jour |
| React | 19.1.0 stable | 18.2.0 | Upgrade recommandé mais pas urgent |
| Tailwind | 4.1.x | 3.4 | Upgrade recommandé mais pas urgent |
| Zustand | 5.0.5 | 4.5.2 | NE PAS UPGRADER (persist breaking change) |
| electron-vite | 5.0 | 5.0 | OK |
| electron-builder | 26.x | 26.x | Rester (pas Forge) |
| fluent-ffmpeg | ARCHIVÉ (mai 2025) | Non utilisé | Hikari utilise child_process.spawn (correct) |

### Concurrents

| App | Approche | Point fort | Point faible |
|-----|---------|-----------|-------------|
| OBS | C++ natif, libobs | Performance, plugins | UX complexe |
| Meld Studio | Custom DX12, pas OBS | UX moderne | Pas VST, jeune |
| Prism (NAVER) | Fork OBS Qt, GPL | Open source, features | Passe payant |
| Streamlabs | libobs + Electron/Vue | UX simple | +20-30% CPU, $27/mois |
| XSplit | C++ custom | Fiable | Payant, vieillissant |

---

## Fichiers clés à connaître

| Fichier | LOC | Rôle |
|---------|-----|------|
| `src/renderer/src/services/CanvasCompositor.ts` | ~750 | Composition video, VP9 encoding, IVF muxer |
| `src/main/services/streaming.ts` | ~1500 | FFmpeg spawn, RTMP, tee muxer |
| `src/renderer/src/hooks/useStreamController.ts` | ~830 | Orchestration start/stop, scene switching, audio |
| `src/renderer/src/services/AudioMixer.ts` | ~300 | Web Audio API, PCM TCP |
| `src/renderer/src/services/IVFMuxer.ts` | ~100 | Container IVF pour VP9 |
| `src/main/services/ffmpeg.ts` | ~400 | Process management, encoder detection |

---

## Règles de discipline

1. **Un blocage = logs d'abord** (WF-003). Pas de suppositions.
2. **Chaque fix = test** avant de passer au suivant.
3. **Pas de refactoring** — on fixe ce qui empêche de streamer, rien d'autre.
4. **Documenter chaque découverte** dans ce fichier (section "Journal Phase 0").
5. **Si bloqué > 15min** → escalader, changer d'approche.

---

## Journal Phase 0

_À remplir pendant le diagnostic_

```
[YYYY-MM-DD HH:MM] — Description du test — Résultat — Action
```
