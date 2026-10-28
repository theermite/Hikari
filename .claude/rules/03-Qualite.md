---
title: "03 — Qualité et preuve"
created: 2026-10-25
updated: 2026-10-25
status: v2
type: regle
fin: F1
proof: hooks (veille, tests, complexité, couverture) + bureau de contrôle
---

# 03 — Qualité et preuve

> **Fin servie : F1** — des outils qui tiennent. La qualité est ce qui reste quand personne ne
> regarde ; elle se prouve, elle ne s'affirme pas.
> Source : doctrine § 3 (« fini ») et § 9.

## 1. Ce que « fini » veut dire

Une brique est finie par **trois preuves, écrites avant de coder** :

| Preuve | La question | Qui la juge |
|---|---|---|
| **Visible** | est-ce que ça ressemble à la maquette, à l'écran ? | Jay |
| **Prouvé** | quelle commande, quelle sortie, montrent que ça marche ? | le bureau de contrôle |
| **Éprouvé** | est-ce que ça tient en conditions réelles, en direct ? | Jay |

Les tests verts sont nécessaires et ne suffisent jamais. Une brique sans ses trois preuves n'a pas une
fin : elle a un arrêt.

## 2. Les tests d'abord

Écrire le test, le voir échouer, puis écrire le code. Un test écrit après le code décrit ce que le
code fait, pas ce qu'il devait faire.

| Seuil | Valeur | Tenu par |
|---|---|---|
| Couverture globale | 80 % | mesure locale, pas de porte |
| Chemins critiques (auth, paiement, crypto) | 95 % | mesure locale, pas de porte |
| Tests mutants sur le critique | ≥ 90 % | à installer |
| Lighthouse (performance, accessibilité) | 90 | mesure locale, pas de porte |

Les seuils sont **écrits une fois, ici**. Aucune autre règle ne les répète : un chiffre recopié
vieillit dans l'ombre.

## 2 bis. La classification du risque — un seul endroit

Le niveau de risque d'une brique décide de ce qu'elle doit prouver. Il se lit ici, et nulle part
ailleurs.

| Niveau | Ce qui est touché | Couverture minimum | Preuve supplémentaire |
|---|---|---|---|
| **Critique** | authentification, paiement, crypto, données personnelles, migration | **95 %** | tests de propriété + mutation + MC/DC ; un relecteur de niveau égal ou supérieur, en contexte frais et complet, relit |
| **Sensible** | calcul métier, API publique, synchronisation | **90 %** | relecture indépendante obligatoire |
| **Standard** | fonctionnalité visible, interface | **80 %** | relecture si l'interface est nouvelle |
| **Outillage** | script interne, documentation, outil de développeur | **60 %** | aucun contrôle indépendant requis |

**La règle qui va avec** : déclarer le niveau **avant** la première ligne, et l'écrire dans le plan.
Un niveau déclaré après coup est un niveau choisi pour ce qui a été fait.

## 3. Le contrôle indépendant

Le contexte qui écrit ne valide jamais seul. Trois couches : un test qui peut échouer, un contexte
neuf qui cherche à réfuter, et — sur le critique — un relecteur de niveau égal ou supérieur, en contexte frais et complet (jamais plus faible que le rédacteur).

**Le brief de contrôle est un artefact de preuve** : périmètre, zones suspectes, et l'ordre de
**réfuter**, jamais de valider. Un contrôle qui répond « ça me semble bon » n'a pas eu lieu.

## 4. La maintenabilité

| Seuil | Limite |
|---|---|
| Fonction | 30 lignes, complexité cyclomatique ≤ 10 |
| Fichier | avertissement à 300 lignes, blocage à 500 (hors `.md`, i18n, schémas) |
| Paramètres | 4 maximum, au-delà un objet |

## 5. Ne pas réécrire ce qui existe

