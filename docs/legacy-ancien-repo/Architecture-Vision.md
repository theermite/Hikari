# Architecture & Vision — Hikari Stream (光)

**Version** : 1.0.0
**Date** : 2026-02-27
**Statut** : Document vivant — mettre à jour à chaque décision architecturale majeure

> Ce document est la source de vérité pour toutes les décisions d'architecture, UX et vision produit.
> Avant toute implémentation : consulter ce document. Avant toute modification structurelle : mettre ce document à jour.

---

## 1. Vision Produit

### 1.1 Positionnement

**Hikari Stream** (光 = Lumière) est le remplacement OBS pour l'écosystème Shinkofa.

> "Quand tu appuies sur un interrupteur, la lumière s'allume. Tu ne penses pas à l'électricité."
> C'est le niveau d'invisibilité que Hikari Stream doit atteindre pour le streamer.

**Mission** : Permettre à n'importe qui — neurodivergent, débutant, solo streamer — de lancer un stream professionnel en moins d'une minute, sans charge cognitive excessive.

### 1.2 Position dans le pipeline Shinkofa

```
Hikari Stream (capture live)
    → Sakusei (post-production)
    → Publication multi-plateforme
```

Hikari Stream est le **point d'entrée** du pipeline contenu. Sa qualité technique impacte tout ce qui suit.

### 1.3 Public cible

- Streamers solo (gaming, IRL, podcast, coaching)
- Neurodivergents (TDAH, HPI) : interface claire, charge cognitive minimale
- Utilisateurs multi-dispositifs : PC + téléphone/tablette

---

## 2. Philosophie UX — Décision Fondamentale

### 2.1 Le principe Desktop / Deck

**Découverte critique (session 2026-02-27)** : La présence du Stream Deck (companion PWA sur téléphone/tablette) change l'architecture UX de façon fondamentale.

```
┌─────────────────────────────────────┐     ┌─────────────────┐
│          DESKTOP (PC)               │     │   DECK (Phone)  │
│                                     │     │                 │
│  AVANT le stream :                  │     │  PENDANT le     │
│  → Configuration sources            │     │  stream :       │
│  → Setup scènes, overlays           │     │  → Switch scène │
│  → Réglages audio                   │     │  → Mute/unmute  │
│  → Connexion Twitch/YouTube         │     │  → Markers      │
│                                     │     │  → Stats live   │
│  PENDANT le stream :                │     │  → Overlay on/off│
│  → Preview (ce que les viewers voient)│   │  → Go Live      │
│  → Accès rapide si besoin           │     │  → Stop stream  │
│                                     │     │                 │
│  APRÈS le stream :                  │     │                 │
│  → Export vers Sakusei              │     │                 │
│  → Review markers                   │     │                 │
└─────────────────────────────────────┘     └─────────────────┘
```

**Principe** : Le desktop n'a PAS besoin d'être une "surface de contrôle" pendant le stream.
Le Deck est là pour ça. Le desktop libère donc son espace pour la visibilité du contenu.

### 2.2 Implications architecturales

1. **Les panels "live" (chat, stream info)** doivent être facilement détachables sur un second moniteur
2. **L'audio et les scènes** n'ont PAS besoin d'être visibles simultanément pendant le stream — le Deck s'en charge
3. **ControlPanel tabs** est un anti-pattern : on ne peut pas voir scènes ET audio en même temps, mais le Deck compense
4. **La disposition par défaut** doit maximiser la surface Preview

### 2.3 Priorité des panels détachables (★ prioritaires)

| Panel | Détachable | Raison |
|-------|-----------|--------|
| Chat | ★ OUI | Second moniteur pendant le stream |
| Stream Info | ★ OUI | Stats temps réel sur second moniteur |
| Deck Panel | ★ OUI | Vue deck intégrée (alternative PWA) |
| Scenes | Non | Deck gère le switching en live |
| Sources | Non | Configuration pre-stream uniquement |
| Audio | Non | Deck gère le mute/volume en live |
| Settings | Non (modal) | — |

---

## 3. Layout OBS par défaut

### 3.1 Disposition cible

