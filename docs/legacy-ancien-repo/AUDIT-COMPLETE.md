# Audit Complet - Hikari Stream

**Date** : 2026-02-08
**Application** : Hikari Stream
**Version Cible** : MVP Streaming (Feb 2, 2024 - Commit 67c0edb)
**Objectif** : Identifier écart entre code existant et UI visible

---

## 🎯 Résumé Exécutif

### Problème Principal

**Le système de panels OBS-like a été entièrement développé (+6,720 lignes) mais n'a JAMAIS été intégré dans App.tsx.**

### Impact

- 15 composants panels inaccessibles
- 640+ lignes de panelStore.ts non utilisées
- Fonctionnalités invisibles : dock zones, panels détachables, layouts sauvegardables
- UI bloquée sur structure ancienne (Sidebar/Preview/ControlPanel)

### Cause Racine

`src/renderer/src/App.tsx` utilise toujours l'ancienne structure :
```tsx
<div className="flex h-screen flex-col bg-hikari-950">
  <TitleBar />
  <div className="flex flex-1 overflow-hidden">
    <Sidebar />
    <main>
      <Preview />
      <StreamInfoPanel />
      <ControlPanel />
    </main>
  </div>
</div>
```

**Au lieu de :**
```tsx
<PanelContainer>
  {/* Tous les panels avec dock zones, drag & drop, detachment */}
</PanelContainer>
```

---

## 📊 Analyse Détaillée : Existant vs Utilisé

### 1. Système de Panels

