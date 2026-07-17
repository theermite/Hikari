# Guide de Reprise — Hikari Stream

> Instructions pour reprendre le developpement a la prochaine session.
> Derniere mise a jour : 2026-02-18

---

## Etat actuel

**Version** : 0.1.0 | **Branch** : master | **Status** : Dev local, non distribue

**Derniers commits** :
- `07635f7` refactor(hikari-stream): audit qualite phase 5 — 4 anti-patterns corriges
- `4f11b87` refactor(hikari-stream): audit qualite — fix 3 bugs, 12 issues critiques, -1400 LOC code mort

**Ce qui fonctionne** : Streaming Twitch/YouTube, scenes (6 templates), audio mixing, overlays, webcam, mobile casting (scrcpy), adaptive streaming, mobile deck, system tray, markers, ConfirmDialog custom, signaux Zustand cross-composants.

**Ce qui ne fonctionne PAS** :
- **Erreur JavaScript au lancement** (apparue apres audit phase 5 — A INVESTIGUER EN PRIORITE)
- Build script casse (`echo skip` au lieu de `electron-vite build`)
- Recording local en mode test uniquement (pas en simultane avec stream)
- Electron obsolete (28.2.0 → 40+)
- 0 tests, 0 fichiers de test

---

## Prochaine session : PRIORITE — Fix erreur JS au lancement

### Etape 1 : Investiguer l'erreur JS

L'erreur est apparue apres l'audit qualite phase 5 (commit `07635f7`). Changements suspects :
1. **CustomEvent → Zustand signals** : ControlPanel.tsx ecoute `requestToggleStream`/`requestToggleRecording` via useEffect + useRef counters
2. **ConfirmProvider** wrapping App.tsx
3. **console.log removes** dans appStore.ts (rehydration logs)
4. **SourceIcon** import change dans Sidebar.tsx et SourcesPanel.tsx

**Methode debug** :
```bash
pnpm dev
# Ouvrir DevTools (Ctrl+Shift+I) → Console → lire l'erreur exacte
# Comparer avec commit precedent si necessaire : git stash && git checkout 4f11b87
```

### Etape 2 : Phase 1 — Stabilisation (apres fix)

1. Fix build script (`package.json:10`)
2. Veille Electron 28→40 (WF-029)
3. Upgrade Electron incremental
4. Upgrade deps (React 18→19, Tailwind 3→4)
5. Build Windows : `pnpm build:win`

---

## Audit qualite complete (2026-02-18) — Resume

### Phase 1-4 (commit `4f11b87`) : -1400 LOC

| Categorie | Corrections |
|-----------|-------------|
| **Bugs** (3) | ScenesPanel crash undefined scene, AudioPanel NaN volume, StatusBar division by zero |
| **Issues critiques** (12) | useEffect deps manquants, state mutations directes, memory leaks intervals, race conditions |
| **Code mort** (-1400 LOC) | panelStore.ts (660L), 14 composants panels non integres |
| **Architecture** | Shared types extraits, imports nettoyes |

### Phase 5 (commit `07635f7`) : -107 LOC

| Correction | Detail |
|-----------|--------|
| **CustomEvent → Zustand** | 5 dispatch sites + 3 listeners → signaux Zustand (counters + pendingPreset) |
| **confirm() → ConfirmDialog** | 3 usages migres vers modal React theme hikari |
| **console.log cleanup** | 72 → 13 intentionnels (-52 lignes en 11 fichiers) |
| **SourceIcon unifie** | 2 copies → 1 composant partage data-driven |

**Total audit** : -1507 LOC, 18 fichiers nettoyes, 2 composants crees, 0 erreur TypeScript

---

## Fichiers cles a connaitre

| Fichier | Role | Notes |
|---------|------|-------|
| `src/main/index.ts` | Entrypoint, 75+ IPC handlers | 978 LOC |
| `src/main/services/streaming.ts` | Pipeline FFmpeg, RTMP, recording | 1,098 LOC |
| `src/renderer/src/stores/appStore.ts` | State Zustand central | ~1,800 LOC, signaux cross-composant |
| `src/renderer/src/components/ControlPanel.tsx` | Controles stream/recording | Ecoute signaux Zustand (useRef counters) |
| `src/renderer/src/hooks/useConfirm.tsx` | **NOUVEAU** — Modal confirmation custom | ConfirmProvider dans App.tsx |
| `src/renderer/src/components/SourceIcon.tsx` | **NOUVEAU** — Icone source partagee | Data-driven SVG paths |
| `src/renderer/src/App.tsx` | Layout principal | Wrappe dans ConfirmProvider |

---

## Commandes utiles

```bash
pnpm dev              # Lancer en dev (HMR)
pnpm build:win        # Build Windows .exe
pnpm typecheck        # TypeScript check (0 erreurs attendues)
pnpm lint             # ESLint (max 50 warnings)
```

---

**Chemin projet** : `D:\30-Dev-Projects\Shinkofa-Ecosystem\apps\hikari-stream\`
**CDC** : `docs/CDC-Hikari-Stream.md`
**Audit** : `docs/Audit-Factuel-2026-02-16.md`
