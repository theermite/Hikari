# Épreuve (c) — surcoût CPU/mémoire vs OBS nu

**But** : le seul chiffre transférable à toutes les machines (ADR-014). On ne mesure pas
la machine, on mesure **notre surcoût** : « on coûte X % de plus qu'OBS nu, à travail égal ».

**Méthode identique des deux côtés** (`measure.ps1`) : même source (capture d'écran,
écran 1), même sortie (NVENC H264, CBR 6000 kbps, keyint 2 s), même cible (MediaMTX
local), même fenêtre de mesure. CPU % = secondes-CPU / secondes-horloge / cœurs × 100.

**Machine** : ERMITE-GAME, RTX 3060, Windows 11 · **Date** : 2026-07-17

> ⚠️ **Limite honnête** : OBS Studio nu porte le coût de son interface Qt qu'Hikari
> (moteur sans interface) n'a pas ; Hikari porte le coût du tuyau inter-processus qu'OBS
> n'a pas. Le chiffre reste le meilleur proxy transférable pour F-003.

## Relevés bruts

Hikari (moteur+controleur) : CPU 0.8% (moy, 12 coeurs) - GPU 27.1% - encodeur 34.9% - RAM 487.2 Mo moy / 487.5 Mo max - fenetre 92s - 2026-07-17 22:08

**OBS nu (référence)** : ⏳ à mesurer — même réglage, même cible MediaMTX. Bloc réservé.

> Lecture : le coût d'Hikari est presque entièrement sur le **GPU** (NVENC), le CPU est
> quasi nul (0,8 %). Le surcoût vs OBS se jugera donc surtout sur GPU/encodeur, pas CPU.