| Composant | Fichier | Status | Raison |
|-----------|---------|--------|--------|
| **PanelContainer** | `components/panels/PanelContainer.tsx` | ❌ NON UTILISÉ | Jamais importé dans App.tsx |
| **DockZone** | `components/panels/DockZone.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |
| **DetachedWindow** | `components/panels/DetachedWindow.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |
| **LayoutManager** | `components/panels/LayoutManager.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |
| **Panel** | `components/panels/Panel.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |
| **PanelHeader** | `components/panels/PanelHeader.tsx` | ❌ NON UTILISÉ | Dépend de Panel |
| **PanelResizeHandle** | `components/panels/PanelResizeHandle.tsx` | ❌ NON UTILISÉ | Dépend de Panel |
| **LayoutModeSelector** | `components/panels/LayoutModeSelector.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |
| **MiniToolbar** | `components/panels/MiniToolbar.tsx` | ❌ NON UTILISÉ | Dépend de PanelContainer |

### 2. Panels de Contenu

| Panel | Fichier | Status | Raison |
|-------|---------|--------|--------|
| **ScenesPanel** | `components/panels/content/ScenesPanel.tsx` | ❌ NON UTILISÉ | Contenu = Sidebar actuel |
| **SourcesPanel** | `components/panels/content/SourcesPanel.tsx` | ❌ NON UTILISÉ | Panel séparé sources |
| **AudioPanel** | `components/panels/content/AudioPanel.tsx` | ❌ NON UTILISÉ | Contenu = ControlPanel.Audio |
| **ChatPanel** | `components/panels/content/ChatPanel.tsx` | ❌ NON UTILISÉ | Chat Twitch/YouTube |
| **SettingsPanel** | `components/panels/content/SettingsPanel.tsx` | ❌ NON UTILISÉ | Settings modal alternatif |
| **StreamInfoPanelContent** | `components/panels/content/StreamInfoPanelContent.tsx` | ❌ NON UTILISÉ | Version panel du StreamInfoPanel |

### 3. Store & État

| Store | Fichier | Status | Utilisation |
|-------|---------|--------|-------------|
| **panelStore.ts** | `stores/panelStore.ts` | ⚠️ CRÉÉ MAIS NON UTILISÉ | 640+ lignes de logique panels |
| **appStore.ts** | `stores/appStore.ts` | ✅ UTILISÉ | 1200+ lignes, state principal |
| **uxStore.ts** | `stores/uxStore.ts` | ✅ UTILISÉ | ZenMode, theme, shortcuts |

---

## 🔍 Fonctionnalités Manquantes par Catégorie

### A. Interface Panels (Priorité CRITIQUE)

| Feature | Existant | Visible UI | Gap |
|---------|----------|------------|-----|
| Dock zones gauche/droite | ✅ Oui (panelStore) | ❌ Non | App.tsx ne les affiche pas |
| Panels collapsables | ✅ Oui (Panel.tsx) | ❌ Non | Structure ancienne |
| Panels détachables | ✅ Oui (DetachedWindow) | ❌ Non | Fonction jamais appelée |
| Drag & Drop panels | ✅ Oui (dragState) | ❌ Non | Logique existe, UI manque |
| Layout save/load | ✅ Oui (savedLayouts) | ❌ Non | LayoutManager pas affiché |
| 3 modes layout | ✅ Oui (compact/standard/extended) | ❌ Non | LayoutModeSelector absent |
| Panel resizing | ✅ Oui (PanelResizeHandle) | ❌ Non | Ancienne logique resize utilisée |

**Impact** : ~6,720 lignes de code inaccessibles.

### B. Fonctionnalités Streaming (Priorité HAUTE)

| Feature | État Technique | État UI | Notes |
|---------|----------------|---------|-------|
| **Multi-sources** | ✅ Implémenté (Feb 1) | ⚠️ Partiel | Sidebar affiche sources mais UI limitée |
| **Multi-webcam** | ✅ Backend ready | ❌ Manque UI | Besoin d'ajouter device selector |
| **Multi-phone** | ✅ scrcpy multi-device | ❌ Manque UI | Besoin d'afficher plusieurs instances |
| **Markers** | ✅ Implémenté (Feb 1) | ⚠️ À vérifier | Vérifier présence dans ControlPanel |
| **Overlays vidéo** | ✅ Logique existe | ❌ Non fonctionnel | Jay signale que ça ne fonctionne pas |
| **Transitions** | ✅ Code présent | ⚠️ UI confuse | Trop d'options "slide" selon Jay |

### C. Status Bar (Priorité HAUTE)

| Élément | État |
|---------|------|
| **Bottom status bar** | ❌ DISPARU |
| Viewers count | ❌ Absent |
| Bitrate | ❌ Absent |
| Live indicator | ❌ Absent |
| Connection status | ❌ Absent |

**Notes** : Jay mentionne explicitement "je ne vois plus la bottom bar".

### D. Settings & Configuration (Priorité MOYENNE)

| Feature | État Actuel | État Attendu |
|---------|-------------|--------------|
| **Modal Settings** | ✅ Existe | ⚠️ Non groupé | Jay demande modal groupé avec tabs |
| Organisation par catégories | ❌ Manque | ✅ Requis | Stream / Audio / Video / Avancé |
| Tabs navigation | ❌ Manque | ✅ Requis | Meilleure UX |
| Paramètres scrcpy | ✅ Existe | ⚠️ Résolution incorrecte | Jay signale résolution trop faible |

### E. Deck Relay (Priorité MOYENNE)

| Feature | Implémentation | Intégration |
|---------|----------------|-------------|
| **WebSocket server** | ✅ Probablement (ports 9876/9877) | ❌ Non testé |
| **QR Code PWA** | ✅ Composant existe | ⚠️ Mal positionné | "Top right, à peine visible" |
| **UI Deck dans Hikari** | ❓ À vérifier | ❌ Pas d'indication visible |

### F. System Tray (Priorité BASSE)

| Feature | État |
|---------|------|
| **Tray icon** | ❓ Implémenté ? | Absence signalée par Jay |
| Minimize to tray | ❓ | Absence signalée par Jay |
| Quick actions | ❓ | Absence signalée par Jay |

### G. Twitch EventSub (Priorité BASSE)

| Feature | État |
|---------|------|
| **Twitch alerts** | ❓ Implémenté ? | Absence signalée par Jay |
| EventSub listener | ❓ | À vérifier dans main process |

---

## 🔎 Historique Git - Analyse des Commits

### Phase 1 : MVP Initial (Jan 31, 2024)

**Commit** : Initial MVP (~4,500 lignes)
**Contenu** : Structure de base, Sidebar, Preview, ControlPanel
**État** : ✅ Fonctionnel mais basique

### Phase 2 : Markers & Multi-Source (Feb 1, 2024)

**Commit** : Markers + Multi-source support (+10,000 lignes)
**Contenu** :
- Système de markers temporels
- Support multi-sources
- Amélioration gestion sources

**État** : ⚠️ Partiellement visible (Sidebar affiche sources)

### Phase 3 : Panel System OBS-like (Feb 2, 2024)

**Commit** : 67c0edb (+6,720 lignes)
**Contenu** :
- 9 composants panels infrastructure
- 6 panels de contenu
- panelStore.ts complet
- Dock zones, detachment, layouts

**État** : ❌ **JAMAIS INTÉGRÉ DANS APP.TSX**

### Phase 4 : Quality Improvements (Feb 2, 2024)

**Commit** : Quality pass
**Contenu** :
- Performance optimizations
- Accessibility improvements
- UI polish

**État** : ⚠️ À vérifier présence dans codebase actuel

---

## 🚨 Problèmes Critiques Identifiés

### 1. Architecture Bloquante

**Problème** : App.tsx n'a jamais été mis à jour pour utiliser PanelContainer
**Impact** : Bloque accès à 15 composants + panelStore
**Priorité** : 🔴 CRITIQUE

### 2. Régression UI

**Problème** : Bottom status bar a disparu
**Impact** : Pas de feedback stream (viewers, bitrate, live status)
**Priorité** : 🔴 CRITIQUE

### 3. Settings Non Ergonomiques

**Problème** : Modal settings pas organisé en tabs
**Impact** : UX confuse, difficile de trouver paramètres
**Priorité** : 🟠 HAUTE

### 4. Overlays Non Fonctionnels

**Problème** : Overlays vidéo ne fonctionnent pas
**Impact** : Feature promise mais cassée
**Priorité** : 🟠 HAUTE

### 5. UI Multi-Device Manquante

**Problème** : Backend supporte multi-webcam/phone mais UI manque
**Impact** : Feature invisible pour utilisateur
**Priorité** : 🟡 MOYENNE

### 6. Deck Relay Mal Intégré

**Problème** : QR code mal positionné, UI Deck incertaine
**Impact** : Feature inutilisable
**Priorité** : 🟡 MOYENNE

---

## 📋 Plan d'Action Structuré

### 🔴 Phase 1 : Restauration Fonctionnalités Critiques (1-2 jours)

#### Task 1.1 : Intégrer Panel System dans App.tsx

**Objectif** : Remplacer structure ancienne par PanelContainer
**Fichiers** :
- `src/renderer/src/App.tsx` (réécrire structure)
- `src/renderer/src/components/panels/PanelContainer.tsx` (importer)

**Actions** :
1. Supprimer ancienne structure (Sidebar, Preview directes)
2. Importer PanelContainer
3. Configurer dock zones (gauche: Scenes/Sources, droite: StreamInfo/Chat)
4. Tester collapsing, resizing, detachment
5. Vérifier persistance localStorage (panelStore)

**Validation** :
- [ ] Panels visibles et fonctionnels
- [ ] Dock zones left/right affichées
- [ ] Panels détachables
- [ ] Layouts sauvegardables
- [ ] Pas de régression sur fonctionnalités existantes

**Estimate** : 4-6 heures

#### Task 1.2 : Restaurer Bottom Status Bar

**Objectif** : Afficher infos stream en bas de l'app
**Fichier** : `src/renderer/src/components/StatusBar.tsx` (créer ou restaurer)

**Contenu requis** :
- Viewers count (avec icône 👁️)
- Bitrate actuel (Mbps)
- Live indicator (🔴 LIVE / ⚫ OFFLINE)
- Connection status (ping, qualité)
- Durée stream

**Validation** :
- [ ] Status bar visible en bas de l'app
- [ ] Données mises à jour en temps réel
- [ ] Design cohérent avec Hikari theme

**Estimate** : 2-3 heures

### 🟠 Phase 2 : Amélioration UX (2-3 jours)

#### Task 2.1 : Réorganiser Modal Settings avec Tabs

**Objectif** : Modal settings ergonomique avec navigation tabs
**Fichier** : `src/renderer/src/components/SettingsModal.tsx` (refactor)

**Tabs requis** :
1. **Stream** : Plateforme, clé stream, résolution output
2. **Audio** : Devices, niveaux, filters
3. **Vidéo** : Webcams, phones scrcpy, overlays
4. **Avancé** : Encoder, présets, chemins

**Validation** :
- [ ] 4 tabs clairement identifiés
- [ ] Navigation fluide entre tabs
- [ ] Paramètres groupés logiquement
- [ ] Pas de doublon avec panels

**Estimate** : 3-4 heures

#### Task 2.2 : Optimiser Résolution scrcpy

**Objectif** : Améliorer qualité preview phone
**Fichier** : Settings scrcpy ou appStore

**Actions** :
1. Identifier résolution actuelle
2. Augmenter à au moins 720p (1280x720)
3. Ajouter option "Qualité Preview" dans Settings > Vidéo
4. Tester performance

**Validation** :
- [ ] Preview phone nette et lisible
- [ ] Pas de lag sur capture
- [ ] Option configurable

**Estimate** : 1-2 heures

#### Task 2.3 : Simplifier Options Transitions

**Objectif** : Réduire confusion options "slide"
**Fichier** : Transitions UI (probablement dans ControlPanel ou Sidebar)

**Actions** :
1. Auditer options transitions actuelles
2. Consolider "slide left/right/up/down" en une option "Slide" avec direction picker
3. Garder : Fade, Cut, Slide (avec direction)
4. Retirer : Duplicatas et options redondantes

**Validation** :
- [ ] Maximum 5-6 options transitions
- [ ] Chaque option clairement distincte
- [ ] UI plus lisible

**Estimate** : 1-2 heures

### 🟡 Phase 3 : Fonctionnalités Multi-Device (2-3 jours)

#### Task 3.1 : UI Multi-Webcam

**Objectif** : Afficher et sélectionner plusieurs webcams
**Fichier** : Créer `components/MultiDeviceSelector.tsx` ou intégrer dans SourcesPanel

**Features** :
- Liste webcams détectées
- Preview thumbnail chaque webcam
- Bouton "Add to Scene" par webcam
- Gestion devices actifs

**Validation** :
- [ ] Liste webcams visible
- [ ] Thumbnails preview
- [ ] Ajout multiple sources fonctionne

**Estimate** : 3-4 heures

#### Task 3.2 : UI Multi-Phone scrcpy

**Objectif** : Afficher et gérer plusieurs phones Android
**Fichier** : Même composant ou séparé

**Features** :
- Détection devices ADB
- Preview chaque phone
- Start/stop capture par device
- Resolution par device

**Validation** :
- [ ] Plusieurs phones affichés simultanément
- [ ] Contrôle indépendant par device
- [ ] Performance stable

**Estimate** : 4-5 heures

### 🟢 Phase 4 : Deck Relay & Intégrations (1-2 jours)

#### Task 4.1 : Repositionner QR Code Deck

**Objectif** : QR code ergonomique et visible
**Fichier** : `components/DeckQRCode.tsx` + intégration

**Actions** :
1. Retirer du top-right
2. Option 1 : Ajouter dans SettingsPanel > tab "Deck"
3. Option 2 : Bouton "📱 Connect Deck" qui ouvre modal centré
4. Augmenter taille QR code (300x300)

**Validation** :
- [ ] QR code facilement accessible
- [ ] Taille lisible
- [ ] Instructions claires

**Estimate** : 1 heure

#### Task 4.2 : Vérifier WebSocket Server Deck

**Objectif** : Confirmer que serveur WS fonctionne
**Fichier** : Main process (probablement `src/main/`)

**Actions** :
1. Chercher code WS server dans main
2. Tester connexion manuelle (wscat ou navigateur)
3. Vérifier ports 9876/9877
4. Documenter API messages

**Validation** :
- [ ] Serveur démarre avec app
- [ ] Accepte connexions
- [ ] Messages scene changes fonctionnent

**Estimate** : 2-3 heures

#### Task 4.3 : Tester Deck PWA Externe

**Fichier** : `apps/hikari-deck/` (projet séparé selon git status)

**Actions** :
1. Vérifier si hikari-deck existe
2. Scanner QR code et tester connexion
3. Vérifier boutons scene changes
4. Fix issues de connexion si nécessaire

**Validation** :
- [ ] PWA se connecte via QR
- [ ] Boutons scenes fonctionnent
- [ ] Latence acceptable

**Estimate** : 2-3 heures

### 🔵 Phase 5 : Features Avancées (Si temps disponible)

#### Task 5.1 : System Tray

**Estimate** : 3-4 heures
**Priorité** : Basse

#### Task 5.2 : Twitch EventSub Alerts

**Estimate** : 4-6 heures
**Priorité** : Basse

#### Task 5.3 : Réparer Overlays Vidéo

**Estimate** : 2-3 heures
**Priorité** : Moyenne (si identifié rapidement)

---

## 🎯 Priorités Recommandées

### Ordre d'Exécution Optimal

1. **Task 1.1 - Panel System** : Débloque tout le reste ✅ CRITIQUE
2. **Task 1.2 - Status Bar** : Feedback stream indispensable ✅ CRITIQUE
3. **Task 2.1 - Settings Tabs** : UX blocking Jay ✅ HAUTE
4. **Task 2.2 - scrcpy Quality** : Amélioration rapide ✅ HAUTE
5. **Task 4.1 - QR Code** : Fix rapide et visible ✅ MOYENNE
6. **Task 3.1 - Multi-Webcam** : Feature promise ✅ MOYENNE
7. **Task 3.2 - Multi-Phone** : Feature promise ✅ MOYENNE
8. **Task 2.3 - Transitions** : Nettoyage UX ✅ BASSE
9. **Task 4.2/4.3 - Deck** : Fonctionnel mais pas critique ✅ BASSE

### Estimation Totale

| Phase | Durée | Priorité |
|-------|-------|----------|
| Phase 1 | 6-9 heures | CRITIQUE |
| Phase 2 | 5-8 heures | HAUTE |
| Phase 3 | 7-9 heures | MOYENNE |
| Phase 4 | 5-7 heures | BASSE |

**Total MVP Fonctionnel** : 23-33 heures (~3-4 jours de dev intensif)

---

## 🔎 Fichiers Clés à Modifier

### Priorité 1 (Phase 1)

```
src/renderer/src/App.tsx                              [CRITIQUE - Réécrire structure]
src/renderer/src/components/StatusBar.tsx             [CRÉER - Bottom status bar]
src/renderer/src/components/panels/PanelContainer.tsx [INTÉGRER - Déjà existe]
```

### Priorité 2 (Phase 2)

```
src/renderer/src/components/SettingsModal.tsx         [REFACTOR - Ajouter tabs]
src/renderer/src/stores/appStore.ts                   [MODIFIER - Settings scrcpy]
src/renderer/src/components/ControlPanel.tsx          [AUDIT - Transitions]
```

### Priorité 3 (Phase 3)

```
src/renderer/src/components/MultiDeviceSelector.tsx   [CRÉER - Webcams/Phones]
src/renderer/src/components/panels/content/SourcesPanel.tsx [INTÉGRER]
```

### Priorité 4 (Phase 4)

```
src/renderer/src/components/DeckQRCode.tsx            [MODIFIER - Repositionner]
src/main/index.ts                                     [AUDIT - WebSocket server]
```

---

## ✅ Checklist de Validation Post-Audit

### Fonctionnalités Visibles

- [ ] Panels OBS-like affichés et fonctionnels
- [ ] Dock zones gauche/droite
- [ ] Panels détachables (drag out)
- [ ] Layout modes (compact/standard/extended)
- [ ] Bottom status bar (viewers, bitrate, live)
- [ ] Settings organisés en tabs
- [ ] Multi-webcam UI
- [ ] Multi-phone UI
- [ ] QR code Deck bien positionné

### Fonctionnalités Techniques

- [ ] panelStore.ts effectivement utilisé
- [ ] Layouts sauvegardés en localStorage
- [ ] scrcpy résolution améliorée
- [ ] Transitions simplifiées
- [ ] WebSocket Deck fonctionnel
- [ ] Overlays vidéo réparés (si traité)

### Qualité Code

- [ ] Pas de composants dupliqués
- [ ] Imports propres (panels utilisés)
- [ ] Performance stable
- [ ] Pas de régression features existantes

---

## 📝 Notes Additionnelles

### Questions en Suspens

1. **System Tray** : Code existe-t-il déjà dans main process ?
2. **Twitch EventSub** : Implémentation présente ou à créer from scratch ?
3. **Overlays vidéo** : Quelle est la nature du bug ? Rendering ? Position ? Opacity ?
4. **Bottom Status Bar** : A-t-elle été supprimée ou jamais créée ?

### Décisions Architecture à Valider avec Jay

1. **PanelContainer** : Remplacer complètement ancienne structure ou migration progressive ?
2. **Settings** : Garder modal OU utiliser SettingsPanel dans dock zone ?
3. **Deck UI** : Modal QR code OU tab permanent dans Settings ?
4. **Multi-Device** : Composant unifié OU séparé webcam/phone ?

---

## 🚀 Prochaines Étapes Immédiates

### Actions Recommandées

1. **Valider ce plan d'action avec Jay**
   → Confirmer priorités
   → Ajuster estimations si nécessaire

2. **Commencer Phase 1, Task 1.1**
   → Intégrer PanelContainer dans App.tsx
   → Débloque 6,720 lignes de code

3. **Créer branches Git par phase**
   ```bash
   git checkout -b feat/phase-1-panel-system
   git checkout -b feat/phase-2-ux-improvements
   # etc.
   ```

4. **Tester après chaque task**
   → Éviter régressions
   → Valider features incrementally

---

**Auteur** : Takumi (Claude Sonnet 4.5)
**Review** : À valider par Jay
**Prochaine Action** : Attendre validation plan + commencer Phase 1
