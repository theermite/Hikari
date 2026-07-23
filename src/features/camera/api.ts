// Camera Tauri bridge (B-cam tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { CameraDevice } from "./types";

/** Lists the real camera devices detected on this machine (`list_cameras`,
 * `camera_bridge.rs`) — never a hardcoded/presumed list (F-003's spirit). */
export function listCameras(): Promise<CameraDevice[]> {
  return invoke("list_cameras");
}

/** Adds `deviceId` (exact value from `listCameras`) as a real source in the live scene
 * (`add_camera_source`, `engine_lifecycle.rs`). Requires the engine to be running (the
 * Aperçu panel open) — rejects clearly otherwise, never a silent no-op. */
export function addCameraSource(deviceId: string): Promise<void> {
  return invoke("add_camera_source", { deviceId });
}

/** Sets whether the real NVIDIA background-removal filter is applied to the webcam
 * (`set_background_removal`). Toggling briefly rebuilds the camera source (a short
 * reinit blip) — no public API exists to detach a filter without it. Requires a camera
 * already added. */
export function setBackgroundRemoval(enabled: boolean): Promise<void> {
  return invoke("set_background_removal", { enabled });
}

/** Sets whether a circular alpha mask is applied to the webcam
 * (`set_circle_mask`). Same rebuild-based toggle as `setBackgroundRemoval`. */
export function setCircleMask(enabled: boolean): Promise<void> {
  return invoke("set_circle_mask", { enabled });
}

/** Removes the webcam from the scene entirely, its filters going with it
 * (`remove_camera_source`) — the real way to "turn the camera off" today, since
 * individual filters can't be detached. */
export function removeCameraSource(): Promise<void> {
  return invoke("remove_camera_source");
}
