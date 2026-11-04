---
title: "Contrat d'autonomie — <Projet>"
created: AAAA-MM-JJ
updated: AAAA-MM-JJ
status: brouillon
type: contrat-autonomie
project: <projet>
cdc_version: "<version du CDC validée avec ce contrat>"
pet_version: "<version du PET validée avec ce contrat>"
mode: brique            # brique | lot | projet
scope: ["<B01>"]        # brique : 1 id · lot : 2 ids ou plus · projet : all
# briques: ["<B-001>", "<B-002>"]   # OBLIGATOIRE en mode projet : liste fermée, CALCULÉE par `python .claude/hooks/lib/plan_bricks.py docs/PET.md` (jamais recopiée à la main)
deploy: jamais          # jamais | staging | prod-apres-checkpoint
budget:
  cout_max_usd: 0       # plafond du run, mesuré et jamais estimé de mémoire
  tokens_max: 0
  duree_max_h: 0
  alerte_pct: 80        # à ce seuil : digest à Jay, on finit la brique en cours
  arret_pct: 100        # à ce seuil : arrêt propre, journal à jour
livrable:               # ce que Jay vérifie en direct ; verification : script_navigateur | commande | geste_jay
  - id: L1
    preuve: "<parcours de la maquette, ex. écrans 1 à 7 × rôles A et B>"
    verification: script_navigateur
  - id: L2
    preuve: "<comportement attendu>"
    verification: commande
    commande: "<commande qui le prouve>"
checkpoints:
  - id: C1
    apres: "<id de la brique après laquelle Jay vérifie>"   # un jalon sans brique (ex. « fin du lot ») attend Jay dès la reprise
    jay_verifie: "<ce que Jay voit et teste en direct, en une phrase>"
    bloquant: true      # false = digest : le run continue sur les briques indépendantes
  # Obligatoire si deploy n'est pas "jamais" : un point bloquant avec avant_mise_en_ligne: true
  # - id: C2
  #   apres: "<dernière brique>"
  #   jay_verifie: "<la version en ligne>"
  #   bloquant: true
  #   avant_mise_en_ligne: true
---

# Contrat d'autonomie — <Projet>

> Ce contrat est signé par la validation de la conception. Il tient lieu de reformulation
> pour tout le run : rien n'est redemandé à Jay à l'intérieur du périmètre ci-dessous.
> **L'en-tête ci-dessus est validé par du code** (`.claude/hooks/lib/contract_lint.py`) avant tout
> départ : le run ne démarre pas sur la moindre erreur. Ce gabarit non rempli est refusé
> par le linter, à dessein.

## 1. Ce que Jay demande (en clair)

<Une à trois phrases : le mode choisi et pourquoi.>

## 2. Livrable — ce que Jay vérifiera en direct

Le détail de chaque ligne du champ `livrable` de l'en-tête, en langage clair. Jay ne relit
pas le code : cette liste est la définition de « fini ».

## 3. Budget

Estimation avant départ : médiane des coûts par brique des journaux précédents × nombre de
briques × 1,5 (marge de départ, à recalibrer sur les runs réels). Calculée par le linter,
jamais écrite à la main. Sans historique, le linter le dit et Jay confirme le plafond.

## 4. Points de contrôle

Le détail en clair de chaque ligne du champ `checkpoints`.

## 5. Ce que l'agent décide seul / ce qui s'arrête

Les trois portes et le protocole d'arrêt de l'annexe `Session-Autonome.md`, sans changement. Ajouts propres à ce projet : <aucun | …>

## 6. Interdits propres à ce projet

<Liste. Sinon : ceux du disjoncteur de Dogu / de la règle, sans ajout.>

## 7. Caducité

Le contrat est lié à `cdc_version` et `pet_version`. Si l'un des deux change, le linter
refuse de valider (`contract_void`) jusqu'à nouvelle validation par Jay.
