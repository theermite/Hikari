# Verdict — Spike B0.2

**Statut** : ✅ **GO — 2026-07-21**.

**Machine** : RTX 3060, Windows 11, AMD Ryzen 5 5600. **Jeu réel joué pendant la mesure**
(charge réelle, pas à vide). **Durée** : ~16,5 minutes (992 s), au-delà des 10 minutes visées.

## Épreuve (a) — les 2 sessions s'ouvrent

- Encodeur horizontal : **NVENC (OBS_NVENC_H264_TEX), matériel=true**.
- Encodeur vertical : **NVENC (OBS_NVENC_H264_TEX), matériel=true**, résolution forcée
  1080×1920 via `obs_encoder_set_scaled_size` (pas un recadrage 9:16 propre — mesure de
  capacité seulement, voir README).
- **Aucun repli logiciel silencieux sur aucune des deux sorties.** ✅

## Épreuve (b) — zéro image perdue

- Horizontal : **images_perdues = 0** / images_totales = 29 764 (à t=992,7 s).
- Vertical : **images_perdues = 0** / images_totales = 29 765 (à t=992,7 s).
- **0 image perdue sur toute la durée, les deux sorties.** ✅

## Épreuve (c) — le jeu reste jouable

- Mesure **qualitative** (pas de compteur images/seconde exact relevé — limite honnête
  de cette session) : retour direct de Jay après ~16,5 min de jeu réel avec le spike actif
  → **« rien remarqué, c'était fluide comme d'habitude »**.
- Aucune chute perçue. ✅ (sous réserve : pas de pourcentage chiffré — si un chiffre exact
  est nécessaire plus tard, réutiliser ce spike avec un overlay FPS actif.)

## Verdict (go / plafonner)

**GO sans réserve** — décision Jay, 2026-07-21. (a) + (b) + (c) passent. **F-026 (vertical
simultané) confirmé.** La RTX 3060 encaisse l'horizontal 1080p + un 2ᵉ flux à résolution
forcée 1080×1920, en même temps, pendant un jeu réel, sans image perdue ni ralentissement
perçu.

**Reste hors scope de ce spike** (voir README) : le vrai recadrage portrait (crop 9:16
propre, question UX) — mesuré ici seulement la capacité GPU/CPU brute de 2 sessions NVENC
simultanées à des résolutions différentes.
