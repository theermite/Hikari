---
title: "Annexe — Veille et preuve de savoir avant d'écrire du code"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Veille et preuve de savoir avant d'écrire du code

> **Quand la lire** : avant d'écrire du code source ou de toucher un manifeste de dépendances.
> **Pourquoi** : Le savoir du modèle est présumé périmé : version et source se déclarent avant d'écrire.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Workflows.md#4 -->
## Veille/SKB Evidence Protocol (BLOCKING — hook-enforced)

Before any Write/Edit on source code (`.ts/.tsx/.js/.py/.ex/.exs/.rs/.go`) or a deps
manifest, have emitted a marker:

```
[VEILLE] <techno>@<version> verifie <YYYY-MM-DD> via <source>
[SKB] consulte: <path1>, <path2>
[VEILLE-SKIP] motif: <enum>
```

SKIP enum (closed): `typo` · `internal-refactor-no-new-deps` · `hotfix-known-root-cause`
· `test-only` · `methodology-edit` · `generated-artifact`. Any other motif → BLOCK.
3 layers: A closed enum · B sensitive diff (manifest, new import, version pin) → ONLY
[VEILLE] accepted · C counter of 3 consecutive SKIPs → BLOCK. **The model's dataset is
presumed stale by default**: every version/API/CVE/best-practice is verified as of today,
never from internal knowledge.

<!-- source: ajout 2026-10-31 (recherche de fond en sept langues, Jay : règle ciblée) -->
## Recherche de fond en sept langues (règle 05-Savoir § 6)

**Ce qui compte comme recherche de fond** : choisir une technologie ou une bibliothèque · un bug qui
résiste à deux correctifs · enrichir Eichi · comprendre un comportement inconnu · croiser une annonce
officielle avec le terrain. **Ce qui n'en est pas une** : vérifier une version, une syntaxe, une option
connue (une langue, la source officielle).

**Les sept langues** : EN, FR, ZH, JA, KO, DE, RU, chacune dans son écriture native (idéogrammes, kana,
hangul, cyrillique). Origine : feedback de Jay du 2026-05-26, « les agents prétendent avoir cherché en
7 langues sans le faire » ; décision de Jay du 2026-10-31 de la rendre ciblée ; ce n'est pas le nombre de langues qui compte d'abord, c'est la couverture dite
honnêtement.

**Le marqueur** (dernière réponse de la recherche) :

    [LANGUES] EN=ok FR=ok ZH=ok JA=rien KO=rien DE=ok RU=ok

Les sept langues y figurent toutes. `ok` : une requête au moins a été lancée dans cette langue. `rien` :
cherché sans résultat, ou non cherché — c'est permis et c'est dit.

**Qui cherche** : les agents qui détiennent un outil web. **Le serveur web d'abord** : `web_search` et `web_read` (moteur du VPS, aucun modèle appelé, aucun frais par requête) ; `WebSearch` et `WebFetch` seulement en repli déclaré (règle 06-Capacites § 1). Le contrôle du parc exige que tout agent qui garde l'outil intégré tienne aussi les deux outils du serveur ; `quality/serveur-web-d-abord.py` rappelle, sans bloquer, une fois par séance. Les autres (base de données,
sécurité, qualité du code, interface, bureau, CI, IA, déploiement) rendent la main à Takumi, qui convoque
`Veille Master` ou `Deep Research Master` ; ceux-ci rendent la couverture avec leur note. Pour lire une page, l'outil est le serveur
web de Jay (`web_read`), plus Playwright.

**Garde-fou** : `.claude/hooks/quality/langues-check.py` (fin de tour) compare le marqueur aux requêtes
réellement lancées dans la séance. Limites écrites : (1) il ne juge qu'une réponse qui porte le marqueur
EMIS — seul sur sa ligne, en clair ou en gras ; cité entre accents graves, dans une liste ou dans un bloc de code,
il n'est pas lu ; la règle dit quand le poser, le hook ne le devine pas ; (2) il tourne aussi à la fin de chaque
sous-agent, sur son propre journal ; si Takumi a lancé un sous-agent depuis le dernier message de Jay, seule la
forme du marqueur de Takumi est jugée ; (3) les requêtes comptées sont celles de toute la séance (ou de tout le journal de l'agent), pas du seul tour : une recherche chinoise antérieure valide un ZH=ok ultérieur ; (4) un journal absent ou illisible n'est pas jugé ; (5) un exemple cité seul sur sa ligne est lu comme émis ; (6) la langue d'une requête se lit à la forme : stricte pour ZH, JA, KO
et RU, indulgente pour EN, FR et DE (un texte latin sans mot-outil ni accent couvre les trois).

**Mesure d'un essai (2026-10-31)** : sur « PostgreSQL 18 asynchronous I/O », la recherche chinoise a trouvé
deux mesures indépendantes (gain de 1 % sur RDS, échec au démarrage avec `io_uring` sur un vieux noyau) que
les sources anglaises, qui répétaient « jusqu'à 3 fois », ne montraient pas.
