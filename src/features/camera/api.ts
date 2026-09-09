// Camera Tauri bridge (B-cam tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { MaskShape } from "../scenes/types";
import type { CameraDevice } from "./types";

/** Lists the real camera devices detected on this machine (`list_cameras`,
 * `camera_bridge.rs`) — never a hardcoded/presumed list (F-003's spirit). */
export function listCameras(): Promise<CameraDevice[]> {
  return invoke("list_cameras");
}

/** Pose la caméra `deviceId` (valeur exacte venue de `listCameras`) dans `scene`.
 *
 * Un appareil = une caméra. La source n'est ouverte qu'à la première demande ; toute scène
 * suivante réutilise la même, avec son propre cadrage. Exige le moteur démarré. */
export function addCameraSource(
  deviceId: string,
  scene: string,
): Promise<void> {
  return invoke("add_camera_source", { deviceId, scene });
}

/** Active ou coupe le fond détouré (NVIDIA) de la caméra `deviceId` DANS `scene`.
 *
 * Interrupteur instantané, jamais une reconstruction. L'état est propre à la paire
 * caméra + scène : deux caméras d'une même scène peuvent avoir deux allures. */
export function setBackgroundRemoval(
  deviceId: string,
  scene: string,
  enabled: boolean,
): Promise<void> {
  return invoke("set_background_removal", { deviceId, scene, enabled });
}

/** Règle la forme de masque (aucun/cercle/coins arrondis). Même contrat que
 * `setBackgroundRemoval` — une seule forme active à la fois. */
export function setMaskShape(
  deviceId: string,
  scene: string,
  shape: MaskShape,
): Promise<void> {
  return invoke("set_mask_shape", { deviceId, scene, shape });
}

/** Relance l'appareil `deviceId` sans le retirer d'aucune scène.
 *
 * Le geste que Jay a dû faire à la main pendant un direct de 1 h 51 : sa caméra a figé, il
 * l'a retirée de la scène et remise. Ça marchait — et ça lui a coûté son cadrage, ses
 * filtres et sa place dans la pile, à refaire pendant que les spectateurs regardaient.
 *
 * Par APPAREIL et non par scène : c'est l'appareil qui décroche, et toutes les scènes qui
 * le montrent sont figées ensemble. */
export function restartCamera(deviceId: string): Promise<void> {
  return invoke("restart_camera", { deviceId });
}

/** Retire la caméra `deviceId` de `scene` seulement — les autres caméras de la scène
 * restent, et les autres scènes gardent celle-ci avec leurs propres filtres. */
export function removeCameraSource(
  deviceId: string,
  scene: string,
): Promise<void> {
  return invoke("remove_camera_source", { deviceId, scene });
}

/** Déplace la caméra `deviceId` dans `scene` de `(dx, dy)` pixels — un pas fixe par clic,
 * jamais un glissement brut (celui de la bibliothèque de panneaux casse en silence dans
 * cette version de la vue web, vécu le 2026-07-23). */
export function nudgeCamera(
  deviceId: string,
  scene: string,
  dx: number,
  dy: number,
): Promise<void> {
  return invoke("nudge_camera", { deviceId, scene, dx, dy });
}

/** Agrandit ou réduit la caméra `deviceId` dans `scene` d'un pas fixe. Même exigence. */
export function scaleCamera(
  deviceId: string,
  scene: string,
  grow: boolean,
): Promise<void> {
  return invoke("scale_camera", { deviceId, scene, grow });
}