```
┌──────────────────────────────────────────────────────────────┐
│  TitleBar frameless — Hikari Stream (光)                      │
├────────────┬──────────────────────────────┬──────────────────┤
│            │                              │                  │
│  SCÈNES    │      PREVIEW                 │  STREAM INFO     │
│            │   (zone principale)          │  bitrate, viewers│
│  F1 F2 F3  │                              │  qualité, durée  │
│  F4 + ...  │                              │  [DÉTACHABLE ★]  │
│  [dock-    │                              ├──────────────────┤
│   left]    │                              │                  │
│            │                              │  CHAT            │
│  SOURCES   │                              │  Twitch+YouTube  │
│            │                              │  [DÉTACHABLE ★]  │
├────────────┴──────────────────────────────┴──────────────────┤
│  ⚡ ACTION BAR : [● GO LIVE] [⏺ REC] [◆ MARKER] [PRESET ▼]  │
└──────────────────────────────────────────────────────────────┘
```

**Zones dock** :
- `dock-left` : Scenes + Sources (panels verticaux)
- `dock-right` : Stream Info + Chat (panels verticaux, détachables)
- **Pas de `dock-bottom`** (voir section 4.2)

### 3.2 Action Bar (ex-ControlPanel)

L'Action Bar est le seul élément **non-dockable** — toujours visible.
Elle contient uniquement les actions critiques : Go Live, Rec, Markers, Preset.

**Hauteur cible** : 40-50px (actuellement 140px — réduction de 65%)

---

## 4. Problèmes Architecturaux Identifiés

### 4.1 ControlPanel — Défaut UX Fondamental

**Fichier** : `src/renderer/src/components/ControlPanel.tsx` (~750 LOC)

**Problème** : Interface à onglets (Scènes / Sources / Overlays / Audio / Markers / Monitor)

| Symptôme | Impact |
|---------|--------|
| Un seul onglet visible à la fois | Impossible de voir audio ET scènes simultanément |
| Occupe 140px en bas de l'écran | 15-20% de la hauteur totale sur 1080p |
| Mélange business logic + UI | Refactoring dangereux sans tests |
| Redondant avec le panel system | Les mêmes panels existent dans `components/panels/` |

**Validé par Jay (2026-02-27)** : *"OUI, absolument. Je valide qu'il y a un défaut fondamental de l'UX."*

**Solution décidée** :
- Extraire la business logic vers `useStreamController` hook
- Le ControlPanel devient une slim Action Bar (~40-50px)
- Les panels (Scènes, Sources, Audio) migrent dans le dock system

### 4.2 dock-bottom Audio — Décision de suppression

**Problème** : `dock-bottom` avec AudioPanel créé dans la session 2026-02-27 est **redondant** avec l'onglet Audio de ControlPanel.

**Conséquence** : Audio mixer existe en 2 endroits → confusion, espace gaspillé, état désynchronisé possible.

**Décision** : Supprimer `dock-bottom` des `defaultDockZones` dans `panelStore.ts`.
- Audio sera géré dans l'Action Bar refactorisée
- L'accès rapide à l'audio sera sur le Deck

**Action requise (Sprint 0)** : Retirer `dock-bottom`, bumper persist key → `v4`.

### 4.3 God Objects

| Fichier | LOC | Problème | Sprint |
|---------|-----|---------|--------|
| `appStore.ts` | ~1777 | 6 domaines mélangés | Sprint 4 |
| `Preview.tsx` | ~1543 | drag + overlay + webcam + phone | Sprint 4 |
| `main/index.ts` | ~978 | 75+ IPC handlers | Sprint 4 |
| `ControlPanel.tsx` | ~750 | business logic + UI tabs | Sprint 1-3 |

### 4.4 AudioPanel — Layout wrong pour dock horizontal

**Problème** : `AudioPanel.tsx` rend des cards verticales (`p-3 space-y-4`), inadaptées à un dock horizontal.

**Pour un dock horizontal OBS-style**, l'audio doit être des colonnes de faders :
```
│ 🎤 Micro │ 🖥️ PC │ 📱 Phone │ 🎵 Musique │
│ ─────── │ ──── │ ──────── │ ───────── │
│   VU    │  VU  │    VU    │    VU     │
│ 🔊 Vol  │ Vol  │   Vol    │   Vol     │
│ [Mute]  │[Mute]│  [Mute]  │  [Mute]   │
```

