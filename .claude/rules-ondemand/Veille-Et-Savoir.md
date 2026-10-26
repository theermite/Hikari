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
