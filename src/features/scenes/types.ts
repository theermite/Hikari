// A loose mirror of the engine's wire protocol (`hikari-protocol::EngineMessage`) — only
// the fields this screen actually reads (F-003 spirit: never invent a shape the wire
// hasn't sent). Not a full protocol port; extend when a screen needs another field.

/** One scene as the engine sees it, mirroring `hikari_protocol::SceneInfo`. Field names are
 * the wire's own snake_case — renaming them here would silently stop matching the JSON. */
/** Ce qu'une source de capture vise : un jeu, une fenêtre, ou un écran. */
export type CaptureKind = "game" | "window" | "monitor";

/** Une chose capturable proposée par le moteur. `id` est la valeur exacte qu'il attend,
 * `label` est ce que l'utilisateur lit. */
export interface CaptureTarget {
  id: string;
  label: string;
}

/** Une source posée dans une scène. `kind` est l'identifiant libobs, jamais deviné. */
export interface SceneSourceInfo {
  name: string;
  kind: string;
}

export interface SceneInfo {
  name: string;
  has_camera: boolean;
  background_removal: boolean;
  circle_mask: boolean;
  sources: SceneSourceInfo[];
}

export interface EngineMessage {
  type: string;
  message?: string;
  scenes?: SceneInfo[];
  active?: string;
  games?: CaptureTarget[];
  windows?: CaptureTarget[];
  monitors?: CaptureTarget[];
}
