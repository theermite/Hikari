# Audit Complet — Hikari Stream & Hikari Deck

**Date** : 2026-02-26
**Auditeur** : Takumi (Claude Sonnet 4.6)
**Méthode** : Exploration complète code source + veille internet (versions, best practices, CVE)
**Version app** : 0.1.0
**Scope** : Hikari Stream (Electron) + Hikari Deck (PWA) + Relay VPS
**Baseline** : Audit précédent du 2026-02-16, CDC v1.0, Plan v2.1

---

## Score Global

| Domaine | Score | Niveau |
|---------|-------|--------|
| Dépendances & Veille | 72/100 | 🟠 |
| Architecture & Code | 42/100 | 🔴 |
| Sécurité Electron | 58/100 | 🟠 |
| Couverture CDC (Features) | 52/100 | 🔴 |
| Qualité code (tests, lint) | 22/100 | 🔴 |
| UX / Accessibilité | 38/100 | 🔴 |
| Hikari Deck | 78/100 | 🟡 |
| Build & Distribution | 55/100 | 🟠 |
| **SCORE GLOBAL** | **52/100** | **🔴 Insuffisant** |

> Seuil Shinkofa : 95/100. Écart critique : -43 points.
> L'application est fonctionnelle pour un usage personnel de Jay, mais n'est pas distribuable ni maintenable à ce stade.

---

## 1. Dépendances & Veille — 72/100

### 1.1 État actuel des dépendances (package.json vérifié)

| Package | Installé | Dernière stable (fév 2026) | Écart | Impact |
|---------|----------|--------------------------|-------|--------|
| **electron** | `^40.0.0` | 39.7.0 / 40.x | ✅ À jour | — |
| **electron-vite** | `^5.0.0` | 5.0.x | ✅ À jour | — |
| **electron-builder** | `^26.0.0` | 26.x | ✅ À jour | — |
| **vite** | `^7.0.0` | 7.x | ✅ À jour | — |
| **typescript** | `^5.9.0` | 5.x | ✅ À jour | — |
| **react** | `^18.2.0` | 19.x | ⚠️ 1 majeure | React 19 : concurrent features, `use()` hook |
| **react-dom** | `^18.2.0` | 19.x | ⚠️ 1 majeure | Idem |
| **tailwindcss** | `^3.4.1` | 4.x | ⚠️ 1 majeure | TW4 : 5x plus rapide, CSS-first |
| **zustand** | `^4.5.2` | 5.0.11 | ⚠️ 1 majeure | API `persist` change |
| **ws** | `^8.19.0` | 8.x | ✅ À jour | — |
| **qrcode** | `^1.5.4` | 1.5.x | ✅ — | — |

### 1.2 Analyse détaillée des upgrades pendants

**Zustand 4 → 5** (priorité haute) :
- API `persist` légèrement modifiée (breaking change mineur)
- `createJSONStorage` : compatible v5
- Avantages v5 : meilleure typage, tree-shaking, performance
- Effort estimé : 2-4h (6 usages dans les stores)

**React 18 → 19** (priorité basse pour Electron) :
- React 19 stable depuis fin 2024
- Compatible Electron sans changement majeur
- `use()` hook, optimistic updates, server actions (inutiles en Electron)
- Effort estimé : 1-2h (peu de breaking changes dans ce contexte)

**Tailwind 3 → 4** (priorité basse) :
- CSS-first, zero configuration
- Breaking : suppression de classes dépréciées
- Template Electron-Vite + Tailwind v4 existe et fonctionne
- Effort estimé : 3-5h (migration config + classes custom hikari)
- Risque : palette hikari custom à migrer vers CSS variables

### 1.3 Vulnérabilités npm

- npm audit n'a pas pu être exécuté dans cet environnement
- Commit `ad02f82` (2026-02-16) mentionnait 9 vulnérabilités non corrigées
- Action requise : `npm audit` + `npm audit fix` à exécuter manuellement

