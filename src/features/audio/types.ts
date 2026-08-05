// Mirror of the engine's audio wire types (`hikari-protocol`) — only what this screen
// reads. Field names are the wire's own snake_case: renaming them here would silently stop
// matching the JSON.

export type AudioSourceKind = "input" | "output";

export interface AudioDevice {
  name: string;
  device_id: string;
}

/** Who hears a source: nobody but the audience, only the streamer, or both. */
export type AudioMonitoring = "none" | "monitor_only" | "monitor_and_output";

/** Which noise-removal method is in use. Counter-intuitive but verified in the OBS source:
 * only `speex` exposes a strength; `rnnoise` has none at all. */
export type NoiseMethod = "speex" | "rnnoise";

export interface AudioSourceInfo {
  name: string;
  kind: AudioSourceKind;
  /** 0–100 slider position for what the AUDIENCE hears. */
  volume_percent: number;
  /** 0–100 slider position for what the STREAMER hears in their headphones. */
  monitor_volume_percent: number;
  muted: boolean;
  monitoring: AudioMonitoring;
  /** Always false on a source that cannot carry room noise (desktop sound). */
  noise_suppression: boolean;
  noise_method: NoiseMethod;
  /** Speex's strength in decibels — an inverted scale: -60 is the strongest. */
  noise_level_db: number;
}

export interface AudioLevel {
  name: string;
  /** Decibels. 0 is the loudest undistorted signal; silence arrives as -Infinity. */
  magnitude_db: number;
}

export interface AudioEngineMessage {
  type: string;
  message?: string;
  inputs?: AudioDevice[];
  outputs?: AudioDevice[];
  items?: AudioSourceInfo[];
  levels?: AudioLevel[];
}
