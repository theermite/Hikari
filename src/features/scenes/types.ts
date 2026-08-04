// A loose mirror of the engine's wire protocol (`hikari-protocol::EngineMessage`) — only
// the fields this screen actually reads (F-003 spirit: never invent a shape the wire
// hasn't sent). Not a full protocol port; extend when a screen needs another field.

/** One scene as the engine sees it, mirroring `hikari_protocol::SceneInfo`. Field names are
 * the wire's own snake_case — renaming them here would silently stop matching the JSON. */
export interface SceneInfo {
  name: string;
  has_camera: boolean;
  background_removal: boolean;
  circle_mask: boolean;
}

export interface EngineMessage {
  type: string;
  message?: string;
  scenes?: SceneInfo[];
  active?: string;
}