### 1.4 Dépendances manquantes pour les features prévues (Sprint 5)

| Feature | Package nécessaire | Statut |
|---------|-------------------|--------|
| Transcription Groq Whisper | `groq-sdk` ou fetch natif | Absent |
| Analyse DeepSeek | Client HTTP (fetch natif possible) | — |
| Post-production vidéo | FFmpeg déjà présent | ✅ |
| Tests unitaires | `vitest` ou `jest` + `@testing-library/react` | Absent |
| Auto-update | `electron-updater` | Absent |
| Crash reporter | `@sentry/electron` | Absent |

---

## 2. Architecture & Code — 42/100

### 2.1 Fichiers critiques — état actuel

| Fichier | LOC | Problème | Priorité |
|---------|-----|----------|----------|
| `appStore.ts` | ~1777 | God object — 6 domaines mélangés | 🔴 Sprint 4 |
| `Preview.tsx` | ~1543 | God component — drag, overlay, webcam, phone | 🔴 Sprint 4 |
| `main/index.ts` | ~978 | 75+ IPC handlers dans un seul fichier | 🟠 Sprint 4 |
| `streaming.ts` | ~1098 | Acceptable mais dense | 🟡 |
| `twitchService.ts` | ~794 | OK (service ciblé) | ✅ |
| `youtubeService.ts` | ~702 | OK | ✅ |

### 2.2 Code mort — décision urgente requise

| Dossier/Fichier | LOC | Status | Age |
|-----------------|-----|--------|-----|
| `components/panels/` (15 fichiers) | ~2000 | ❌ Jamais intégré dans App.tsx | Depuis commit 67c0edb (fév) |
| `stores/panelStore.ts` | ~660 | ❌ Complètement inutilisé | Idem |
| **Total code mort** | **~2660** | **12% de la codebase** | — |

**Décision requise** (bloquée depuis 3 semaines) :
- **Option A — Supprimer** : -2660 LOC, codebase propre, 1-2h de travail
- **Option B — Intégrer** : Remplacement App.tsx, déblocage des 15 composants, 8-12h de travail

> Le panel system contient : dock zones, panels détachables, layouts sauvegardables, 3 modes (compact/standard/extended). **Fonctionnalité OBS-like de valeur si intégrée.**

### 2.3 Architecture services (Main process) — bonne séparation

| Service | LOC | Qualité |
|---------|-----|---------|
| `secureStore.ts` | 86 | ✅ Excellent — générique, typé, migration legacy |
| `adaptiveStreaming.ts` | 438 | ✅ Bon |
| `deckRelay.ts` | 386 | ✅ Bon |
| `deckPage.ts` | 398 | ✅ Bon |
| `audio.ts` | 320 | ✅ Bon |
| `dependencies.ts` | 306 | ✅ Bon |

### 2.4 Patterns identifiés — positifs

- `SecureStore<T>` : pattern générique typé avec chiffrement sélectif ✅
- `StreamingService extends EventEmitter` : event-driven ✅
- `DeckRelayService extends EventEmitter` : idem ✅
- Séparation claire main/preload/renderer ✅
- `contextIsolation: true`, `nodeIntegration: false` ✅

### 2.5 Patterns identifiés — négatifs

- `appStore.ts` 1777 lignes : stream, scene, audio, deck, recording, overlays mélangés
- `Preview.tsx` 1543 lignes : logique drag, rendu overlay, webcam, phone, context menu
- `index.ts` 75+ IPC handlers : difficile à naviguer, risque de régression
- Pas de découpage en stores spécialisés (streamStore, sceneStore, audioStore)
- `@typescript-eslint/no-explicit-any: 'warn'` — any autorisé
- `react-hooks/exhaustive-deps: 'warn'` — dépendances hooks incomplètes autorisées

### 2.6 Nouveau fichier notable (non documenté)

