---
title: Hikari — Dossier de conception
created: 2026-07-11
updated: 2026-07-17
status: actif
type: index
---

# Hikari — Dossier de conception

> Docs du projet, dans le dépôt du projet (décision Jay 2026-06-27 : CDC/PET vivent
> dans le repo). Rapatriés depuis `Takumi/docs/hikari-stream/` le 2026-07-17 —
> l'historique git de leur écriture reste dans le dépôt Takumi.

## Nature du projet

Application desktop Windows de streaming/enregistrement vidéo, **open-source**, qui
remplace la combinaison actuelle de Jay (OBS + Streamer.bot + deck + scrcpy + Aitum
Vertical + monitoring + pipeline social) par **un seul cockpit**.

Promesse cardinale : **streamer l'esprit tranquille** — config simple, fiabilité
totale, expérience live alignée à l'identité du créateur, sur tout le **parcours**
(création → édition → publication → viewer), jamais un fragment.

## ⛔ Aucun code de production avant B0.0

Le spike moteur (1 jour) **mesure**, il ne décide plus. Une app livrée depuis mars 2022
(`league_record` — Rust + Tauri + moteur d'OBS) a fait tomber le pari technique. Seul
inconnu restant : personne n'a croisé **Rust + moteur d'OBS + diffusion en direct**.

## Fichiers

| Fichier | Contenu |
|---|---|
| `CDC.md` | Cahier des charges **v1.3.0** — 13 sections, l'intention |
| `PET.md` | Plan d'exécution **v1.4.0** — 14 sections, 29 briques, 14 ADR, 64/64 fonctions couvertes |
| `Mockup-Hikari-Stream.html` | Maquette cliquable — 9 écrans, dont **Automations** (le différenciateur) |
| `Vision-Cadrage.md` | Étoile polaire, 3 piliers, 3 points de vue, carte du parcours, principes fondateurs |
| `Veille-Technique.md` | ⚠️ **PÉRIMÉ** (voir ci-dessous) — conservé comme trace |
| `refs-concurrence/` | Analyse Streamer.bot + TouchPortal (rétro-ingénierie du fichier de données réel) |
| `legacy-ancien-repo/` | Documentation + audits rapatriés de l'ancien repo Electron (2026-02 → 03), 13 fichiers |

## ⚠️ `Veille-Technique.md` est périmé — ne pas s'y fier

Trois de ses affirmations étaient fausses, découvert le 2026-07-16 :

| Affirmation | Réalité |
|---|---|
| `libobs-wrapper` 3.0.3 | **9.0.4+32.0.2** — 6 versions majeures d'écart. Chiffre lu sur docs.rs (gelé sur le dernier build réussi) au lieu de l'API crates.io. Il est entré dans un CDC validé, non détecté 5 jours, **sur le composant du go/no-go**. |
| « Aucune app connue en production » | **Faux, et jamais vérifié.** `league_record` livre depuis 4 ans. Trouvé en 3 requêtes, sur demande de Jay. |
| « Réutiliser l'ancien repo » | Écarté — le moteur maison était justement le point faible historique. |

**La leçon, gravée en ADR-010** : la vérité d'une version est l'**API du registre**
(crates.io, npm), jamais un site de documentation. Et un document interne vieillit comme
un article de blog — le Double Regard vaut aussi pour nos propres docs.

## `legacy-ancien-repo/` — l'ancien projet

Rapatrié depuis `shinkofa/Hikari-Stream` (archivé) le 2026-07-11. **Le code source reste
dans le repo archivé** ; seule la documentation est ici.

| Fichier | Rôle |
|---|---|
| `CDC-Hikari-Stream.md` | Cahier des charges de l'époque (328 l) |
| `Architecture-Vision.md` | Vision d'architecture initiale (268 l) |
| `Plan-Implementation-Hikari-Stream.md` | Plan d'implémentation (437 l) |
| `Execution-Plan-2026-03-06.md` | Plan d'exécution (152 l) |
| `Reprise-Hikari-Stream.md` | Guide de reprise + ce qui marchait/ne marchait pas (105 l) |
| `Audit-Complet-2026-02-26.md` | Audit complet (694 l) |
| `Audit-Factuel-2026-02-16.md` | Audit factuel (411 l) |
| `Session-Plan-2026-02-27.md` · `Sprint-Plan.md` | Planning de l'époque |
| `AUDIT-COMPLETE.md` · `SESSION-SUMMARY.md` · `CHANGELOG-SESSION.md` | Résumés de sessions + audits racine |
| `SESSION-2026-02-09-Multi-Webcam-Background.md` | Session multi-webcam + arrière-plan |

> ⚠️ Ces docs reflètent l'**ancienne** approche (Electron + Canvas + FFmpeg, sans moteur
> OBS). À lire comme **matière première historique**, pas comme la cible. La cible est
> dans `CDC.md` + `PET.md`.

## État (2026-07-17)

- ✅ Conception **terminée et auditée** — CDC v1.3.0 + PET v1.4.0, 64/64 fonctions couvertes.
- ✅ Maquette : 9 écrans. Analyse concurrence livrée.
- ✅ 4 fiches de spike exécutables (prérequis · durée bornée · livrable · seuils · verdict).
- ✅ Méthodologie `.claude/` synchronisée dans ce dépôt (2026-07-17).
- ⛔ **B0.0 (1 j)** : diffusion en direct depuis Rust + **surcoût mesuré vs OBS nu**
  (mesure de référence obligatoire — une machine est un point, jamais une courbe).
- ⏳ Après B0.0 : raffiner le PET en version exhaustive (ADR-004).

> État détaillé, décisions actives et sessions : `Shinzo/02-Projets/Hikari-Stream.md`.
