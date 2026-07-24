// Camera Tauri bridge (B-cam tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { CameraDevice } from "./types";

/** Lists the real camera devices detected on this machine (`list_cameras`,
 * `camera_bridge.rs`) — never a hardcoded/presumed list (F-003's spirit). */
export function listCameras(): Promise<CameraDevice[]> {
  return invoke("list_cameras");
}

/** Puts `deviceId` (exact value from `listCameras`) into `scene` (`add_camera_source`,
 * `engine_lifecycle.rs`, multi-scene tranche 2) — the ONE physical camera, reused if
 * another scene already shows it. Requires the engine running (the Aperçu panel open). */
export function addCameraSource(
  deviceId: string,
  scene: string,
): Promise<void> {
  return invoke("add_camera_source", { deviceId, scene });
}

/** Sets whether the real NVIDIA background-removal filter is enabled for `scene`
 * (`set_background_removal`) — instant toggle (`obs_source_set_enabled`), independent per
 * scene: each scene remembers its own on/off state. Requires a camera already in `scene`. */
export function setBackgroundRemoval(
  scene: string,
  enabled: boolean,
): Promise<void> {
  return invoke("set_background_removal", { scene, enabled });
}

/** Sets whether the circular alpha mask filter is enabled for `scene`
 * (`set_circle_mask`). Same per-scene, instant-toggle contract as `setBackgroundRemoval`. */
export function setCircleMask(scene: string, enabled: boolean): Promise<void> {
  return invoke("set_circle_mask", { scene, enabled });
}

/** Removes the webcam from `scene` only — other scenes keep showing it with their own
 * filter state untouched (`remove_camera_source`). */
export function removeCameraSource(scene: string): Promise<void> {
  return invoke("remove_camera_source", { scene });
}

/** Moves the webcam's placement within `scene` by `(dx, dy)` pixels (`nudge_camera`, B7) —
 * a fixed step per click, never a raw drag delta (dockview's own drag broke silently in
 * this WebView2 build, session 2026-07-23). Requires a camera already in `scene`. */
export function nudgeCamera(
  scene: string,
  dx: number,
  dy: number,
): Promise<void> {
  return invoke("nudge_camera", { scene, dx, dy });
}

/** Grows or shrinks the webcam's placement within `scene` by one fixed step
 * (`scale_camera`, B7). Same requirement as `nudgeCamera`. */
export function scaleCamera(scene: string, grow: boolean): Promise<void> {
  return invoke("scale_camera", { scene, grow });
}