**Sprint 2** : Refactorer AudioPanel pour layout compact horizontal (colonnes de faders, VU meters verticaux, `~80-100px` de hauteur).

---

## 5. Décisions Techniques Prises

### 5.1 Panel System

| Décision | Valeur | Raison |
|----------|--------|--------|
| `audio.detachable` | `false` | Éviter duplication accidentelle |
| `persist key` | `v3` actuel → `v4` Sprint 0 | Reset localStorage après changement defaultZones |
| `dock-bottom` defaults | Suppression Sprint 0 | Redondant avec ControlPanel |
| Panels détachables | Chat, StreamInfo, DeckPanel | Companion second moniteur |

### 5.2 Comportement ControlPanel

| Décision | Valeur |
|----------|--------|
| ControlPanel reste | OUI — contient Go Live, Rec (non-dockable) |
| ControlPanel tabs | SUPPRIMÉS Sprint 3 |
| Business logic | Extraite vers `useStreamController` Sprint 1 |
| Hauteur cible finale | ~40-50px (Action Bar) |

### 5.3 Stream Deck companion

| Décision | Valeur |
|----------|--------|
| Rôle | Compagnon PRINCIPAL pendant le stream |
| Overlay toggle | Doit être implémenté (bloquant Sprint 3 audit) |
| Audio controls | Sprint 4 — mute/volume depuis Deck |
| Stats temps réel | Sprint 4 — bitrate, viewers, FPS sur Deck |

---

## 6. Architecture Technique Stable (Ne Pas Toucher)

Ces services sont **de qualité professionnelle** et ne doivent pas être refactorisés sans raison critique :

| Composant | Qualité | Pourquoi stable |
|-----------|---------|-----------------|
| `streaming.ts` | ✅ Pro | NVENC B-frames, circuit breaker, reconnect auto |
| `twitchService.ts` | ✅ Pro | OAuth complet, refresh tokens, safeStorage |
| `twitchEventSub.ts` | ✅ Pro | EventSub WebSocket, alerts temps réel |
| `youtubeService.ts` | ✅ Pro | OAuth complet, broadcast management |
| `adaptiveStreaming.ts` | ✅ Pro | QoS scoring 0-100, adaptive bitrate |
| `deckRelay.ts` | ✅ Pro | Heartbeat, orphan recovery, state cache |
| `SecureStore<T>` | ✅ Excellent | Pattern générique, chiffrement sélectif |

---

## 7. Règles Non-Négociables

### Pour toute modification UX
1. **Lire ce document avant de coder**
2. **Respecter la philosophie Desktop/Deck** : ne pas surcharger le desktop avec des contrôles live
3. **Maximiser la surface Preview** : c'est ce que les viewers voient
4. **Charge cognitive minimale** : public neurodivergent

### Pour toute modification de store
1. **Lire `panelStore.ts` ET `appStore.ts`** avant modification
2. **Bumper le `persist key`** si `defaultDockZones` ou `defaultPanelConfigs` changent
3. **Ne jamais créer de panel redondant** sans vérifier ControlPanel.tsx d'abord

### Pour tout nouveau panel
1. Vérifier : **existe-t-il dans ControlPanel.tsx comme onglet ?**
2. Si oui → le panel dock doit **remplacer** l'onglet, pas s'y ajouter
3. Vérifier `detachable` : Chat et StreamInfo doivent rester détachables

---

## 8. Références

| Document | Contenu |
|----------|---------|
| `CLAUDE.md` | Stack technique, structure fichiers, commandes |
| `docs/CDC-Hikari-Stream.md` | Cahier des charges complet (phases 1-5) |
| `docs/Audit-Complet-2026-02-26.md` | Audit factuel complet (scores, problèmes) |
| `docs/Sprint-Plan.md` | Plan sprints actuel (source de vérité planning) |
| `docs/Session-Plan-2026-02-27.md` | Plan session 2026-02-27 (historique) |

---

**Auteur** : Takumi (Claude Sonnet 4.6) — session 2026-02-27
**Validé par** : Jay (décisions UX + Stream Deck philosophy)
