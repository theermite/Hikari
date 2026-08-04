// Audio mixer Tauri bridge (B6) — thin `invoke` wrappers, no logic here.

import { invoke } from "@tauri-apps/api/core";
import type { AudioMonitoring, AudioSourceKind } from "./types";

/** Asks the engine to emit the machine's real audio devices. Requires the engine running
 * (the Aperçu panel open). */
export function listAudioDevices(): Promise<void> {
  return invoke("list_audio_devices");
}

/** Adds a microphone or desktop-audio capture to the mixer under `name`. `deviceId` comes
 * from the engine's device list, never guessed. */
export function addAudioSource(
  deviceId: string,
  kind: AudioSourceKind,
  name: string,
): Promise<void> {
  return invoke("add_audio_source", { deviceId, kind, name });
}

/** Removes an audio source from the mixer. */
export function removeAudioSource(name: string): Promise<void> {
  return invoke("remove_audio_source", { name });
}

/** Sets a source's volume from its 0–100 slider position. */
export function setAudioVolume(name: string, percent: number): Promise<void> {
  return invoke("set_audio_volume", { name, percent });
}

/** Mutes or unmutes a source, leaving its slider where the user put it. */
export function setAudioMuted(name: string, muted: boolean): Promise<void> {
  return invoke("set_audio_muted", { name, muted });
}

/** Sets whether the streamer hears this source, and whether the audience does. */
export function setAudioMonitoring(
  name: string,
  monitoring: AudioMonitoring,
): Promise<void> {
  return invoke("set_audio_monitoring", { name, monitoring });
}