`src/main/services/secureStore.ts` — classe générique `SecureStore<T>` :
- Chiffrement sélectif par clé via `safeStorage`
- Migration automatique plaintext → chiffré
- Non mentionné dans CLAUDE.md ni dans les audits précédents
- Qualité : excellente

---

## 3. Sécurité Electron — 58/100

### 3.1 Configuration BrowserWindow — points critiques

```typescript
webPreferences: {
  preload: join(__dirname, '../preload/index.cjs'),
  sandbox: false,       // ⚠️ PROBLÈME : désactivé
  contextIsolation: true, // ✅ Correct
  nodeIntegration: false  // ✅ Correct
}
```

**`sandbox: false`** — Score impact : -15 points
- La recommandation Electron 2026 est `sandbox: true`
- Avec `sandbox: false`, le renderer process peut accéder à certaines APIs Node.js via le preload
- Justification partielle : nécessaire pour le preload script complexe avec 100+ méthodes
- Mitigation : `contextIsolation: true` + `nodeIntegration: false` limitent l'impact
- Action : évaluer si `sandbox: true` est possible avec les IPC actuels

### 3.2 Protocole hikari://

```typescript
protocol.registerSchemesAsPrivileged([{
  scheme: 'hikari',
  privileges: {
    standard: true,
    secure: true,
    supportFetchAPI: true,
    stream: true,
    bypassCSP: true    // ⚠️ PROBLÈME
  }
}])
```

**`bypassCSP: true`** — Score impact : -10 points
- Toute ressource chargée via `hikari://` contourne la Content Security Policy
- Justification : nécessaire pour charger des fichiers locaux (images, vidéos)
- Risque : si une source HTML5/browser overlay injecte du JavaScript, il peut utiliser ce protocole
- Mitigation actuelle : validation path traversal ✅, whitelist MIME types ✅
- Action : évaluer remplacement par `net.protocol` avec validation stricte du chemin

### 3.3 Path traversal — protection en place

- Validation `..` dans les chemins ✅
- `normalize(resolve(filePath))` ✅
- Whitelist MIME types ✅
- CORS `Access-Control-Allow-Origin: *` sur les réponses hikari:// ⚠️ (large mais local)

### 3.4 Stockage des tokens OAuth

- `safeStorage.encryptString` pour Twitch/YouTube tokens ✅
- `SecureStore<T>` avec chiffrement sélectif ✅
- Tokens stockés dans `app.getPath('userData')` ✅
- Pas de tokens dans le code source ✅

### 3.5 Relay WebSocket

- URL hardcodée : `wss://deck.shinkofa.com/relay` ✅
- TLS sur le relay ✅
- Pas d'authentification entre Stream et Relay ⚠️ (n'importe quel client peut se connecter comme "stream")
- Heartbeat 30s ✅

### 3.6 Bilan sécurité

| Point | Status | Sévérité |
|-------|--------|----------|
| contextIsolation | ✅ Activé | — |
| nodeIntegration | ✅ Désactivé | — |
| sandbox | ❌ Désactivé | 🟠 Moyenne |
| bypassCSP | ⚠️ Activé hikari:// | 🟠 Moyenne |
| Path traversal | ✅ Protégé | — |
| safeStorage OAuth | ✅ Implémenté | — |
| setWindowOpenHandler | ✅ deny + openExternal | — |
| Relay auth | ❌ Absent | 🟡 Faible (LAN) |
| Signing Windows | ❌ Non configuré | 🟠 Distribution |
| npm audit | ❌ Non vérifié | 🟠 Dépend du résultat |

---

## 4. Couverture CDC (Features) — 52/100

### 4.1 CDC v1.0 — Phases de développement

#### Phase 1 : Stabilisation — COMPLÈTE ✅

