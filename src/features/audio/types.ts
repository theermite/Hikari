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

export interface AudioSourceInfo {
  name: string;
  kind: AudioSourceKind;
  /** 0–100 slider position, never the raw engine multiplier. */
  volume_percent: number;
  muted: boolean;
  monitoring: AudioMonitoring;
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
