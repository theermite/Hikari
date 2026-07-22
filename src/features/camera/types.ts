// Mirrors `CameraDevice` (protocol crate) — one real camera device detected on this
// machine, never a hardcoded/presumed list (B-cam tranche 1).

export interface CameraDevice {
  name: string;
  device_id: string;
}
