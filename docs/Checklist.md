---
title: Hikari — Checklist du projet
created: 2026-09-14
updated: 2026-09-14
status: active
type: checklist
project: Hikari Stream
---

# Hikari — Checklist du projet

> Vue d'ensemble à consulter au lieu de redemander « où en est-on ? ». Détail complet et
> historique de chaque brique → `docs/PET.md`. Cette page en est le résumé exhaustif, tenu
> à jour à chaque session.
>
> **Légende** : `[x]` fait et prouvé à l'écran · `[ ]` pas encore (en cours ou non commencé,
> le détail le dit) · 🟧 = entamé mais pas fini.

## 1. Les fondations (déjà construites, closes)

Rien à faire dessus — elles portent tout le reste.

- [x] Moteur OBS en processus séparé, qui survit et se relance si tué
- [x] Diffusion réelle RTMP/NVENC (une plateforme)
- [x] Multistream horizontal (plusieurs plateformes à la fois)
- [x] Comptes Twitch + YouTube connectés (OAuth + coffre)
- [x] Clé de diffusion transmise au moteur sans réglage manuel (Twitch prouvé ; YouTube reste, flux différent)
- [x] Deck local (< 100 ms, fonctionne sans réseau)
- [x] Moteur d'automations (condition/délai/séquence/déclencheurs) — la logique, pas encore son écran
- [x] Coque du cockpit (panneaux, modes Préparation/Live/Focus)
- [x] Installation en un seul exécutable (moteur OBS embarqué, testée sur machine vierge)
- [x] Mises à jour reçues dans l'app (bandeau → redémarrage)
- [x] Sources de scène : ajouter/retirer/réordonner (jeu, fenêtre, écran, image, vidéo, texte), déplacer/redimensionner à la souris, verrouillage — page web restant bloquée (greffon non embarqué)
- [x] Caméra comme source ordinaire, plusieurs caméras en même temps, masques (cercle/coins arrondis), fond IA
- [x] Multi-scènes : créer/lister/basculer, collections (onglets par contexte)
- [x] La session survit à la fermeture (scènes + sources prouvé ; caméra/audio codés mais jamais revérifiés à l'écran depuis)

## 2. Ordre de travail actuel (décidé par Jay, 2026-09-06)

| # | Sujet | Statut |
|---|---|---|
| 1 | Aligner l'application sur la maquette | [x] fermé 2026-09-13 |
| 2 | Réglages d'encodage — mesurer la machine, proposer une config qui tient | [x] fermé 2026-09-13 (zoom d'aperçu corrigé, pré-vol qui propose, Démarrer jamais bloquant) |
| 3 | Caméra qui décroche, relance automatique | [ ] **stoppé 2026-09-13** : la détection (lire l'image de la caméra) perturbait la caméra elle-même — cassait des caméras saines. Coupée. Reste acquis : bouton « Relancer » + icône ↻ sur la ligne, en un clic. Reste à faire : trouver une détection sans effet de bord, si on y revient. |
| 4 | Le moteur se ferme avec la fenêtre (dette actuelle : il continue de tourner) | [ ] |
| 5 | Automations — l'écran pour les composer (le moteur logique existe déjà) | [ ] |
| 6 | Scènes — transitions, mouvements automatiques | [ ] (déplacer/redimensionner à la souris déjà fait) |
| 7 | Sources — page web, poignées visibles | [ ] (texte déjà fait) |
| 8 | Filtres de sources (au-delà de la caméra) | [ ] |
| 9 | Chat — messages, modération, alertes, bandeaux, objectifs | [ ] |
| 10 | Deck mobile (pont VPS + permissions) | [ ] |
| 11 | Audio — atténuation automatique (ducking), formes d'onde | [ ] (mixeur + suppression de bruit + volumes séparés déjà faits) |
| 12 | Caméra mobile | [ ] |
| 13 | Vertical (double encodage simultané) | [ ] |
| 14 | Édition — marqueurs, clips, replay, sous-titres, chapitres | [ ] |
| 15 | Publication — planning, miniatures, pont Kobo | [ ] |
| 16 | Suivi — statistiques, débit, viewers | [ ] |
| 17 | Accueil — tableau de bord | [ ] |
| 18 | Paramètres — écran unifié (comptes/périphériques/encodage/deck/marque/stockage) | [ ] |
| 19 | Assistant d'accueil (wizard première ouverture) | [ ] |
| 20 | Marque — kit + propagation automatique | [ ] |
| 21 | Avatar VRM (2 étapes) | [ ] |
| 22 | Confort — morphique, palette de commandes Ctrl+K, accessibilité WCAG | [ ] |

## 3. Dérisquages jamais faits (à trancher si on les reprend)

- [ ] Sous-titres live locaux — un test pour savoir si la machine peut transcrire sans ralentir le stream (utile avant l'item 14)
- [ ] Détachement d'un panneau sur un second écran — jamais testé séparément (la coque existe déjà sans ce test)

## 4. Pas dans la liste de Jay, mais toujours au plan (à statuer)

- [ ] Connexion à un espace cloud personnel (Drive/Dropbox/OneDrive/S3) + archivage automatique — jamais rattaché à un numéro de la liste ci-dessus
- [ ] Contrôles rapides (mute micro, confidentialité écran, caméra virtuelle, co-stream, don discret) — même cas

## 5. Volontairement pour plus tard

- [ ] Copilote IA conversationnel (compose une scène par la conversation) — décision de Jay 2026-09-09 : fin de feuille de route, pas avant tout le reste
- [ ] Panneaux d'éclairage virtuels (fenêtres pleine couleur en second écran, façon panneau à diodes) — idée notée, jamais planifiée

## 6. Dette connue, acceptée pour l'instant

- Le pré-vol d'un second « Démarrer » juge sur le réglage FICHIER, jamais sur ce que le moteur déjà lancé encode réellement — tant qu'il n'est pas relancé.
- Le moteur ne se ferme pas avec la fenêtre (item 4 ci-dessus).
