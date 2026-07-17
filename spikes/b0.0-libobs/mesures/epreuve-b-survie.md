# Épreuve (b) — le processus séparé tient (survie + relance)

**Date** : 2026-07-17 · **Machine** : ERMITE-GAME (RTX 3060, Windows 11)

## La question

Si le moteur meurt en pleine diffusion, l'application meurt-elle avec lui ? C'est le pari
fondateur de Jay (ADR-001) et la raison du processus séparé (ADR-013).

## Protocole

Diffuser, puis **tuer de force le processus moteur** (`Stop-Process hikari-engine`) au
milieu du flux. Observer le contrôleur (processus distinct) et le récepteur.

## Preuves brutes

**Côté contrôleur** (`ctrl.log`) — le moteur est tué, le contrôleur ne meurt pas :

```
ENGINE:STARTED secs=30
[rtmp stream] Connection to rtmp://localhost:1935/live (::1) successful
CTRL: /!\ MOTEUR MORT sans finir (code exit code: 0xffffffff) — le controleur a SURVECU
CTRL: relance isolee 1/1...
CTRL: lancement du moteur (processus séparé) : ...\hikari-engine.exe
ENGINE:STARTED secs=30                       (le 2e moteur rediffuse)
[rtmp stream] Connection to rtmp://localhost:1935/live (::1) successful
```

Contrôleur toujours vivant après le kill : PID confirmé par `Get-Process`.

**Côté récepteur** (MediaMTX) — deux sessions, la coupure forcée entre les deux :

```
22:10:27 [RTMP] conn 53432 is publishing to path 'live/hikari'
22:10:38 [RTMP] conn 53432 closed: connection forcibly closed by the remote host   <- le kill
22:10:41 [RTMP] conn 63105 is publishing to path 'live/hikari'                       <- la relance
```

## Verdict

| Critère (fiche PET B0.0, épreuve b) | Résultat |
|---|---|
| L'app survit à la mort du moteur | ✅ contrôleur vivant, ne meurt pas avec le moteur |
| Elle détecte la mort | ✅ code de sortie ≠ 0 capté |
| Elle relance | ✅ relance isolée, 2ᵉ moteur rediffuse |
| Elle le dit | ✅ message explicite (jamais un « ok » muet) |

**ADR-001 (isolation des pannes) et ADR-013 (processus séparé) : prouvés, des deux côtés.**

## Note d'implémentation

Le spike relance **une fois** (borne anti-boucle). En production, la politique de relance
(nombre, backoff, alerte utilisateur) est à définir en B1 — ici on prouve le mécanisme,
pas la politique.
