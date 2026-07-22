// Camera Tauri bridge (B-cam tranche 1) — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { CameraDevice } from "./types";

/** Lists the real camera devices detected on this machine (`list_cameras`,
 * `camera_bridge.rs`) — never a hardcoded/presumed list (F-003's spirit). */
export function listCameras(): Promise<CameraDevice[]> {
  return invoke("list_cameras");
}
