# Plan Session — 2026-02-27
# Hikari Stream : Remontée qualité 52 → 90%+

> **STATUT SESSION** : Terminée — découvertes majeures qui ont révisé le plan
> **Référence plan révisé** : `docs/Sprint-Plan.md` (source de vérité going forward)

**Objectif session 1** : Intégration panel system + UX fondamentale
**Durée estimée** : 4-6h
**Décisions validées par Jay** :
- Layout par défaut : OBS Studio
- Panels détachables priorité : Chat, Deck, Stream Info

---

## Résultat Session (Résumé)

### Accompli
- Panel system intégré dans App.tsx ✅
- DockZone : fix flex-direction pour horizontal zones ✅
- PanelContainer : hasBottomPanels, bottomIsCollapsed, height animation ✅
- audio.detachable = false ✅
- persist key v3 ✅

### Découvertes critiques (changement de plan)
1. **dock-bottom Audio redondant** avec ControlPanel Audio tab → suppression Sprint 0
2. **ControlPanel défaut UX fondamental** : tabs cachent les panels → validé par Jay
3. **Philosophie Desktop/Deck** : le Deck est le compagnon live, le desktop = setup → change l'architecture UX complète
4. **AudioPanel layout wrong** pour dock horizontal → Sprint 2 nécessaire

### Plan révisé → voir `docs/Sprint-Plan.md`

---

## Contexte — Pourquoi cette session est critique

Le panel system (~2660 LOC) a été construit mais jamais intégré dans App.tsx.
L'app utilise depuis toujours une structure fixe incompatible avec la flexibilité voulue.
C'est la source principale de frustration UX identifiée.

---

## Layout OBS cible

```
┌─────────────────────────────────────────────────────────────┐
│  TitleBar (frameless — Hikari Stream)                       │
├──────────────────────────────┬──────────────────────────────┤
│                              │                              │
│        PREVIEW               │    STREAM INFO               │
│     (zone principale)        │    (bitrate, viewers,        │
│                              │     qualité, durée)          │
│                              │    [DÉTACHABLE ★]            │
│                              │                              │
│                              ├──────────────────────────────┤
│                              │                              │
│                              │    CHAT                      │
│                              │    (Twitch + YouTube)        │
│                              │    [DÉTACHABLE ★]            │
│                              │                              │
├──────────┬───────────────────┴──────────────────────────────┤
│  SCÈNES  │  SOURCES          │  AUDIO MIXER   │  DECK       │
│          │                   │                │  [DÉTACH. ★]│
│  F1 F2   │  Écran            │  🎤 Micro  ──  │            │
│  F3 F4   │  Webcam(s)        │  🖥️ PC     ──  │  Contrôles │
│  + ...   │  Téléphone        │  📱 Phone  ──  │  rapides   │
│          │  Overlays         │  🎵 Musique──  │            │
├──────────┴───────────────────┴────────────────┴────────────┤
│  ControlPanel : [⬤ GO LIVE] [⏺ REC] [Markers] [Preset]    │
└─────────────────────────────────────────────────────────────┘
```

**Panels détachables ★ en priorité** :
1. `ChatPanel` — second moniteur, toujours visible pendant le stream
2. `StreamInfoPanel` — stats temps réel sur second moniteur
3. `DeckPanel` — vue deck intégrée (alternative à la PWA)

---

## Bloc 1 — Panel System Integration (3-4h)

### Étape 1.1 — Audit PanelContainer (30 min)

Lire et comprendre exactement :
- `PanelContainer.tsx` : props attendues, configuration DockZone
- `panelStore.ts` : state structure, actions, persistence localStorage
- `DockZone.tsx` : comment les panels s'y attachent
- `Panel.tsx` : props (id, title, icon, resizable, detachable)
- `DetachedWindow.tsx` : comment le détachement fonctionne (BrowserWindow IPC ?)
- `LayoutModeSelector.tsx` : les 3 modes (compact / standard / extended)
- Panels contenu existants : ScenesPanel, SourcesPanel, AudioPanel, ChatPanel, MarkersPanel, StreamInfoPanelContent, SettingsPanel

**Objectif** : avoir une carte complète de ce que le système attend avant de toucher App.tsx

### Étape 1.2 — Configuration layout par défaut (30 min)

Définir dans `panelStore.ts` le layout OBS par défaut :

| Panel | Zone | Position | Détachable | Visible par défaut |
|-------|------|----------|------------|-------------------|
| Preview | Centre | main | Non | Oui |
| StreamInfoPanel | Droite haut | right-top | ✅ Oui (★) | Oui |
| ChatPanel | Droite bas | right-bottom | ✅ Oui (★) | Oui |
| ScenesPanel | Bas gauche | bottom-left | Non | Oui |
| SourcesPanel | Bas centre | bottom-center | Non | Oui |
| AudioPanel | Bas droite | bottom-right | Non | Oui |
| DeckPanel | Bas extrême droite | bottom-far-right | ✅ Oui (★) | Oui |
| MarkersPanel | Intégré ControlPanel | — | Non | Oui |
| SettingsPanel | Modal (inchangé) | — | Non | — |

### Étape 1.3 — Remplacement App.tsx (1-2h)

