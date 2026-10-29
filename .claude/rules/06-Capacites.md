---
title: "06 — Capacités, coût et usage"
created: 2026-10-25
updated: 2026-10-25
status: v2
type: regle
fin: F2
proof: vérification au démarrage + indicateurs de la passe hebdomadaire
---

# 06 — Capacités, coût et usage

> **Fin servie : F2** — un process léger. Cette règle est nouvelle : rien de tel n'existait.
> Trois constats mesurés le 25 octobre : des règles exigent des outils absents ; aucun coût n'est
> mesuré ; aucune règle ne vérifie qu'un outil est réellement utilisé par Jay.
> Source : doctrine § 6 et § 7.

## 1. Une règle ne promet jamais une capacité qu'elle n'a pas

Le constat : les règles citent la recherche web, la vision, le coffre de savoir, le navigateur de
test et le suivi d'erreurs. Dans un harnais sans ces outils, chaque marqueur `[VEILLE] … via
<source>` devient une **déclaration fausse** — plus dangereuse qu'une absence, parce qu'elle rassure.

**Donc, au démarrage de chaque session**, l'état des capacités est connu et dit :

| Capacité | Si présente | Si absente |
|---|---|---|
| Recherche web | `[VEILLE] techno@version via source` | `[VEILLE-IMPOSSIBLE] motif: pas-d-acces-web`, et le rapport le dit — **seulement après avoir cherché l'outil, y compris différé** (`ToolSearch`, `select:WebSearch,WebFetch`) |
| Vision (images, captures) | une capture est lue et comparée | aucune preuve visuelle n'est affirmée ; on demande une description ou un test — **seulement après avoir essayé l'outil `Read` sur l'image** |
| Coffre de savoir (MCP) | consultation directe | lecture des fichiers, et on le dit |
| Navigateur de test | vérification d'interface | test automatisé, et on le dit |
| Suivi d'erreurs | le débogage commence là | journal local |
| Lecture de documents | le document est lu | il est signalé illisible, jamais résumé de mémoire |

**L'application fournit la recherche web et la lecture d'images** (Claude Code : `WebSearch`, `WebFetch`,
`Read`). Elles sont **présumées présentes** sauf refus lisible dans les réglages : « non vérifiable par un
garde-fou » ne veut jamais dire « absente » (deux séances ont déclaré l'impossibilité sans chercher l'outil,
2026-10-28). Un harnais d'un autre fournisseur peut ne pas les avoir : le modèle le constate en essayant.

Une dégradation est **toujours explicite**. Jamais silencieuse.

## 2. Le coût se lit, il ne s'estime pas

| Coût | Ce qu'on lit | Ce qu'on fait |
|---|---|---|
| **Contexte** | ce qui est chargé à chaque tour | une amélioration qui ajoute du poids doit en retirer autant |
| **Jetons** | ce que la session consomme | une veille coûteuse se justifie par ce qu'elle évite |
| **Temps de Jay** | accords demandés, minutes de lecture, manipulations | c'est le plus rare : cible zéro hors des cinq arrêts |

Un chiffre de coût annoncé sans être lu est une opinion. On cite la mesure, ou on ne chiffre pas.

## 3. Un outil n'existe que s'il est utilisé

C'est la règle la plus importante de ce document, et la plus neuve.

| Constat | Conséquence |
|---|---|
| Un projet livré que Jay n'ouvre pas | c'est une dette, pas un livrable ; on le dit à la brique suivante |
| Un agent jamais convoqué | il est câblé ou archivé, jamais laissé en sommeil |
| Une règle jamais appliquée | elle est supprimée ou tenue par du code |

Chaque projet porte donc un **critère d'usage, daté** : qui l'utilise, à quelle fréquence, et depuis
quand. Un critère d'usage absent est un signe que le projet n'a pas de raison d'être — ou que sa
raison n'a pas été écrite.

## 4. Ce que ça change dans le travail quotidien

- Une fonctionnalité dont personne ne se sert ne se répare pas : elle se retire.
- Une bibliothèque partagée ne se juge pas au nombre de composants, mais au nombre de projets qui
  l'importent.
- Un indicateur qui ne change aucune décision est un indicateur à supprimer.

## Sans hook

La sonde `lifecycle/capacites-check.py` annonce au démarrage ce qui est déclaré, refusé ou non
vérifiable (registre : `.claude/rules-ondemand/capacites.json`). Sa limite est écrite : elle ne voit pas les outils
réellement chargés, donc « déclarée » n'est pas « connectée ». La confirmation reste au modèle, d'après sa
propre liste d'outils (outils différés compris : `ToolSearch`), en première ligne du rapport. Le coût et l'usage se mesurent à la passe hebdomadaire.

## Ce que cette règle remplace

Rien : elle est nouvelle. Elle répond aux exigences 45 à 48 du programme de réécriture.
