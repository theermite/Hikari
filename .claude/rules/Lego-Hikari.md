# Lego-Hikari — Pourquoi Hikari ne dépend pas de `@shinkofa/ui`

**Proof state**: 🟢 robuste — contrainte de licence, vérifiable dans les deux dépôts.

> Adapte `Quality.md` § « Lego Library » au seul projet libre et public de l'écosystème.
> Décision de Jay, 2026-09-04.

**Niveau** : BLOCKING.

**Règle** : les composants d'interface de Hikari vivent **dans Hikari**. Une pièce de
`@shinkofa/ui` entre ici en **copiant sa source**, avec sa provenance écrite en tête du
fichier — jamais en ajoutant une dépendance au paquet.

**Pourquoi** : `@shinkofa/ui` est sous licence `UNLICENSED` (propriétaire) et publié sur un
registre privé. Hikari est public et sous **GPL-3.0**, licence imposée par le moteur OBS
qu'il embarque. Les deux se heurtent sur deux plans à la fois :

| Plan | Ce qui casse |
|---|---|
| Licence | La GPL exige que l'ensemble distribué soit sous licence compatible. Du code propriétaire lié à du GPL ne l'est pas. |
| Compilation | Le paquet vit sur un registre privé. N'importe qui clonant le dépôt public ne peut plus construire l'application. |

Jay est propriétaire des deux dépôts : il peut donc placer une pièce de sa bibliothèque
sous GPL pour cet usage précis. C'est la copie-avec-mention ci-dessus, et elle règle les
deux plans d'un coup — le second n'est pas réglé par une simple licence.

**Ce que ça ne change pas** : la règle Lego reste entière **partout ailleurs**. Elle
protège contre une duplication mesurée à 146 fichiers dans l'écosystème (`Quality.md`).
L'exemption vaut pour Hikari, pas pour le principe.

**Déclencheur** : créer un composant d'interface dans Hikari, ou vouloir y réutiliser une
pièce de `@shinkofa/ui`.

**Ce qu'il faut évaluer avant de copier** (mesuré, jamais supposé) : une pièce de
`@shinkofa/ui` s'appuie sur les jetons de style `ui-*` des plateformes web, tandis que
Hikari a les siens, `hikari-*`. Copier une petite pièce fait donc entrer une seconde
charte graphique pour économiser quelques dizaines de lignes — mesuré le 2026-09-04 :
`Badge` 30 lignes, `Card` 37. Sur une grosse pièce autonome, l'arbitrage peut s'inverser.

**Preuve** : `git grep "@shinkofa/" -- package.json` ne renvoie rien. Tout composant copié
porte en tête la ligne de provenance et la mention de licence.

**Sans hook** : avant d'écrire un composant, dire d'où il vient — écrit ici, ou copié de
`@shinkofa/ui` sous GPL-3.0 par décision du propriétaire.

**BLOCKING recap** : composants locaux · copie-avec-mention autorisée · dépendance au
paquet interdite · la règle Lego générale reste entière ailleurs.
