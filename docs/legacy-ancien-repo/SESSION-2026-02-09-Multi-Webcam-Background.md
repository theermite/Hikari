# Session Hikari Stream - 2026-02-09
## Multi-Webcam + Background + Optimisations Performance

**Durée**: ~6h
**Commit**: `3b15def` - feat(hikari): Multi-webcam + background + optimisations performance
**Statut**: Pause - Investigation en cours

---

## 🎯 Objectifs Initiaux

1. ✅ Implémenter multi-webcam (2+ webcams simultanées dans stream)
2. ✅ Afficher background (image/vidéo) dans preview ET stream
3. ✅ Optimiser fluidité des caméras
4. ⚠️ Aligner position téléphone preview ↔ stream
5. ⚠️ Corriger problème persistence (webcams/background disparaissent)

---

## ✅ Réalisations

### 1. Multi-Webcam Support Complet

**Problème Initial**: Une seule webcam supportée, deuxième webcam montrait placeholder

**Solution Implémentée**:
- **ControlPanel.tsx**: Passe array de toutes webcams activées (au lieu d'une seule)
  ```typescript
  webcams: webcams.filter(w => w.enabled && w.deviceId).map(...)
  ```
- **streaming.ts**:
  - Type `StreamConfig.webcams[]` ajouté (backward compatible avec `webcam`)
  - Boucle `forEach` sur chaque webcam pour créer inputs dshow
  - Filter_complex: overlay pour chaque webcam avec labels uniques
- **Preview.tsx**:
  - Maps scalables: `webcamRefsMap`, `webcamStreamsMap`
  - useEffect refactoré: gestion individuelle de chaque stream
  - IIFE pour async operations (évite race conditions)
  - Callback refs pour assignment dynamique

**Résultat**: 2 webcams s'affichent correctement dans preview ET stream ✅

---

### 2. Background (Couleur/Image/Vidéo)

**Problème Initial**: Background seulement couleur, images/vidéos bloquées par sécurité

**Solution Implémentée**:

#### A. Protocol Handler Custom (main process)
**Fichier**: `src/main/index.ts`

```typescript
protocol.handle('hikari', async (request) => {
  let filePath = request.url.replace('hikari://', '')
  filePath = decodeURIComponent(filePath).replace(/\//g, '\\')

  const data = await readFile(filePath)
  const ext = extname(filePath).toLowerCase()
  const mimeType = mimeTypes[ext] || 'application/octet-stream'

  // Range requests pour vidéos (HTTP 206)
  const rangeHeader = request.headers.get('range')
  if (rangeHeader) {
    // Parse bytes=start-end, read chunk, return 206
  }

  return new Response(data, {
    headers: { 'Content-Type': mimeType, 'Accept-Ranges': 'bytes' }
  })
})
```

**Clés**:
- Conversion Windows paths: backslashes → forward slashes → backslashes (pour readFile)
- Range requests pour seeking vidéo (crucial pour `<video>`)
- MIME types automatiques selon extension

#### B. CSP Update
**Fichier**: `src/renderer/index.html`

```html
img-src 'self' data: hikari:
media-src 'self' data: hikari:
```

#### C. URL Helper (renderer)
**Fichier**: `src/renderer/src/components/Preview.tsx`

```typescript
const toHikariUrl = (filePath: string): string => {
  const normalized = filePath.replace(/\\/g, '/')
  const encoded = encodeURIComponent(normalized)
  return `hikari://${encoded}`
}

// Usage
<img src={toHikariUrl(background.imagePath)} />
<video src={toHikariUrl(background.videoPath)} />
```

**Résultat**: Background image/vidéo fonctionne dans preview ✅

---

### 3. Optimisations Performance

**Problème Initial**: Fluidité 80-85%, frame drops constants (buffer full)

**Changements**:

**Fichier**: `src/main/services/streaming.ts`

```typescript
// Webcam capture
args.push(
  '-f', 'dshow',
  '-rtbufsize', '250M',           // ↑ 100M → 250M
  '-thread_queue_size', '1024',   // ↑ Nouveau
  '-i', videoArg
)

