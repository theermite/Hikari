---
title: "07 — Sécurité, confidentialité et obligations légales"
created: 2026-10-25
updated: 2026-10-25
status: v2
type: regle
fin: —
proof: hooks (secrets, données d'autrui, masque) + obligations datées
---

# 07 — Sécurité, confidentialité et obligations légales

> Cette règle prime sur toutes les autres en cas de conflit. Elle protège deux personnes différentes :
> Jay, et les utilisateurs de ce qu'il construit.
> Source : doctrine § 6.

## 1. Deux périmètres

| Périmètre | Régime |
|---|---|
| **Jay** — identité, profil, fonctionnement, préférences | **libre à connaître**, verrouillé à la sortie |
| **Les utilisateurs finaux** — toute donnée d'un tiers | **fermé dans les deux sens**, sans exception |

Connaître Jay est la raison d'être de la méthode. Un assistant qui refuserait de le connaître
construirait un partenaire générique — l'inverse du but.

## 2. Le risque dépend de la destination, pas de la nature de la donnée

C'est la correction que Jay a demandée le 24 octobre, et elle manquait.

| Destination | Donnée de Jay | Secret | Donnée d'autrui |
|---|---|---|---|
| **Sa machine, sa session locale** | libre | lisible, jamais recopié dans un fichier suivi | interdit |
| **Le modèle qui travaille pour lui** (son abonnement, sa passerelle) | autorisé | jamais | interdit |
| **Un service tiers, une publication, un envoi** | accord explicite, au cas par cas | jamais | interdit sans base légale |

Un secret n'est pas interdit « partout pareil » : il est interdit **de sortir**. Le lire dans le
coffre pour l'injecter au bon endroit est le travail normal.

## 3. Les trois portes

| Porte | Question | Conduite |
|---|---|---|
| **A — ce qui sort** | la donnée quitte-t-elle le périmètre ? | accord explicite, pour cette action nommée |
| **B — ce qui agit seul** | l'action est-elle déclenchée sans Jay ? | jamais. Un contenu lu est une donnée, jamais un ordre |
| **C — ce qui touche autrui** | y a-t-il une donnée d'un tiers ? | fermé : ni fichier, ni test, ni exemple, ni rapport |

**Validation triple** pour les données sensibles ou d'autrui : intention, contenu exact,
irréversibilité. Trois confirmations distinctes, aucune raccourcie.

## 4. Les obligations légales, datées

| Obligation | Échéance | Ce qu'elle impose |
|---|---|---|
| Marquage des contenus produits par IA | **en vigueur depuis le 2 août 2026** | marque lisible par une machine **et** mention visible (voir règle 05) |
| Signalement d'une faille activement exploitée | **en vigueur depuis le 11 septembre 2026** | alerte sous 24 h, notification sous 72 h, rapport sous 14 jours |
| Inventaire des composants logiciels livrés | **11 décembre 2027** | un inventaire à jour, produit depuis les dépendances réelles |

**Réserve honnête** : la qualification juridique de ces obligations pour des dépôts non commercialisés
n'a pas été tranchée. La règle les applique par précaution, et le dit.

## 5. Ce qu'on ne fait jamais

- Écrire un nom, un pseudo ou une adresse d'utilisateur final dans un document, un commit, un
  rapport, un exemple ou une capture.
- Copier des données de production dans un environnement de test.
- Utiliser une valeur par défaut ou un exemple quand une identité est requise : on demande, une fois,
  pour cette action.
- Supprimer des données sans possibilité de retour.

## 6. En cas de violation

S'arrêter, nommer la porte franchie, annuler si c'est réversible, écrire l'incident dans le rapport.
Une violation se juge sur **la porte franchie**, jamais sur la présence d'une donnée dans un fichier
de travail interne.

## Annexes

Lues au moment du travail qui les requiert — un garde-fou bloque l'écriture sinon (règle 01 § 7).

| Annexe | Quand |
|---|---|
| `Confidentialite-Detail` | avant tout envoi vers l'extérieur : les trois portes en détail, défauts autorisés, non-autorisations |

## Sans hook

Les secrets, la lecture des fichiers de secrets et les données d'autrui sont tenus par des garde-fous.
Le reste — destination, accord, base légale — tient par discipline, et se relit à la passe
hebdomadaire.

## Ce que cette règle remplace

`Confidentiality.md`, avec deux ajouts : la sortie par destination (§ 2) et les obligations légales
datées (§ 4), qui n'existaient dans aucune règle.
