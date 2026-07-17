# Épreuve (a) — diffusion en direct depuis Rust

**Date** : 2026-07-17 · **Machine** : ERMITE-GAME (RTX 3060, Windows 11) · **Moteur** :
libobs 32.0.4 via libobs-wrapper 9.0.4 · **Cible** : MediaMTX v1.19.2 local (rtmp://localhost:1935/live/hikari)

## La question du projet, résolue

Personne n'avait croisé **Rust + moteur d'OBS + diffusion en direct**. C'est fait, prouvé,
reçu de bout en bout par un serveur RTMP.

## Preuves brutes

**Côté moteur (Hikari)** — 15 s de diffusion, processus séparé lancé par le contrôleur :

```
ENGINE:ENCODERS [FFMPEG_AOM_AV1, FFMPEG_SVT_AV1, OBS_NVENC_H264_TEX, OBS_NVENC_HEVC_TEX, OBS_X264]
ENGINE:VIDEO_ENCODER type=OBS_NVENC_H264_TEX hardware=true
[rtmp stream] Connection to rtmp://localhost:1935/live (::1) successful
Output 'hikari-stream': Total frames output: 451   (≈ 30 fps sur 15 s)
ENGINE:STOPPED  → exit code 0
```

**Côté récepteur (MediaMTX)** — la vérité de terrain, l'autre bout du tuyau :

```
[RTMP] [conn [::1]] opened
[path live/hikari] stream is available and online, 2 tracks (H264, MPEG-4 Audio)
[RTMP] [conn [::1]] is publishing to path 'live/hikari'
[RTMP] [conn [::1]] closed: EOF
```

## Verdict par sous-critère (fiche PET B0.0, épreuve a)

| Sous-critère | Seuil | Résultat |
|---|---|---|
| Le flux arrive | reçu par un serveur | ✅ MediaMTX : 2 pistes H264 + AAC, online |
| Codec matériel confirmé | jamais un repli logiciel muet | ✅ `OBS_NVENC_H264_TEX hardware=true` |
| 0 image perdue · débit stable | run long | ⏳ à sceller (5 min + compteur `obs_output_get_frames_dropped`) |

## Ce qui reste pour sceller l'épreuve (a)

1. Run **5 min** + relevé des **images perdues réseau** (pas les images de démarrage).
2. Confirmation sur **Twitch réel** (clé du compte test, via `HIKARI_RTMP_KEY`, jamais committée).

Puis épreuve (b) survie du moteur, (c) surcoût vs OBS nu (le chiffre du spike), (d), (e).

## Comment reproduire

```sh
# Serveur RTMP local
./mediamtx/mediamtx.exe   # écoute :1935

# Diffuser 15 s (défaut MediaMTX local)
cargo run --bin hikari-controller -- 15

# Diffuser vers Twitch (clé jamais écrite dans un fichier)
$env:HIKARI_RTMP_SERVER="rtmp://live.twitch.tv/app"; $env:HIKARI_RTMP_KEY="<clé test>"
cargo run --bin hikari-engine -- 300
```