Remplacer la structure fixe actuelle :
```tsx
// AVANT (structure fixe)
<TitleBar />
<Sidebar />
<Preview />
<StreamInfoPanel />
<ControlPanel />
```

Par :
```tsx
// APRÈS (panel system)
<TitleBar />
<PanelContainer defaultLayout="obs-like">
  {/* Panels configurés via panelStore */}
</PanelContainer>
<ControlPanel /> {/* Bottom bar fixe — toujours visible */}
```

**Règle** : ControlPanel (Go Live, Rec, Markers) reste fixe en bas. C'est le seul élément non-dockable — on doit toujours y accéder.

### Étape 1.4 — Vérification sans régression (1h)

Checklist de validation obligatoire avant de continuer :

**Streaming** :
- [ ] Bouton Go Live fonctionne
- [ ] Status stream s'affiche (offline/connecting/live/error)
- [ ] Bitrate et FPS visibles dans StreamInfoPanel
- [ ] Reconnexion auto en cas de coupure

**Scènes** :
- [ ] Changer de scène fonctionne
- [ ] Templates de scène accessibles
- [ ] F1-F4 fonctionnent (si implémentés)
- [ ] Transitions appliquées

**Sources** :
- [ ] Screen capture fonctionne
- [ ] Webcam(s) détectées et affichées
- [ ] Phone/scrcpy fonctionne si connecté
- [ ] Overlays visibles et positionnables

**Audio** :
- [ ] VU meters actifs
- [ ] Mute/unmute par piste
- [ ] Volume ajustable

**Deck** :
- [ ] QR code accessible (dans DeckPanel ou Settings)
- [ ] Connexion relay fonctionne
- [ ] Scènes switchables depuis le Deck

**Panels** :
- [ ] Chaque panel redimensionnable
- [ ] Chat détachable sur second moniteur
- [ ] StreamInfo détachable
- [ ] Layout sauvegardé en localStorage (refresh = même layout)

---

## Bloc 2 — Overlay Toggle depuis le Deck (30-45 min)

Feature manquante Sprint 3. Implémentation dans :
- `deckPage.ts` : ajouter handler `action:overlay` → `appStore.toggleOverlay(overlayId)`
- `Deck PWA` (deck.shinkofa.com) : ajouter boutons overlays dans l'interface

---

## Bloc 3 — Raccourcis Clavier (30-45 min)

Implémenter et documenter :

| Raccourci | Action |
|-----------|--------|
| `F1` | Scène 1 |
| `F2` | Scène 2 |
| `F3` | Scène 3 |
| `F4` | Scène 4 |
| `Ctrl+G` | Go Live (toggle stream) |
| `Ctrl+R` | Toggle Recording |
| `M` | Mute/unmute micro |
| `Espace` | Marker "Epic" |
| `Ctrl+Espace` | Marker custom (prompt) |
| `Ctrl+,` | Ouvrir Settings |

Ajouter un modal "Raccourcis" accessible via `?` ou dans Settings.

---

## Bloc 4 — Flow Go Live simplifié (30 min)

Objectif : Preset → Live en < 1 minute

Vérifier et corriger le GoLiveModal :
- [ ] Sélection preset pré-remplit titre/catégorie/plateforme
- [ ] Confirmation en 1 clic si preset déjà configuré
- [ ] Pas de formulaire à remplir si preset chargé
- [ ] Indicateur "Prêt à streamer" visible

---

## Fichiers qui vont être modifiés (Session 1)

**Modifiés** :
- `src/renderer/src/App.tsx` — remplacement structure principale
- `src/renderer/src/stores/panelStore.ts` — layout par défaut OBS
- `src/main/services/deckPage.ts` — overlay toggle handler
- `src/renderer/src/components/GoLiveModal.tsx` — simplification flow

**Potentiellement créés** :
- `src/renderer/src/constants/defaultLayout.ts` — config layout OBS par défaut

**Non touchés cette session** :
- `appStore.ts` — refactoring en Session 2
- `Preview.tsx` — refactoring en Session 2
- Services main (streaming, ffmpeg, etc.) — stables

---

## Checkpoints de validation Session 1

### Checkpoint 1 — Après intégration panel system
L'app démarre avec la disposition OBS.
Tous les panels sont visibles.
Le stream fonctionne toujours.

### Checkpoint 2 — Après overlay toggle Deck
Depuis le téléphone, activer/désactiver un overlay fonctionne.

### Checkpoint 3 — Après raccourcis + Go Live
F1-F4 changent de scène.
Ctrl+G lance le stream.
GoLiveModal avec preset chargé = 2 clics maximum.

---

## Sessions suivantes (rappel)

| Session | Objectif | Score cible |
|---------|----------|-------------|
| **1 (demain)** | Panel system + UX | UX : 38 → 75 |
| **2** | Découpage stores + Preview | Architecture : 42 → 80 |
| **3** | Tests + ESLint durci | Qualité code : 22 → 85 |
| **4** | Sécurité + a11y + Phase 2 CDC (recording) | Sécurité : 58 → 85, a11y : 38 → 80 |
| **5** | Phase 3-4 CDC (export Sakusei, podcast) | Features CDC : 52 → 90 |

---

**Prêt à démarrer demain matin.**
**Commencer par Étape 1.1 (audit PanelContainer) sans toucher de code.**
