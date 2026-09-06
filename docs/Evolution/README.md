---
title: Évolution visuelle de Hikari
created: 2026-09-07
updated: 2026-09-07
status: active
type: reference
---

# Évolution visuelle de Hikari

Une capture du cockpit par version publiée. Idée de Jay, 2026-09-07.

## Pourquoi ce dossier existe

Trois raisons, et elles ne se recouvrent pas :

| Raison | Ce que ça sert |
|---|---|
| **Preuve** | La règle du projet dit que la preuve est à l'écran, jamais dans un test vert. Le rendu réel du moteur n'est pas vérifiable sans machine — une capture datée est l'artefact qui manque. |
| **Visibilité** | Hikari est public et libre. Une évolution visuelle raconte le projet mieux qu'un journal de commits. |
| **Mémoire** | Dans six mois, personne ne se souviendra de l'écran d'aujourd'hui. Une décision de design se juge à ce qu'elle a remplacé. |

## Où déposer

Les captures brutes vont dans `a-trier/`, sous n'importe quel nom. Elles y attendent d'être
choisies, renommées et converties. Ce dossier est un sas, jamais une destination.

Les captures retenues vivent à la racine de `Evolution/`, sous ce nom :

    <version>-<ecran>.webp

Par exemple : `0.5.1-cockpit.webp`, `0.5.1-scenes.webp`, `0.4.0-cockpit.webp`.

- `<version>` est celle qui tournait, telle qu'elle s'affiche en haut à droite du cockpit ;
- `<ecran>` dit ce qu'on regarde : `cockpit`, `scenes`, `audio`, `comptes`, `prevol`.

Une capture d'un état AVANT toute version publiée porte sa date à la place :
`2026-08-06-cockpit.webp`. C'est le seul cas où la date remplace le numéro.

## La règle qui protège le dépôt

**Aucun gros média ici.** Un fichier lourd se fossilise dans l'historique de git : il
alourdit chaque copie du dépôt pour toujours, même supprimé ensuite. Hikari est public,
donc chaque personne qui le clone porte ce poids.

Concrètement : **WebP, et rien d'autre**. Une capture de cockpit en 1920 de large y pèse
100 à 250 Ko, contre 2 à 4 Mo en PNG. Jamais de vidéo, jamais de rafale — une capture par
écran et par version suffit à raconter.

## Ce qu'on ne fait pas

- Pas de capture montrant une clé, un jeton, une adresse privée ou un nom de compte. Le
  dépôt est public : ce qui entre ici n'en sort plus.
- Pas de capture d'un chat en direct avec de vrais pseudonymes — ce sont les données de
  quelqu'un d'autre.
- Pas de retouche qui embellit. Une évolution qui ment ne sert plus de preuve.