// NVENC encoder
args.push(
  '-preset', 'p4',
  '-tune', 'll',
  '-rc', 'cbr',
  '-zerolatency', '1',    // ↑ Nouveau (latence minimale)
  '-delay', '0',          // ↑ Nouveau (no B-frames delay)
  '-bf', '0',             // ↑ Nouveau (no B-frames)
  '-spatial_aq', '1',     // ↑ Nouveau (qualité adaptative)
  '-temporal_aq', '1'     // ↑ Nouveau
)
```

**Résultat**:
- Frame drops réduits (70-95% buffer vs 70-103% avant)
- Fluidité perçue: 95%+ ✅
- FPS stable: 31fps, speed: 1.03-1.06x

---

## ⚠️ Problèmes Identifiés (Non Résolus)

### 1. Persistence Défaillante 🚨 CRITIQUE

**Symptôme**: Webcams + background disparaissent au redémarrage app

**Investigation**:
- `partialize`: webcams ✅, background ✅ (sauvegardés dans localStorage)
- `merge`:
  - webcams restaurés via `validWebcams` ✅
  - background restauré via `persisted.background || currentState.background` ✅

**Hypothèses**:
1. **Validation trop stricte**:
   ```typescript
   validWebcams = persisted.webcams.filter(w =>
     typeof w.deviceId === 'string'  // ← Si deviceId vide, filtré!
   )
   ```
   Si webcams n'ont plus deviceId au redémarrage, elles sont filtrées.

2. **localStorage pas écrit**: Zustand persist ne sauvegarde pas (vérifier hooks)

**Logs Debug Ajoutés** (à vérifier au prochain démarrage):
```typescript
console.log('[AppStore] Persisted webcams before validation:', persisted.webcams)
console.log('[AppStore] Valid webcams after validation:', validWebcams)
console.log('[AppStore] Persisted background:', persisted.background)
```

**TODO Prochaine Session**:
- Relancer app, vérifier console DevTools pour logs `[AppStore]`
- Si validation filtre tout: assouplir critères ou pré-remplir deviceId
- Si localStorage vide: vérifier Zustand persist config

---

### 2. Position Téléphone - Décalage Preview ↔ Stream

**Symptôme**: Téléphone apparaît à des endroits différents dans preview vs stream

**Investigation**:

#### A. Calculs FFmpeg (streaming.ts) ✅ CORRECTS
**Logs Debug** (dernière exécution):
```
customPosition: { x: 18.24%, y: 49.64% }
portraitWidth: 422px
portraitHeight: 750px

Calculs:
- Centre X = 18.24% * 1920 = 350px ✅
- Centre Y = 49.64% * 1080 = 536px ✅
- Coin sup gauche X = 350 - (422/2) = 139px ✅
- Coin sup gauche Y = 536 - (750/2) = 161px ✅

Position FFmpeg finale: 139:161 ✅
```

**Les calculs sont PARFAITS!** Le problème n'est PAS dans streaming.ts.

#### B. Affichage Preview (Preview.tsx) ⚠️ À INVESTIGUER

**Code actuel**:
```typescript
// Position custom
const getCustomPositionStyle = (customPosition) => ({
  left: `${customPosition.x}%`,      // 18.24%
  top: `${customPosition.y}%`,       // 49.64%
  transform: 'translate(-50%, -50%)' // Centre sur ce point
})

