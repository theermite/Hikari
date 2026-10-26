---
title: "05 — Savoir et mémoire"
created: 2026-10-25
updated: 2026-10-25
status: v2
type: regle
fin: F1
proof: hooks (sommaire généré, rappel avant commande) + mesure de l'effet
---

# 05 — Savoir et mémoire

> **Fin servie : F1** — des outils justes. Une méthode qui oublie ce qu'elle a appris paie deux fois.
> Constat de départ : 577 souvenirs, 1 043 documents de savoir, et presque aucun usage mesuré.
> Source : doctrine § 5.

## 1. Trois régimes de lecture

| Régime | Quoi | Règle |
|---|---|---|
| **Toujours chargé** | la doctrine, le profil de Jay, le projet courant | reste petit ; si ça grossit, quelque chose d'autre doit maigrir |
| **Consulté sur déclencheur** | une règle selon la tâche, un souvenir selon le sujet | le déclencheur est nommé, jamais « quand c'est pertinent » |
| **Interrogé à la demande** | le savoir, les archives, la mémoire — par recherche | on paie la requête, jamais le contexte |

**Le critère qui rend la chose mesurable** : une consultation ne compte que si elle **change quelque
chose** — une décision, un test, une ligne de code. Une consultation qui ne change rien est du bruit,
et le bruit se filtre en trois minutes.

## 2. La mémoire n'est pas une archive

- Le **sommaire** est généré depuis les fichiers, jamais écrit à la main.
- Un souvenir s'écrit quand il **change une façon de travailler**, pas quand il raconte un fait.
- Un souvenir périmé se **date** ou se retire : un souvenir faux est plus dangereux qu'un souvenir
  absent, parce qu'il a l'autorité d'une leçon.

**Format d'un souvenir** : un titre qui dit l'action (« ne pas relancer une commande Bash qui a
expiré »), la règle, le pourquoi daté et sourcé, et comment l'appliquer. Un souvenir sans « comment
l'appliquer » est une anecdote.

## 3. Ce qui se consulte au bon moment

| Moment | Ce qu'on rouvre |
|---|---|
| Avant d'écrire du code | la règle de qualité, les pièces existantes, les souvenirs du sujet |
| Avant une commande risquée | les souvenirs de sécurité et d'infrastructure |
| Avant une conception | l'intention de Jay, les décisions déjà prises, le savoir du domaine |
| Avant une mise en ligne | le registre d'infrastructure et les ports |

## 4. La provenance de ce qu'on publie

Tout contenu produit par une IA et publié porte **deux marques** : une lisible par une machine
(métadonnée signée) et une visible pour l'humain. C'est une obligation en vigueur depuis le
2 août 2026, et c'est aussi une question de respect : la personne doit savoir ce qu'elle lit.

## 5. Le registre des ports et de l'architecture

Une seule source, générée. Un service qui démarre sur un port consulte le registre **avant**, et le
registre est mis à jour **dans le même geste**, jamais après. Une dérive entre le registre et la
machine réelle est un défaut, pas une note.

## Annexes

Lues au moment du travail qui les requiert — un garde-fou bloque l'écriture sinon (règle 01 § 7).

| Annexe | Quand |
|---|---|
| `Memoire-Format` | avant d'écrire un souvenir : schéma, dépôt, sommaires |
| `Provenance-Du-Contenu` | avant de publier : la légende fermée, la valeur lisible par machine, la mention visible |
| `Veille-Et-Savoir` | la preuve de savoir avant d'écrire du code |

## Sans hook

Le sommaire et le rappel sont tenus par du code. L'effet d'une consultation ne l'est pas : il se lit
dans le compte rendu (« ce document a changé cette décision »), et la passe hebdomadaire compte les
semaines sans consultation utile.

## Ce que cette règle remplace

`Memory.md` et la partie « provenance » de `Content-Provenance.md`. Le registre de ports, resté
orphelin dans une note de Jay, y entre pour de bon.