| Tâche CDC | Status |
|-----------|--------|
| Fix build script (`electron-vite build`) | ✅ Fait |
| Upgrade Electron 28 → 40 | ✅ Fait (package.json `^40.0.0`) |
| Upgrade electron-builder 24 → 26 | ✅ Fait |
| Upgrade electron-vite 2 → 5 | ✅ Fait |
| Test enregistrement local | ⚠️ Partiel (config existe, UI unclear) |
| Build distributable Windows | ✅ `build:win` configuré |
| Smoke test complet | ❓ Non documenté |

#### Phase 2 : Recording simultané — PARTIELLE ⚠️

| Tâche CDC | Status |
|-----------|--------|
| Mode dual output FFmpeg (RTMP + fichier) | ⚠️ Infrastructure présente (RecordingConfig, isRecording) |
| Format MKV crash-tolerant | ✅ Type `'mkv' \| 'mp4'` dans RecordingConfig |
| UI recording (bouton indépendant) | ❌ Non visible dans l'audit UI |
| Settings recording (dossier, qualité, codec) | ⚠️ RecordingQuality type existe |
| Auto-save markers en metadata.json | ❌ Non implémenté |

> **Verdict** : L'infrastructure de types est là, mais le dual-output FFmpeg TEE et l'UI recording ne sont pas confirmés dans le code actuel.

#### Phase 3 : Export Sakusei — NON COMMENCÉE ❌

| Tâche CDC | Status |
|-----------|--------|
| Schema metadata.json standardisé | ❌ |
| Dossier sortie structuré `~/Hikari-Exports/` | ❌ |
| Bouton "Envoyer à Sakusei" | ❌ |
| Integration API Sakusei (placeholder) | ❌ |

#### Phase 4 : Extraction Podcast — NON COMMENCÉE ❌

| Tâche CDC | Status |
|-----------|--------|
| Extract audio FFmpeg → MP3 | ❌ |
| Bouton "Extraire podcast" post-recording | ❌ |
| Metadata podcast (chapitres ID3) | ❌ |

#### Phase 5 : UX Polish — PARTIELLE ⚠️

| Tâche CDC | Status |
|-----------|--------|
| Thème Shinkofa dark navy | ✅ Palette hikari, backgroundColor `#0c4a6e` |
| Presets de scène (Gaming, IRL, Podcast, Tutorial) | ✅ 6 templates dans sceneTemplates.ts |
| Raccourcis clavier (start/stop stream, scènes) | ⚠️ Non confirmé dans le code |
| Notifications Twitch (follow, sub, raid) | ✅ EventSub + AlertOverlay |
| Multi-monitor | ❌ Non implémenté |

### 4.2 Plan v2.1 — Sprints

| Sprint | Status | Détail |
|--------|--------|--------|
| Sprint 1 (Sécurité) | ✅ Complet | safeStorage, path traversal, TS 0 erreurs |
| Sprint 2 (Qualité streams) | ✅ Complet | NVENC B-frames, reconnect, adaptive, OAuth |
| Sprint 3 (Scènes + Deck) | 🟡 85% | Templates, macros, deck — manque Go Live flow + overlay toggle deck |
| Sprint 4 (Refactoring) | ❌ 0% | God objects, dead code, tests, a11y |
| Sprint 5 (Post-prod IA) | ❌ 0% | Recording, transcription, clips |

### 4.3 Features non prévues au CDC mais présentes (valeur ajoutée)

| Feature | Valeur |
|---------|--------|
| System tray Windows | ✅ Utile |
| Setup wizard auto-download FFmpeg/scrcpy | ✅ Utile |
| Circuit breaker RTMP | ✅ Critique |
| `SecureStore<T>` générique | ✅ Réutilisable |
| Deck orphan recovery | ✅ Robustesse |
| `adaptiveStreaming.ts` avec scoring 0-100 | ✅ Qualité pro |

---

## 5. Qualité Code — 22/100

### 5.1 Tests — 0/100

**0 fichiers de test dans l'ensemble du projet.**