// Taille téléphone
const getPhoneSizeStyle = (size) => ({
  width: '22%',           // 422px sur 1920px
  aspectRatio: '9/16'     // Portrait
})
```

**Théorie**:
- `left: 18.24%` + `translate(-50%)` = coin sup gauche à `18.24% - 11%` = `7.24%`
- En pixels: `7.24% * 1920 = 139px` ✅

**Si calculs sont identiques, pourquoi décalage?**

**Hypothèses**:
1. **Canvas preview n'est pas 1920x1080**: Si preview est redimensionné, les % ne correspondent pas aux mêmes pixels
2. **AspectRatio CSS vs réalité**: `aspectRatio: '9/16'` peut être interprété différemment selon le navigateur
3. **Transform origin**: `translate(-50%, -50%)` suppose que l'origin est `top left` (défaut), mais peut être modifié ailleurs

**TODO Prochaine Session**:
- Vérifier dimensions exactes du canvas preview (devrait être 1920x1080 ou ratio 16:9)
- Ajouter logs dans Preview.tsx pour vérifier dimensions réelles téléphone après render
- Tester avec position prédéfinie (ex: `bottom-right`) pour voir si décalage persiste

---

### 3. Webcam Preview Zoomée vs Stream Angle Large

**Symptôme**: Webcam principale (Krom Kam) montre zoom dans preview, angle large dans stream

**Cause Probable**:
- **Preview**: `getUserMedia` capture avec contraintes résolution (peut cropper)
- **Stream**: `dshow` via FFmpeg capture résolution native sans crop

**Investigation Nécessaire**:
- Vérifier contraintes `getUserMedia` dans Preview.tsx useEffect
- Comparer avec ce que FFmpeg capture (résolution native webcam)

**TODO Prochaine Session**:
- Lire useEffect webcam dans Preview.tsx
- Ajouter logs pour voir résolution capturée par getUserMedia
- Aligner contraintes getUserMedia avec résolution FFmpeg (ou vice-versa)

---

### 4. UX Demandé: Menu Dropdown Positions Téléphone

**Demande Utilisateur**:
> "Si je veux ancrer la position du téléphone de manière fixe, il me faudrait les neuf positions avec gauche, droite, haut, bas aussi. Mais ça veut dire que lorsque je clique sur l'option du téléphone, que le choix des positions soit dans un menu drop-down pour prendre moins de place."

**Positions à implémenter** (9 total):
```
top-left      top-center      top-right
center-left   center          center-right
bottom-left   bottom-center   bottom-right
+ custom (déjà existant)
```

**TODO Prochaine Session**:
- Ajouter positions manquantes à type `OverlayPosition`
- Implémenter calculs dans `getOverlayPosition` (streaming.ts)
- Implémenter calculs dans `getPositionClasses` (Preview.tsx)
- UI: Transformer boutons positions en dropdown Select (SourcesPanel)

---

## 📊 Métriques Session

### Performance
- **Fluidité**: 80-85% → 95%+
- **Frame drops**: Réduits de ~50%
- **Buffer usage**: 70-103% → 70-95% (plus stable)
- **FPS stream**: 31 stable (target 30)
- **Speed**: 1.03-1.06x (bon signe)

### Fonctionnalités
- **Multi-webcam**: ✅ Implémenté et fonctionnel
- **Background**: ✅ Implémenté (image/vidéo)
- **Persistence**: ❌ Cassée (à debugger)
- **Position téléphone**: ⚠️ Calculs corrects mais décalage visuel

---

## 🔧 Fichiers Modifiés

### Main Process
- `src/main/index.ts` (+50 lignes)
  - Protocol handler `hikari://`
  - Range requests (HTTP 206)
  - Import `net`, `readFile`, `extname`

- `src/main/services/streaming.ts` (+120 lignes, -70 lignes)
  - Multi-webcam: `webcams[]` array, forEach loops
  - Background: color/image/video support
  - Optimisations: buffer 250M, NVENC params
  - Logs debug: phone positioning

### Renderer
- `src/renderer/src/components/ControlPanel.tsx` (+15 lignes)
  - Multi-webcam: passe array au lieu d'une seule
  - Background: ajouté au streamConfig

- `src/renderer/src/components/Preview.tsx` (+60 lignes, -20 lignes)
  - Multi-webcam: Maps, useEffect refactor, IIFE
  - Background: rendering color/image/video
  - Helper `toHikariUrl` pour paths Windows

