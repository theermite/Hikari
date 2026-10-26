---
title: "02 — Parcours du travail"
created: 2026-10-25
updated: 2026-10-25
status: v2
type: regle
fin: F1, F2
proof: hooks existants (gates, review, smoke) + recette écrite
---

# 02 — Parcours du travail

> **Fins servies : F1** (des outils qui marchent) et **F2** (un process léger). Cette règle décrit
> le trajet d'une demande jusqu'à un outil que Jay utilise.
> Source : doctrine § 3, § 4, § 7.

## 1. Le parcours, en sept étapes

> **Il se déclenche par une demande en langage normal**, jamais par une commande que Jay devrait
> retenir. Les commandes sont des listes de contrôle pour moi ; pour Jay, il n'y en a aucune.

| # | Étape | Ce qui est produit | Qui juge |
|---|---|---|---|
| 1 | **Cadrer** | la note d'intention : le besoin, le pourquoi, ce que ça change pour Jay | Jay, une fois |
| 2 | **Planifier** | les briques, chacune avec ses **trois preuves écrites avant de coder** | Jay, sur le plan |
| 3 | **Réaliser** | une brique = un commit atomique ; un tag de sauvegarde tous les trois ou quatre commits | — |
| 4 | **Prouver** | les trois preuves : visible, prouvé, éprouvé | Jay et le bureau de contrôle |
| 5 | **Mettre en service** | mise en ligne + test de fumée | Takumi seul |
| 6 | **Faire exister** | l'outil est **utilisé** par Jay : c'est la seule preuve qu'il existe | Jay |
| 7 | **Entretenir** | la passe hebdomadaire | Takumi seul |

**L'étape 6 est nouvelle et elle est décisive** : un projet que Jay n'utilise pas n'est pas un
projet, c'est une dette. Aucune brique ne s'ouvre sur un projet non utilisé sans que ça soit dit.

## 2. Le plan d'une brique nomme ses agents

Une brique porte, avant de commencer :

- ses **trois preuves** (visible / prouvé / éprouvé) ;
- les **agents convoqués**, et l'étape qui les convoque ;
- ce qui **n'est pas touché**.

Un agent qu'aucune étape ne nomme ne sera pas convoqué. Mesure de départ : 5 agents convoqués sur 32.

## 3. Les portes qualité, toujours actives

| Porte | Ce qu'elle refuse |
|---|---|
| Contexte | coder sans avoir lu le plan ou le cahier des charges existant |
| Veille | écrire du code sans avoir déclaré la version vérifiée — **ou déclaré qu'on ne peut pas vérifier** |
| Tests d'abord | livrer un comportement sans test qui échoue avant |
| Lint / tests | laisser une erreur, ou dire « ça devrait marcher » |
| Sécurité | un secret, une entrée non validée, un motif faible |
| Relecture indépendante | mettre en service sans un contexte neuf qui a cherché à réfuter |
| Mise en ligne | déployer sans test de fumée ni retour arrière prêt |

**La porte Veille a changé de forme** : si la capacité de recherche web est absente, la règle ne
prétend pas avoir vérifié. Elle déclare `[VEILLE-IMPOSSIBLE] motif: pas-d-acces-web` et le rapport
le dit. Une déclaration fausse coûte plus cher qu'une absence.

## 4. La mise en service

- Test de fumée dans les cinq minutes : la route protégée sans jeton répond 401, avec répond 200 ;
  les dépendances répondent ; les parcours critiques passent.
- **Fix = déployé et vérifié.** Un correctif non déployé n'est pas un correctif.
- Retour arrière prêt avant de commencer, jamais après.

## 5. La documentation avance avec le code

Le compte rendu, la fiche projet et les décisions se mettent à jour **pendant** le travail. Écrire la
trace après coup revient à la perdre : le contexte d'une brique est frais juste après l'avoir posée.

## 6. Ce qui n'est pas une étape

- Un compte rendu de session n'est pas une clôture : c'est une trace. Jay seul décide qu'une session
  est finie.
- Une mise en ligne sur le serveur de Jay n'est pas un arrêt : c'est du travail, avec son test.

## 7. Un seul écrivain par dépôt

Plusieurs séances peuvent travailler en parallèle — c'est voulu — mais pas écrire dans le même dépôt
au même moment : trois collisions réelles l'ont montré (un commit qui embarque le travail de l'autre,
une branche changée sous ses pieds). Un garde-fou note qui écrit ; une autre séance est **avertie**, et
`commit`, changement de branche, fusion et poussée sont **refusés** tant que l'autre écrit. Deux issues :
attendre ou travailler dans un `worktree` séparé ; ou, si c'est le même chantier ouvert dans deux
fenêtres, ajouter `# WRITER-OK: <raison>`. Un contrôleur n'écrit jamais ; un sous-traitant rend sa part
au maître d'œuvre.

## Annexes

Lues au moment du travail qui les requiert — un garde-fou bloque l'écriture sinon (règle 01 § 7).

| Annexe | Quand |
|---|---|
| `Conduite` | au premier travail de la séance : gestes de fond, plan par brique, contrat d'autonomie |
| `Veille-Et-Savoir` | avant d'écrire du code : version vérifiée, marqueurs, double regard |
| `Mise-En-Service` | avant et après une mise en ligne : le test de fumée complet |
| `Debug-Et-Blocage` | en enquêtant sur un bug, ou après un refus d'un garde-fou |
| `Reprise-Et-Contexte` | en écrivant le rapport, à la compaction : fils ouverts, contexte |
| `Notation` | en écrivant le rapport : notes et reproches de livraison |
| `Session-Autonome` | avant un lot de briques sans validation brique par brique |

## Sans hook

Les portes sont tenues par des garde-fous pour la moitié d'entre elles. Pour le reste — le plan qui
nomme ses agents, l'étape 6 — c'est la passe hebdomadaire qui mesure l'écart, pas la bonne volonté.

## Ce que cette règle remplace

`Workflows.md`. Ses huit portes deviennent six, la huitième (vérifier) devient la **recette** du § 1,
et la porte de reformulation cesse d'exiger une approbation.