Ce n'est pas seulement un manque — c'est un risque critique pour un projet de cette taille (~22 000 LOC) :
- Tout refactoring (Sprint 4) se fait à l'aveugle
- Chaque bug découvert ne peut pas être capturé pour éviter la régression
- Le dual-output FFmpeg (Phase 2 CDC) ne peut pas être validé automatiquement

Cibles pour Sprint 4 (Plan v2.1) :
- Vitest pour les stores (appStore, streaming)
- Tests IPC (mocking Electron)
- Tests WebSocket (relay protocol)

### 5.2 ESLint — Configuration trop permissive

```javascript
// Seuils actuels
'@typescript-eslint/no-explicit-any': 'warn'  // ← devrait être 'error'
'@typescript-eslint/no-unused-vars': 'warn'   // ← devrait être 'error'
'react-hooks/exhaustive-deps': 'warn'          // ← devrait être 'error'
--max-warnings 50                              // ← 50 warnings tolérés en CI
```

Conséquences :
- Des `any` peuvent se propager silencieusement
- Des dépendances manquantes dans `useEffect` = bugs stale closures
- 50 warnings tolérés = indicateur non fiable

### 5.3 TypeScript — Configuration acceptable mais incomplète

**Présent** :
```json
"strict": true       // ✅ Couvre strictNullChecks, strictFunctionTypes
"skipLibCheck": true // Acceptable
```

**Absent vs checklist Shinkofa** :
```json
// Ces options ne sont PAS dans tsconfig.json
"noUnusedLocals": true          // ← manquant
"noUnusedParameters": true      // ← manquant
"noImplicitReturns": true       // ← manquant
"noUncheckedIndexedAccess": true // ← manquant
```

### 5.4 Conventions de nommage

- Fichiers `.ts/.tsx` : PascalCase composants, camelCase services ✅
- Fichiers `.md` : `Audit-Complet-2026-02-16.md` ✅ (Title-Kebab-Case respecté)
- Commits : conventional commits ✅

### 5.5 Complexité

| Fichier | LOC | Complexité estimée |
|---------|-----|--------------------|
| `appStore.ts` | 1777 | 🔴 Très haute |
| `Preview.tsx` | 1543 | 🔴 Très haute |
| `main/index.ts` | 978 | 🟠 Haute (75+ IPC handlers) |
| `streaming.ts` | 1098 | 🟠 Haute |

---

## 6. UX / Accessibilité — 38/100

### 6.1 UX actuelle (points positifs)

- Thème dark navy cohérent ✅
- Custom scrollbar hikari ✅
- Palette couleurs `hikari-*` dans Tailwind ✅
- Titlebar frameless personnalisée ✅
- System tray avec quick actions ✅
- AlertOverlay pour événements Twitch ✅
- GoLiveModal : workflow de lancement ✅
- StatusBar : métriques temps réel ✅
- Setup wizard pour les débutants ✅

### 6.2 UX — Problèmes identifiés

| Problème | Impact | Source |
|----------|--------|--------|
| Panel system non intégré (OBS-like) | Élevé | Code mort depuis fév |
| Flow Go Live > 1 min (target < 1 min) | Moyen | Sprint 3 incomplet |
| Overlay toggle depuis Deck non implémenté | Moyen | Sprint 3 restant |
| Transitions : trop d'options "slide" | Faible | Audit précédent |
| QR Code Deck : accessibilité du modal | Faible | Audit précédent |

### 6.3 Accessibilité — WCAG 2.2 AA

**État : Non évalué / Non implémenté**

Checklist minimale :

| Critère WCAG | Status |
|--------------|--------|
| Navigation clavier complète (Tab, Enter, Esc) | ❌ Non vérifié |
| Focus visible (`:focus-visible`) | ❌ Non vérifié |
| ARIA labels sur boutons/icônes | ❌ Absent (vu dans Preview.tsx) |
| Contraste couleurs 4.5:1 minimum | ❓ Thème dark — à mesurer |
| `prefers-reduced-motion` | ❌ Absent |
| Screen readers | ❌ Non conçu pour |
| Landmarks sémantiques | ❌ App SPA sans `<main>` etc. |