Avant d'écrire une pièce, chercher si elle existe déjà — dans le dépôt, dans les paquets partagés,
dans la bibliothèque de composants. Le contrôle se fait sur le **contrat** de la pièce, pas seulement
sur son nom : une pièce forcée hors de son contrat coûte plus cher qu'une construction locale.

## 6. Un correctif est un changement de garde-fou

Un correctif de garde-fou mérite son test, sa relecture par un contexte neuf, et une **mutation** qui
prouve que le test sait rougir. Quatre relectures d'affilée ont un jour trouvé un défaut né du
correctif précédent.

Après un verdict négatif : nommer la famille du défaut, sa cause, et l'artefact qui empêche le
retour. Au deuxième échec de la même famille, changer de méthode — pas réessayer.

**Le recul** (Jay 2026-10-28) : si une correction ne fonctionne pas, prendre du recul sur le problème
pour trouver la **cause racine**, avant d'en tenter une autre. C'est le travail de l'expert, pas un renvoi
vers Jay : lui regarde l'ensemble et propose une autre direction quand la racine n'a pas été trouvée de
manière évidente — on le consulte dans ce cas, pas systématiquement.

**Le marqueur obligatoire** sur tout commit `fix:` ou `hotfix:` (tenu par un garde-fou) :

```
[ROBUSTNESS]
- 6 mois: <pourquoi ça tient dans 6 mois>
- cause racine: <oui — laquelle | non — symptôme supposé parce que ...>
- alternative durable: <aucune valable | voici X, différé parce que Y>
- appelants reels: <oui — comment vérifié (grep, appels) | non-applicable — pourquoi>
- garde a l'envers: <le test rougit-il si on retire le garde-fou ? oui | non-applicable>
```

Dispense légitime, motif fermé : `[ROBUSTNESS-SKIP] motif: <typo|revert|test-fix|lint-fix|formatting|comment-only>`.

## 7. Le test de fin de séance

Six questions, six réponses honnêtes. Un « non » injustifié est un défaut de session :

1. Les commits sont-ils terminés — sans TODO, sans code commenté, sans trace de débogage ?
2. La rigueur a-t-elle tenu — aucune porte sautée ?
3. Les erreurs ont-elles été lues avant d'être corrigées ?
4. La trace suffit-elle à reprendre sans moi ?
5. Chaque « ça marche » est-il prouvé par une commande et sa sortie ?
6. Les choix tiendront-ils encore dans six mois ?

## 8. L'erreur est une donnée

Journaux d'abord, puis les commits récents, puis le code. Jamais d'hypothèse avant d'avoir lu.
Un test rouge trouvé en arrivant est à corriger, quelle qu'en soit l'origine.

## Annexes

Lues au moment du travail qui les requiert — un garde-fou bloque l'écriture sinon (règle 01 § 7).

| Annexe | Quand |
|---|---|
| `Socle-Minimal` | au début de tout projet : les lignes à imprimer dans le cahier des charges et les portes de qualité humaines |
| `Tests-Et-Mesures` | avant d'écrire un test, un seuil, un compteur ou un réglage d'analyse |
| `Interface` | avant toute interface : pièces existantes, accessibilité, performance, dignité |
| `Debug-Et-Blocage` | l'arrêt sur défaut quand un garde-fou n'est pas disponible |

## Sans hook

Les seuils de couverture et de mutation ne sont pas tenus par du code : c'est écrit ici, et ça se
mesure à la passe hebdomadaire. Le reste — veille, complexité, taille de fichier, tests — est tenu
par des garde-fous.

## Ce que cette règle remplace

`Quality.md`, `Monozukuri.md`, `Autonomous-Session.md`, `QE-V2-Retroactive.md`. Le **principe** de
Monozukuri (la qualité est une identité, pas une étape) et ses **six gestes** vivent dans la doctrine,
section « La manière de bâtir » ; son **marqueur de correctif** et son **test de fin de séance** sont
repris ici, aux § 6 et 7. Rien n'est perdu.
