---
title: Hikari Stream — Cadrage de vision
created: 2026-07-11
updated: 2026-07-11
status: draft
type: vision
---

# Hikari Stream — Cadrage de vision

> Issu du brainstorm Jay ↔ Takumi du 2026-07-11. Base du futur `/concevoir` (POUR QUOI).

## Étoile polaire

> **Hikari Stream : streamer l'esprit tranquille.**
> Config simple, fiabilité totale, expérience live hors du commun — la complexité pro
> cachée sous une interface limpide.

## Les 3 piliers

| Pilier | La promesse |
|---|---|
| **Simplicité** | Tu configures une fois, sans jargon, sans peur de mal faire |
| **Sérénité** | Zéro angoisse au lancement — l'app prouve que tout marche avant le direct |
| **Singularité** | Une expérience live alignée à l'identité du créateur, pour lui et son audience |

## Les 3 points de vue à servir

| Point de vue | Ce que Hikari doit garantir |
|---|---|
| **Le créateur** | L'app *renvoie son âme* : alignée à son identité, sans lag, stable, fluide |
| **Son besoin de visibilité** | Structure, régularité, pipeline édition → publication → planning réseaux, sans friction |
| **Le viewer** | Reçoit du contenu de qualité, aligné à ce qu'il veut — respecté, jamais un produit |

## Carte du parcours (le squelette)

Du premier clic jusqu'au viewer. La ligne marque où les outils classiques s'arrêtent.

| # | Étape | Ce que Hikari garantit |
|---|---|---|
| 0 | **Socle** (une fois) | install + wizard + identité/marque + presets |
| 1 | **Pré-vol** (chaque live) | checks auto + test privé → feu vert, zéro peur |
| 2 | **Live** | scènes, sources, deck, automations, cam mobile, moteur fiable, vertical simultané |
| 3 | **Interaction** | chat, alertes, events — selon le degré voulu |
| — | ⬆️ *ici s'arrêtent OBS et l'ancien Hikari* | |
| 4 | **Édition** | clips, highlights, sous-titres, segments |
| 5 | **Publication** | pipeline → Kobo ou réseaux + planning + cohérence |
| 6 | **Viewer** | reçoit la qualité, alignée — le juge final |
| ↺ | **Boucle** | stats et monitoring nourrissent la régularité |

## Principes fondateurs

1. **Le parcours entier, jamais le fragment.** Un live/une vidéo n'est qu'un fragment
   du but. Hikari couvre création → édition → publication → viewer + boucle. C'est le
   vrai différenciateur (les autres restent fragmentés parce que c'est dur et rentable
   de l'être).
2. **La complexité assumée dans l'ombre.** Voie cardinale Shinkofa : l'utilisateur ne
   sait pas à quel point c'était dur. Ça marche, c'est simple pour lui. Code invisible,
   impact réel.
3. **L'app s'adapte à la machine.** La machine de l'utilisateur pose toujours la limite.
   Hikari détecte le matériel, propose le réglage sûr **par défaut**, garde l'utilisateur
   dans la zone sûre, et le laisse ajuster s'il veut. Adaptation morphique appliquée au
   matériel (écho du principe Shinkofa d'adaptation à l'humain).
4. **Renvoyer l'âme du créateur.** Identité = principalement **habillage visuel**
   cohérent (overlays, couleurs, typo, transitions, traitement cam, avatars optionnels).

## Décisions verrouillées (2026-07-11)

| Sujet | Décision | Pourquoi |
|---|---|---|
| **Moteur vidéo** | Embarquer le moteur d'OBS (`libobs`) dans l'app | Fiabilité éprouvée par des millions d'installs ; on ne réécrit pas OBS |
| **App unique** | Une seule app (pas OBS + Hikari côte à côte) | Zéro friction d'install pour l'utilisateur final |
| **Licence** | Open-source assumé (moteur OBS = GPL) | Jay distribue, peut-être gratuit ; GPL non bloquant |
| **Cadre applicatif** | Tauri 2.x (Rust) | Léger, robuste, convention écosystème ; suffisant |
| **Pont moteur** | `libobs-rs` (Rust) — **à dérisquer par spike** | Convention Tauri ; repli = `obs-studio-node` (Electron) si le spike casse |
| **Vertical simultané** | Canvas multiple OBS 30+ (type Aitum) | Éprouvé ; à valider sur RTX 3060 (double encodage) |
| **Voix** | Uniquement filtres micro / changeur de voix intégré | Pas d'autre levier pertinent |
| **Avatar** | Capacité désirée, **2 étapes**, format **VRM** (pas Live2D) | Live2D = licence payante au-delà d'un seuil de revenu, incompatible open-source |
| **Frontière Hikari ↔ Kobo** | Hikari **autonome** : édition + publication réseaux **natives** ; Kobo = **pont optionnel** | L'app est pour tous ; tous n'ont pas Kobo → Hikari doit être complet seul. Kobo = bascule vers le pipeline avancé pour ceux qui l'ont |

## Réutilisable depuis l'ancien repo (`shinkofa/Hikari-Stream`)

Se transfère (indépendant du moteur) : UX complète (scènes, sources, deck, GoLive,
wizard, presets, tests de validation), intégrations (Twitch + EventSub, YouTube,
scrcpy, deck mobile QR), templates de scènes, flux GoLive. **À remplacer** : le moteur
(Canvas + FFmpeg → `libobs`) et la couche Electron (→ Rust/Tauri).

## Questions ouvertes (pour le `/concevoir`)

1. ✅ **Frontière Hikari ↔ Kobo — TRANCHÉE (2026-07-11)** : Hikari est autonome
   (édition + publication réseaux natives) ; Kobo = pont optionnel. Sous-question à
   affiner au `/concevoir` : **niveau d'édition natif** (essentiel vs avancé) — Hikari
   fait l'essentiel, Kobo l'avancé, pour ne pas réabsorber tout Kobo.
2. **Spike `libobs-rs`** (1-2 j) : valider scène simple + encodage NVENC + pas de blocage
   async avant de bâtir. Go/no-go, sinon repli `obs-studio-node`.
3. **Double encodage RTX 3060** : horizontal + vertical simultanés — valider le
   comportement NVENC/x264 sur banc.