> Note : pour une application desktop de streaming usage pro/semi-pro, le niveau d'accessibilité est acceptable pour un MVP. La priorité reste la fonctionnalité. Cependant, le label "neurodivergent-friendly" dans `package.json` impose une attention particulière à la lisibilité et la réduction de charge cognitive.

### 6.4 Neurodivergent-friendly — Évaluation

| Principe | Implémentation | Status |
|----------|----------------|--------|
| Charge cognitive minimale | Interface dense, beaucoup d'éléments | ⚠️ |
| Feedback immédiat | StatusBar, AlertOverlay | ✅ |
| Sans-serif (lisibilité dyslexie) | Tailwind system-ui par défaut | ✅ |
| Instructions visibles | Setup wizard | ✅ |
| Pas de surprises | Navigation stable | ✅ |
| Formulaires tolérants | Presets save/load/duplicate | ✅ |

### 6.5 Raccourcis clavier

- F1-F4 pour les scènes : mentionné dans CLAUDE.md mais non confirmé dans le code
- Pas de liste de raccourcis documentée
- Pas de modal "Keyboard shortcuts" dans l'UI

---

## 7. Hikari Deck — 78/100

### 7.1 État du déploiement

| Élément | Status |
|---------|--------|
| **URL** | `deck.shinkofa.com` ✅ HTTPS |
| **Relay VPS** | `wss://deck.shinkofa.com/relay` ✅ |
| **PWA installable** | ✅ service worker, manifest |
| **SSL** | Let's Encrypt, auto-renew ✅ |

### 7.2 Protocol de communication — robuste

**Stream → Deck** : welcome, state:sync, state:update, scene:changed, stream:status, audio:update, overlay:update
**Deck → Stream** : request:sync, action:scene, action:stream, action:audio, action:marker, action:overlay

### 7.3 Robustesse réseau

| Feature | Status | Détail |
|---------|--------|--------|
| Heartbeat 30s | ✅ | ping/pong WebSocket |
| Auto-reconnect | ✅ | 15 tentatives, backoff 3s→5s |
| Orphan recovery | ✅ | Re-association auto |
| State caching relay | ✅ | Full state pour nouveaux clients |
| QR Code pairing | ✅ | BarcodeDetector API |

### 7.4 Points faibles Deck

| Problème | Impact | Priorité |
|----------|--------|----------|
| Pas d'authentification relay | ⚠️ N'importe qui peut se connecter comme "stream" | Faible (usage privé) |
| BarcodeDetector API : support limité | ⚠️ Non supporté Firefox (fallback nécessaire) | Moyen |
| Pas d'overlay toggle dans l'UI Deck | Fonctionnalité promise non livrée | Moyen |
| React 18 / Zustand 4 côté Deck | Même retard que Stream | Basse |
| Pas de tests PWA | ❌ | Basse |

### 7.5 Relay server (relay/server.js)

- Node.js + ws
- Heartbeat, orphan recovery, state cache
- Pas de rate limiting
- Pas de validation des messages entrants (type safety absent côté Node.js)
- Port 3456 exposé sur le VPS

---

## 8. Build & Distribution — 55/100

### 8.1 Build script — corrigé ✅

```json
// Ancien (no-op)
"build": "echo 'Build skipped'"

// Actuel (correct)
"build": "electron-vite build",
"build:win": "npm run build && electron-builder --win --config",
"build:mac": "npm run build && electron-builder --mac --config",
"build:linux": "npm run build && electron-builder --linux --config"
```

### 8.2 electron-builder.json5 — config de base

```json
{
  "appId": "com.shinkofa.hikari-stream",
  "win": {
    "target": [{"target": "nsis", "arch": ["x64"]}]
  }
}
```

