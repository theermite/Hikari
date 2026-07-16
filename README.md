# 光 Hikari

**Le cockpit de stream qui ne t'épuise pas.**
Du premier clic au clip publié — dans une seule application.

> ⚠️ **Ce projet n'est pas encore utilisable.** La conception est faite ; le développement n'a pas
> commencé. Il attend une preuve technique (voir *Où en est le projet*). Ce dépôt est ouvert dès le
> premier jour, par choix : le chemin fait partie du travail.

---

## Le problème

Streamer aujourd'hui, c'est empiler des outils. Un logiciel pour diffuser, un autre pour automatiser,
un troisième pour piloter, un quatrième pour les clips. Chacun avec sa logique, ses réglages, ses
pannes. Résultat : **des heures cumulées de configuration** avant même de dire bonjour à quelqu'un.

Le pire n'est pas le temps perdu. C'est ce qu'on abandonne. Un effet visuel qu'on voulait, un
enchaînement qu'on avait en tête — laissés tomber parce que les monter coûtait trop cher. **L'outil
finit par décider de ce que tu crées.**

## Le pari

Une seule application. Elle embarque le moteur de diffusion, le pilotage, les automatisations et
l'essentiel de l'édition. Pas parce que « tout-en-un » sonne bien — parce qu'un outil qui possède les
deux côtés peut rendre **un geste** ce qui en demandait vingt ailleurs.

| Principe | Ce que ça veut dire |
|---|---|
| **Le cas simple est trivial** | Un enchaînement de deux étapes ne demande pas de tutoriel |
| **Chercher, pas fouiller** | Tu décris ce que tu veux, en français. Pas de menu en cascade |
| **La machinerie est cachée, pas absente** | Réglages sains par défaut ; la profondeur reste accessible |
| **Rien ne fige ton direct** | Une automation qui boucle est refusée *avant* le live, jamais pendant |
| **Ton cerveau d'abord** | Charge mentale, contrôle sensoriel, prévisibilité — pour tous, pas une case à cocher |

**La mesure de réussite** : combien d'idées as-tu abandonnées parce que l'outil les rendait trop
chères ? La cible est zéro.

## Ce que ça fait (prévu)

Le parcours complet, d'un bout à l'autre :

| Étape | Contenu |
|---|---|
| **Socle** | Installation unique · accueil guidé · détection du matériel · kit de marque |
| **Pré-vol** | Vérifications automatiques · test privé · feu vert avant de diffuser |
| **Live** | Scènes · audio · deck de contrôle · **automations** · multi-plateforme · vertical simultané |
| **Interaction** | Chat multi-plateforme · modération · alertes · bandeaux |
| **Édition** | Marqueurs · clips · replay instantané · sous-titres · chapitres |
| **Publication** | Réseaux en natif · planification · miniatures à ta marque |
| **Suivi** | Statistiques · santé du stream · spectateurs en direct |

Transversal : adaptation morphique (densité, thème, contraste, police, langue), avatar VRM,
deck mobile local et distant, caméra virtuelle.

## Où en est le projet

| Étape | État |
|---|---|
| Vision + cadrage | ✅ fait |
| Cahier des charges (64 fonctions) | ✅ fait |
| Plan d'exécution (29 briques) | ✅ fait |
| Prototype cliquable | ✅ fait |
| Analyse de la concurrence | ✅ fait |
| **Spike moteur — go/no-go** | ⬜ **la prochaine étape** |
| Développement | ⛔ bloqué tant que le moteur n'est pas prouvé |

**Rien ne sera codé avant que le moteur soit prouvé.** Le pari technique — piloter le moteur d'OBS
depuis Rust — repose sur un pont peu éprouvé. Un banc d'essai tranche : il tient, ou on prend le
repli déjà choisi. C'est une règle du projet, pas une précaution de façade.

## Sous le capot

| Couche | Choix | Pourquoi |
|---|---|---|
| Coquille | **Tauri 2.x** (Rust) | Léger, natif — et surtout : isole les pannes |
| Moteur vidéo | **`libobs`** via `libobs-wrapper` | Le moteur d'OBS, embarqué. Jamais réécrit |
| Cœur | **Rust** | Empêche des classes entières de bugs |
| Interface | React 19 + TailwindCSS 4 | Dans la fenêtre Tauri |
| Deck distant (option) | Phoenix (Elixir) | Le deck **local** marche toujours sans serveur |

**Une automation est une donnée, jamais du code exécuté.** C'est ce qui permet de refuser une boucle
*avant* le direct, et ce qui sépare Hikari d'un outil scriptable.

**Hikari n'héberge rien.** L'archivage vise **ton** espace cloud. Aucun compte Hikari, aucune donnée
collectée.

## Plateformes

Windows d'abord. Linux ensuite. macOS différé — pas une porte fermée.

## Licence

**GPL-3.0** — imposée par le moteur d'OBS, et assumée. Le code est lisible, modifiable, et ne peut
pas mourir avec son auteur.

## Documentation

La conception (cahier des charges, plan d'exécution, prototype, analyse concurrence) vit pour
l'instant dans l'espace de conception, le temps du spike. Elle rejoindra `docs/` ici une fois le
moteur tranché.

## Histoire

Une première version (2026, Electron + Canvas + FFmpeg) a été tentée puis abandonnée : elle
réécrivait un moteur vidéo maison — l'erreur à ne pas refaire. Elle est archivée
([`Hikari-Stream-Legacy`](https://github.com/shinkofa/Hikari-Stream-Legacy)). Ce dépôt repart d'une
autre architecture, avec cette leçon écrite noir sur blanc dans le cahier des charges.

---

*Hikari (光) — la lumière. Streamer l'esprit tranquille.*
