# Spike B0.2 — Double encodage RTX 3060

**Régime SPIKE (§9bis du PET) — code jetable, jamais fusionné dans `main`.**
Voir `docs/PET.md` section "B0.2" pour les 3 épreuves, leurs seuils, et le fork
go/plafonner.

## Question unique

La RTX 3060 encaisse-t-elle l'horizontal 1080p **et** un 2ᵉ flux vertical simultané,
**pendant qu'un jeu tourne** ?

## Ce que ce spike NE mesure PAS

Le recadrage visuel "propre" en portrait (crop 9:16) — ici la sortie verticale est
juste une résolution forcée (`obs_encoder_set_scaled_size`), pas une composition
recadrée. Le cadrage esthétique est une question UX séparée, pour la vraie
implémentation B3 plus tard.

## Prérequis

1. **MediaMTX local actif** — réutilise celui du spike B0.0 :
   `spikes/b0.0-libobs/mediamtx/mediamtx.exe` (même config, chemin `/live/*` accepté).
2. **Un jeu réel qui tourne** (LoL ou Dofus) — jamais mesuré à vide.
3. **Un moyen d'observer les images/seconde du jeu** (overlay Steam, RTSS, ou l'IHM du
   jeu lui-même) — l'épreuve (c) compare ces images/seconde avec et sans le spike actif.

## Lancer le spike

```powershell
# 1. Démarrer MediaMTX (dans un terminal séparé — reste ouvert, trouve mediamtx.yml
#    automatiquement car il est à côté de l'exécutable)
cd spikes\b0.0-libobs\mediamtx
.\mediamtx.exe

# 2. Lancer ton jeu, noter ses images/seconde SANS le spike (référence)

# 3. Lancer le spike (dans ce dossier)
cd spikes\b0.2-double-encodage
cargo run --release
```

Le spike affiche toutes les 2 secondes les compteurs d'images perdues pour les deux
sorties (`horizontal` et `vertical`). Laisse tourner **10 minutes** pendant que tu joues.

## Les 3 épreuves à remplir dans `mesures/verdict.md`

| # | Épreuve | Ce que tu regardes |
|---|---|---|
| **a** | Les 2 sessions s'ouvrent | La console affiche `materiel=true` pour les deux sorties (jamais un repli logiciel muet) |
| **b** | Zéro image perdue | Après 10 min, `images_perdues=0` sur les deux sorties |
| **c** | Le jeu reste jouable | Images/seconde du jeu, avec vs sans le spike actif — chute **< 10 %** |

## Arrêter

`Ctrl+C` dans le terminal du spike. MediaMTX peut rester ouvert pour un autre essai.