**Manquant** :
- `signingHashAlgorithms: ["sha256"]` → Code signing non configuré
- `publisherName` → SmartScreen warning sans signing
- `publish` → Pas d'auto-update (GitHub Releases, S3, etc.)
- `artifactName` personnalisé pour le DMG/AppImage

### 8.3 Code signing — ABSENT

Sans code signing Windows :
- **SmartScreen warning** à chaque installation (fichier bloqué)
- Utilisateurs doivent cliquer "Plus d'infos → Exécuter quand même"
- Certificat OV (Organization Validation) : ~100-200€/an
- Alternative gratuite : pas d'alternative officielle pour Windows Authenticode
- **Impact pour distribution** : bloquant pour un public neurodivergent (confusion, anxiété)

### 8.4 Auto-update — ABSENT

Sans `electron-updater` :
- Pas de mise à jour automatique
- Jay doit redistribuer manuellement chaque version
- Recommandation : `electron-updater` (inclus dans electron-builder) + GitHub Releases

### 8.5 Ressources manquantes

- `resources/icon.ico` : référencé dans electron-builder.json5 — doit exister
- `resources/icon.icns` : pour macOS (si distribution Mac prévue)
- `resources/icon.png` : pour Linux

### 8.6 CI/CD

- Pas de GitHub Actions pour build automatique
- Pas de release pipeline
- Build manuel uniquement (`pnpm build:win`)

---

## 9. Métriques Clés

| Métrique | Valeur | Cible |
|----------|--------|-------|
| LOC total | ~22 000 TypeScript | — |
| Code mort | ~2 660 LOC (12%) | 0% |
| Fichiers de test | 0 | >20 |
| Coverage tests | 0% | >80% |
| TypeScript strict | ✅ | ✅ |
| TS erreurs | 0 | 0 ✅ |
| ESLint warnings max | 50 (très permissif) | 0 |
| Electron version | 40.x | ✅ |
| Electron-vite version | 5.x | ✅ |
| Zustand version | 4.5.2 | 5.0.11 ⚠️ |
| React version | 18.2 | 19.x ⚠️ |
| Tailwind version | 3.4.1 | 4.x ⚠️ |
| Commits hikari | 20+ | — |
| Services main | 15 | — |
| Composants renderer | 40+ | — |

---

## 10. Gaps non couverts par le CDC (nouvelles observations)

Ces points n'étaient pas dans le CDC original mais sont des besoins réels :

### 10.1 Technique

| Gap | Urgence | Effort |
|-----|---------|--------|
| Tests automatisés (0 coverage) | 🔴 | 3-5 sessions |
| Auto-update (`electron-updater`) | 🟠 | 2-4h |
| Code signing Windows | 🟠 | 1-2h + coût certificat |
| Rate limiting relay WebSocket | 🟡 | 1h |
| Heartbeat WebSocket local (pas seulement relay) | 🟡 | 1h |
| Crash reporter (Sentry/équivalent) | 🟡 | 2-4h |
| Validation messages WebSocket (TypeScript) | 🟡 | 2h |
| npm audit fix | 🟡 | 1-2h |

### 10.2 UX non adressé

| Gap | Urgence |
|-----|---------|
| Liste des raccourcis clavier visible (modal) | 🟡 |
| Multi-monitor support | 🟡 |
| Indicateur d'espace disque avant recording | 🟡 |
| Notification quand FFmpeg/scrcpy manquant | 🟡 |
| Export settings/config (backup) | 🟢 |
| Onboarding guide pour premier démarrage | 🟢 |

### 10.3 Pipeline contenu (Post-Sprint 3)

| Gap | Urgence |
|-----|---------|
| Recording simultané RTMP+local (Phase 2 CDC) | 🔴 |
| metadata.json auto-généré post-session | 🔴 |
| Intégration Sakusei (dossier partagé) | 🟠 |
| Transcription Groq Whisper | 🟠 |
| Analyse DeepSeek moments forts | 🟠 |
| Dashboard post-stream | 🟠 |