- `src/renderer/src/stores/appStore.ts` (+10 lignes)
  - Persistence: background ajouté au merge
  - Logs debug: webcams validation, background

- `src/renderer/index.html` (+2 lignes)
  - CSP: `hikari:` protocol autorisé

---

## 🎯 Plan Prochaine Session

### Priorité 1: Persistence (Critique) 🚨
1. Relancer app, vérifier logs console `[AppStore]`
2. Si validation filtre: assouplir critères `validWebcams`
3. Si localStorage vide: debug Zustand persist
4. Test: Ajouter webcam + background, relancer app, vérifier présence

### Priorité 2: Position Téléphone
1. Vérifier dimensions canvas preview (F12 → Elements)
2. Comparer avec résolution stream (1920x1080)
3. Si différent: ajuster scale ou calculs Preview.tsx
4. Test avec position prédéfinie (bottom-right) pour isoler problème

### Priorité 3: Webcam Zoom Preview
1. Lire contraintes `getUserMedia` dans Preview.tsx
2. Comparer résolution capturée vs résolution FFmpeg
3. Aligner les deux pour cohérence

### Priorité 4: Menu Dropdown Positions
1. Ajouter 5 positions manquantes (top-center, center-left, etc.)
2. Implémenter calculs côté stream + preview
3. UI: Dropdown au lieu de boutons (gain espace)

---

## 💡 Leçons Apprises

### Technique
1. **Protocol handlers Electron**: `net.fetch` ne supporte pas `file://`, utiliser `readFile` + `new Response`
2. **Range requests essentiels pour vidéo**: Sans HTTP 206, `<video>` ne peut pas seek
3. **Multi-webcam scalable**: Maps > refs individuelles pour nombre illimité de webcams
4. **IIFE pour async dans useEffect**: Évite race conditions avec setTimeout
5. **Persistence Zustand**: `partialize` + `merge` doivent être alignés, validation peut tout casser

### Philosophie Shinkofa
1. **Ne jamais se contenter de "ça va aller"**: Investigation jusqu'au bout, pas de compromis
2. **Prendre soin de son énergie**: Pause et retour frais > forcer quand fatigué
3. **Documentation exhaustive**: Permet de reprendre exactement où on était

---

## 📝 Notes Techniques

### Debugging Tips
- **Protocol handler**: Ajouter `console.log('[Protocol] Loading file:', filePath)` pour voir chemins
- **Persistence**: Logs dans `merge` pour voir ce qui est restauré
- **Position**: Logs détaillés avec calculs intermédiaires pour tracer erreurs

### Windows Paths Gotchas
```typescript
// ERREUR: hikari://D:\path\to\file (backslashes invalides dans URL)
// CORRECT: hikari://D%3A%2Fpath%2Fto%2Ffile (encodé)

// Conversion:
const normalized = filePath.replace(/\\/g, '/')  // D:/path/to/file
const encoded = encodeURIComponent(normalized)   // D%3A%2F...
```

### FFmpeg Multi-Webcam Pattern
```bash
# Input 0: background
# Input 1: webcam 1
# Input 2: webcam 2
# Input 3: phone
# Input 4-5: audio

filter_complex:
[0:v]scale=1920:1080[base];
[1:v]scale=768:432[webcam0_scaled];
[base][webcam0_scaled]overlay=W-w-20:20[with_webcam0];
[2:v]scale=576:324[webcam1_scaled];
[with_webcam0][webcam1_scaled]overlay=W-w-20:H-h-20[with_webcam1];
[3:v]scale=422:-1[phone_scaled];
[with_webcam1][phone_scaled]overlay=139:161[with_phone];
```

**Clé**: Chaînage des overlays, labels uniques pour chaque étape.

---

**Fin de session** - 2026-02-09 08:30
**Reprise prévue**: Après pause, investigation persistence + position téléphone
**Commit**: `3b15def`

---

*Michi no Kata - La Voie de l'Excellence*
