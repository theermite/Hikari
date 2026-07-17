# Spike B0.0 — moteur libobs depuis Rust, en processus séparé

> **Code jetable.** Régime spike (§9bis du PET) : pas de TDG, pas de couverture ; en
> échange, des **critères chiffrés écrits avant** (voir `docs/PET.md` §7, fiche B0.0) et
> des **mesures conservées**. Ce code n'est **jamais** promu en production — s'il est bon,
> il est réécrit sous régime normal. Branche `spike/b0.0-libobs`, jamais fusionnée.

## La question, et une seule

La diffusion en direct tient-elle, depuis Rust, avec le moteur d'OBS dans un **processus
séparé** — et **combien coûte-t-on de plus qu'OBS nu** ?

La faisabilité est déjà prouvée (`league_record`, Rust + Tauri + moteur d'OBS, livré
depuis mars 2022). Le seul inconnu : personne n'a croisé **Rust + moteur d'OBS +
diffusion en direct**. Ce spike **mesure**, il ne décide plus (PET v1.4.0, ADR-013/014).

## Architecture (copiée, pas redécouverte — ADR-013)

```
[ hikari-controller ] --lance/observe--> [ hikari-engine : libobs dans SON processus ]
```

Deux binaires dans un workspace. Le contrôleur lance le moteur par son chemin. **Rust
stable**, jamais nightly : on n'utilise pas les *binary-artifact dependencies* (`-Z
bindeps`) de league_record, on lance le moteur comme un exécutable voisin.

## Ordre de preuve (du moins cher au plus cher)

1. **Étape 1 — la chaîne de build** *(le code actuel)* : le moteur **enregistre** 5 s
   (`record.mp4`). C'est le « hello world » de libobs-rs. Si `cargo-obs-build` ou
   l'édition de liens casse, on le voit ici, vite et pour pas cher.
2. **Étape 2 — la diffusion** : remplacer la sortie fichier par une sortie **RTMP** =
   l'épreuve (a). `libobs-simple` ne fait que l'enregistrement → passage à l'API bas
   niveau (`output` + service RTMP) de `libobs-wrapper`.

## Prérequis (vérifiés le 2026-07-17)

| Élément | Requis | État |
|---|---|---|
| Rust stable (msvc) | 1.97.1 | ✅ |
| OBS Studio (mesure de référence) | 32.x | ✅ 32.1.2 |
| Carte | RTX 3060 (⚠️ NVIDIA seulement) | ✅ |
| `libobs-wrapper` | 9.0.4+32.0.2 | ✅ crates.io |
| `libobs-simple` | 8.0.1 | ✅ crates.io |
| `cargo-obs-build` | 2.0.3 | à installer |

`[VEILLE] libobs-wrapper@9.0.4+32.0.2 vérifié 2026-07-17 via crates.io`

## Construire et lancer

```sh
# Une fois : l'outil qui pose les binaires OBS signés dans target/
cargo install cargo-obs-build

# Poser libobs dans le dossier de build (version dérivée du crate = OBS 32.0.2)
cargo obs-build build --out-dir target/debug

cargo build
cargo run --bin hikari-controller -- 5   # le contrôleur lance le moteur 5 s
```

## Les 5 épreuves et leurs seuils (source : `docs/PET.md` §7)

| # | Épreuve | Seuil de réussite |
|---|---|---|
| a | **Diffuser** en direct ⭐ | flux arrive · codec matériel confirmé · 0 image perdue |
| b | **Le processus séparé tient** ⭐ | moteur tué → l'app survit, détecte, relance, le dit |
| c | **Surcoût vs OBS nu** ⭐⭐ | **< 20 %** de CPU à travail égal (LE chiffre du spike) |
| d | Double encodage en jouant | 0 image perdue ET chute du jeu < 10 % |
| e | Installation | 2 tailles relevées + somme de contrôle oui/non |

## Mesures

Tout relevé brut va dans `mesures/` (suivi par git). Les captures vidéo lourdes y sont
ignorées (`.gitignore`). Le **verdict** s'écrit dans `docs/PET.md`, fiche B0.0.

## Durée bornée

**1 jour ouvré.** Au-delà → arrêt + escalade à Jay. Un spike qui déborde EST un résultat.