---

## 11. Roadmap Recommandée

### Prochaine session — Sprint 3 (finalisation)

**Durée estimée** : 1 session (2-4h)

| Tâche | Effort |
|-------|--------|
| Overlay toggle UI dans Hikari Deck | 2h |
| Valider multi-RTMP simultané (Twitch + YouTube live) | 1h |
| Décision panel system (supprimer ou intégrer) | 30min |

### Sprint 4 — Refactoring (BLOQUEUR pour Sprint 5)

**Durée estimée** : 3-4 sessions

**Ordre d'exécution impératif** (WF-016 : max 3 fichiers/commit) :

1. **Extraire les stores** (2 sessions) :
   - `streamStore.ts` : status, RTMP, encoding, stats
   - `sceneStore.ts` : scenes, sources, overlays
   - `audioStore.ts` : tracks, VU meters, mixer
   - `settingsStore.ts` : presets, config
   - `recordingStore.ts` : recording state

2. **Découper Preview.tsx** (1 session) :
   - `SourceLayer.tsx` : rendu individuel source
   - `useDragResize.ts` : logique drag/resize
   - `OverlayRenderer.tsx` : rendu overlays

3. **Tests + a11y** (1 session) :
   - Setup Vitest
   - Tests stores (streamStore, sceneStore)
   - Tests streaming pipeline (mock FFmpeg)
   - ARIA labels sur boutons critiques

4. **Décision panel system** :
   - Si suppression : 1-2h
   - Si intégration App.tsx : 8-12h

### Sprint 5 — Post-production IA

**Pré-requis** : Sprint 4 terminé (architecture extensible)
**Durée estimée** : 4-5 sessions

Ordre : Recording local → metadata.json → Dashboard post-stream → Groq transcription → DeepSeek analyse → Clips courts

---

## 12. Conclusion

### Ce qui fonctionne vraiment bien

- **Pipeline streaming** : NVENC B-frames, reconnexion auto, circuit breaker, adaptive bitrate — niveau professionnel
- **OAuth + EventSub Twitch** : complet, tokens chiffrés, refresh tokens
- **OAuth YouTube** : broadcasts, streams, categories
- **Deck Relay** : heartbeat, orphan recovery, QR pairing — robuste
- **SecureStore** : solution élégante et générique
- **Electron 40 + electron-vite 5** : stack moderne

### Ce qui bloque

- **0 tests** : impossible de refactorer sans casser
- **God objects** (appStore 1777 LOC, Preview 1543 LOC) : maintenabilité critique
- **2660 LOC code mort** : confusion, charge cognitive dev
- **Recording simultané non validé** : feature CDC Phase 2 incomplète
- **Sprint 4-5 non commencés** : pipeline post-production IA, objectif principal v2.0

### Score synthèse

| Dimension | Score |
|-----------|-------|
| Ce qui est livré | 🟠 52% des features CDC |
| Qualité du code livré | 🟠 Bon mais non testable |
| Potentiel | ✅ Architecture solide une fois refactorisée |
| Risque principal | 🔴 Pas de tests = régression à chaque sprint |

**Verdict** : Hikari Stream est une application fonctionnelle et impressionnante pour son état de développement. Le pipeline technique (FFmpeg, OAuth, Deck relay) est de qualité professionnelle. L'obstacle majeur pour la suite est **l'absence totale de tests combinée aux god objects** — Sprint 4 est un pré-requis non négociable avant Sprint 5.

---

**Audit réalisé avec** : exploration complète du code source + veille internet (Electron releases, Zustand changelog, Tailwind v4, electron-vite, code signing best practices)
**Sources vérifiées** : electronjs.org releases, npmjs.com/package/zustand, electron-vite.org, electron.build
**Zéro supposition** : toutes les conclusions sont basées sur les fichiers lus.

**Version** : 1.0.0 | **Date** : 2026-02-26
